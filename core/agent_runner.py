"""
agent_runner.py – główna pętla iteracji run() i metody pomocnicze iteracji.

Wydzielony z agent.py (refaktoryzacja: agent.py > 2000 linii).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List

from core.agent_state import (
    AgentState, DoneReason, FailedReason,
    IterationContext, StagnationDetector,
)

if TYPE_CHECKING:
    from core.agent import AIAgent


class AgentRunnerMixin:
    """Mixin zawierający główną pętlę run() i logikę iteracji."""

    def run(self: "AIAgent", user_input: str):
        """Główny punkt wejścia - obsługa zapytania użytkownika."""
        from classification.intent_classifier import IntentClassifier
        from core.ollama import OllamaConnectionError
        from planning.action_planner import ActionPlanner
        from planning.action_validator import ActionValidator, ActionRisk
        from project.global_mode import GlobalMode
        from tasks.web_search import WebSearchError, RateLimitError

        self.execution_failed = False
        self.last_failed_command = None

        if self.logger:
            self.logger.debug(f"User input: {user_input}")

        system_answer = GlobalMode.handle_system_query(user_input)
        if system_answer:
            self.ui.success(system_answer)
            self.conversation.add_user_message(user_input)
            self.conversation.add_ai_message(system_answer)
            return

        if self.conversation.has_pending_confirmation():
            if self.conversation.is_confirmation_response(user_input):
                decision = self.conversation.get_confirmation_decision(user_input)
                if decision:
                    pending_actions = self.conversation.get_pending_actions()
                    if pending_actions:
                        self._execute_pending_actions(pending_actions)
                    self.conversation.clear_pending_confirmation()
                else:
                    self.ui.warning("Operacja anulowana")
                    self.conversation.clear_pending_confirmation()
                return

        if self.global_mode:
            self._run_global_mode(user_input)
            return

        if self.config.get('project', {}).get('auto_analyze_on_change', True):
            if self._is_project_reasonable_size():
                self._ensure_project_analyzed()

        if self._is_project_question(user_input):
            self._handle_project_question()
            return

        self.conversation.add_user_message(user_input)
        if self.conv_history:
            self.conv_history.append("user", user_input)

        web_search_context = self._maybe_web_search_context(user_input)
        rag_context = self._get_rag_context(user_input)

        _img_exts = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tiff')
        _has_image = any(ext in user_input.lower() for ext in _img_exts)
        _image_paths = self._extract_image_paths(user_input) if _has_image else []

        intent_result = IntentClassifier.classify(user_input)
        # Tłumaczenia dla TUI audit trail
        _conf_pl = {"high": "wysoka", "medium": "średnia", "low": "niska"}
        _intent_pl = {
            "explore":  "eksploracja",
            "modify":   "modyfikacja",
            "create":   "tworzenie",
            "delete":   "usuwanie",
            "execute":  "wykonanie",
            "query":    "zapytanie",
            "other":    "inne",
        }
        _iv = intent_result.intent.value
        _cv = intent_result.confidence.value
        _conf_str = _conf_pl.get(_cv, _cv)
        _intent_str = _intent_pl.get(_iv, _iv)
        self.ui.verbose(f"Zamiar: {_intent_str} (pewność: {_conf_str})")
        self.ui.verbose(f"Uzasadnienie: {intent_result.reasoning}")

        conversation_context = self.conversation.format_context_for_prompt()
        intent_context = self._format_intent_context(intent_result)

        messages = [
            {"role": "system", "content": self._build_system_prompt(user_input) + conversation_context + intent_context + web_search_context + rag_context},
            {"role": "user", "content": user_input + self._json_reminder()}
        ]

        _iter_ctx = IterationContext(max_iterations=8)
        _stagnation = StagnationDetector()
        _read_file_counts: dict = {}

        while _iter_ctx.tick():
            iteration = _iter_ctx.current_iteration - 1
            self.execution_failed = False
            self.last_failed_command = None
            self.ui.spinner_start("Analizuję...")

            if self.logger:
                self.logger.debug(
                    f"[{AgentState.THINKING.value}] iter={_iter_ctx.current_iteration} "
                    f"remaining={_iter_ctx.remaining_iterations}"
                )

            try:
                raw = self.client.chat(messages, user_input=user_input, has_image=_has_image, image_paths=_image_paths)
            except OllamaConnectionError as e:
                self.ui.spinner_stop()
                self.ui.error("Nie można połączyć się z Ollamą!")
                self.ui.verbose(f"Serwer: {e.host}:{e.port}")
                print()
                print(e.reason)
                if self.logger:
                    self.logger.error(f"Ollama connection failed: {e.reason}")
                return
            except KeyboardInterrupt:
                self.ui.spinner_stop()
                print()
                self.ui.warning("Przerwano przez użytkownika")
                return
            except Exception as e:
                self.ui.spinner_stop()
                self.ui.error(f"Błąd komunikacji z modelem: {e}")
                if self.logger:
                    self.logger.error(f"Model communication error: {e}", exc_info=True)
                return
            finally:
                self.ui.spinner_stop()

            if not raw or not raw.strip():
                self.ui.error("Model zwrócił pustą odpowiedź")
                return

            try:
                data = self._extract_json_or_wrap(raw)
            except Exception as e:
                self.ui.error(f"Błąd parsowania JSON: {e}")
                self.ui.verbose(f"Surowa odpowiedź: {raw[:200]}")
                if self.logger:
                    self.logger.error(f"JSON parse error: {e}")
                    self.logger.log_model_response(user_input, raw, error=str(e))
                return

            if self.plan_only and data.get("plan"):
                self.ui.section("Plan działania")
                for i, step in enumerate(data["plan"], 1):
                    self.ui.success(f"{i}. {step}")
                return

            if data.get("message") and not data.get("actions"):
                _file_injected = self._inject_existing_file_if_needed(user_input, data["message"], messages)
                if _file_injected:
                    messages.append({"role": "assistant", "content": raw})
                    continue

                rescued = self._rescue_code_from_message(data["message"])
                if rescued:
                    data = rescued
                else:
                    if self.logger:
                        self.logger.log_model_response(user_input, raw, parsed=data)
                        self.logger.log_session_turn(user_input, data["message"])
                    self.ui.ai_message(data["message"])
                    self.conversation.add_ai_message(data["message"])
                    mem_cfg = self.config.get("memory", {})
                    if mem_cfg.get("auto_extract", True):
                        saved = self.global_memory.auto_extract_and_save(user_input, data["message"])
                        if mem_cfg.get("show_saved", True):
                            for f in saved:
                                self.ui.success(f"💾 Zapamiętano [{f['id']}]: {f['content']}")
                    if self.logger:
                        self.logger.reset_run(user_input)
                    return

            actions = data.get("actions", [])

            if not actions:
                if data.get("message"):
                    self.ui.ai_message(data["message"])
                    self.conversation.add_ai_message(data["message"])
                    if self.conv_history:
                        self.conv_history.append("assistant", data["message"])
                    if self.logger:
                        self.logger.reset_run(user_input)
                    return
                self.ui.error("Model nie zwrócił ani akcji, ani odpowiedzi.")
                if self.logger:
                    self.logger.log_model_response(user_input, raw, parsed=data, error="empty_response")
                return

            # Walidacja i planowanie
            max_actions = self.config.get('behavior', {}).get('max_actions_per_run', 10)
            if len(actions) > max_actions:
                self.ui.warning(f"Zbyt wiele akcji ({len(actions)}), limit to {max_actions}")
                if not self.ui.confirm_actions():
                    return

            valid, errors = ActionValidator.validate(actions)
            if not valid:
                self.ui.error("Akcje zawierają błędy:")
                for err in errors:
                    self.ui.error(f"  • {err}")
                return

            if self.capabilities:
                caps_valid, caps_errors = self.capabilities.validate_actions(actions)
                if not caps_valid:
                    self.ui.error("Akcje naruszają ograniczenia projektu:")
                    for err in caps_errors:
                        self.ui.error(f"  • {err}")
                    return

            action_plan = ActionPlanner.create_plan(intent_result, actions)
            if not action_plan.is_valid():
                self.ui.error("Plan zawiera błędy krytyczne:")
                print(ActionPlanner.format_plan_summary(action_plan))
                return

            actions = ActionPlanner.optimize_order(actions)
            risk_summary = ActionValidator.get_risk_summary(actions)
            self.ui.section(f"Do wykonania: {len(actions)} akcji")
            print(risk_summary)

            if self.project_root:
                print()
                self.ui.success(f"📁 Katalog projektu: {self.project_root}")
            print()

            for i, action in enumerate(actions, 1):
                self.ui.action_preview(i, self._describe_action(action))

            self._show_impact_and_semantic(actions, user_input)

            needs_confirm = self._needs_confirm(actions)
            if needs_confirm and not self.auto_confirm and not self.plan_only:
                if not self.ui.confirm_actions():
                    self.ui.warning("Anulowano przez użytkownika")
                    self.ui.success(
                        "Nie wykonałem akcji, bo nie zaakceptowałeś. "
                        "Co robimy? Możesz zmienić polecenie, doprecyzować zakres lub wpisać \"nie rób nic\"."
                    )
                    return

            if not self.plan_only:
                self.ui.spinner_start("Wykonywanie akcji...")

            if self.logger:
                self.logger.info(
                    f"[{AgentState.EXECUTING.value}] "
                    f"actions={len(actions)} iter={_iter_ctx.current_iteration}"
                )

            results = self._execute_with_transaction(actions)

            if not self.plan_only:
                self.ui.spinner_stop()

            intent = self._extract_intent_from_data(data, user_input, actions)
            if self.memory:
                self.memory.update_from_actions(actions, user_input, intent=intent)

            if self.logger and actions and not self.plan_only:
                self.logger.log_operation(user_input=user_input, actions=actions, results=results, intent=intent)
                self.logger.log_model_response(user_input, raw, parsed=data)
                ai_summary = data.get("message", f"{len(actions)} akcji: " + ", ".join(a.get("type", "?") for a in actions[:3]))
                self.logger.log_session_turn(user_input, ai_summary, actions=actions)

            had_rollback = any(
                isinstance(r, dict) and r.get("type") == "transaction_rolled_back"
                for r in results
            )

            if actions and not self.plan_only:
                self.ui.section("Zakończono")
                self._summarize_results(actions, results)

            if data.get("message"):
                print()
                if had_rollback:
                    self.ui.warning("Operacja cofnięta (rollback)")
                    self.ui.verbose(f"AI sugerowało: {data['message']}")
                else:
                    self.ui.ai_message(data["message"])
                if self.logger:
                    self.logger.reset_run(user_input)
                return

            needs_next = self._results_need_followup(results, _read_file_counts)
            if not needs_next:
                # Poprawka #5: jeśli agent zakończył serię akcji bez żadnej wiadomości
                # tekstowej, wymuś rundę podsumowującą zamiast milczeć.
                # Bez tego użytkownik musiał pisać "i co?" żeby dostać odpowiedź.
                if not data.get("message"):
                    self._append_iteration_messages(messages, raw, actions, results,
                                                    force_action=False)
                    messages.append({
                        "role": "user",
                        "content": json.dumps({
                            "type": "system_instruction",
                            "instruction": (
                                "Zakończyłeś wykonywanie akcji. "
                                "Teraz podsumuj wyniki użytkownikowi w polu 'message'. "
                                "Co znalazłeś/wykonałeś? Jakie są wyniki? "
                                "Odpowiedz zwięźle i konkretnie. "
                                "Zwróć TYLKO: {\"message\": \"...\"}."
                            )
                        }, ensure_ascii=False)
                    })
                    # Jedna dodatkowa runda — tylko po odpowiedź tekstową
                    try:
                        summary_raw = self.client.chat(
                            messages, user_input=user_input,
                            has_image=False, image_paths=[]
                        )
                        summary_data = self._extract_json_or_wrap(summary_raw)
                        if summary_data.get("message"):
                            self.ui.ai_message(summary_data["message"])
                            self.conversation.add_ai_message(summary_data["message"])
                            if self.logger:
                                self.logger.log_model_response(user_input, summary_raw, parsed=summary_data)
                                self.logger.log_session_turn(user_input, summary_data["message"])
                    except Exception:
                        pass  # Jeśli auto-summary zawiedzie, po prostu kończymy cicho
                if self.logger:
                    self.logger.reset_run(user_input)
                return

            for a in actions:
                if a.get("type") == "read_file":
                    p = a.get("path", "")
                    _read_file_counts[p] = _read_file_counts.get(p, 0) + 1

            _iter_ctx.record_actions(actions)

            is_stagnant, stagnation_reason = _stagnation.check(_iter_ctx)
            if is_stagnant:
                self.ui.warning(f"Wykryto pętlę: {stagnation_reason}")
                if self.logger:
                    self.logger.warning(
                        f"[{AgentState.FAILED.value}] reason={FailedReason.STAGNATION.value} "
                        f"{stagnation_reason} | {_iter_ctx.summary()}"
                    )
                return

            self._append_iteration_messages(messages, raw, actions, results,
                                            force_action=_iter_ctx.should_force_action)

        self.ui.verbose(f"Osiągnięto limit {_iter_ctx.max_iterations} iteracji")

    # ── Helpers dla run() ──────────────────────────────────────────────────────

    def _maybe_web_search_context(self: "AIAgent", user_input: str) -> str:
        """Auto-trigger web search jeśli włączony i wykryto frazę."""
        from tasks.web_search import WebSearchError, RateLimitError

        if not self.config.get("web_search", {}).get("enabled", False):
            return ""
        if not self.config.get("web_search", {}).get("auto_trigger", True):
            return ""

        engine = self.web_search_engine
        if not engine.detect_trigger(user_input):
            return ""

        self.ui.verbose("Wyszukiwanie w internecie...")
        try:
            results = engine.search(user_input, max_results=engine._ws_config.get("max_results", 5))
            if results:
                if self.logger:
                    self.logger.info(f"Web search auto-triggered: {user_input!r}, {len(results)} results")
                return (
                    "\n\n=== WYNIKI WYSZUKIWANIA (auto-trigger) ===\n"
                    + engine.format_results_for_prompt(results)
                    + "\n=== KONIEC WYNIKÓW ===\n"
                    + "Użyj powyższych wyników aby odpowiedzieć na pytanie użytkownika.\n"
                )
        except (WebSearchError, RateLimitError) as e:
            self.ui.verbose(f"⚠ Web search: {e}")
        except Exception as e:
            self.ui.verbose(f"⚠ Web search error: {e}")
        return ""

    def _format_intent_context(self: "AIAgent", intent_result) -> str:
        from classification.intent_classifier import IntentClassifier

        suggested = ', '.join(IntentClassifier.get_suggested_actions(intent_result.intent, intent_result.scope))
        return f"""

    ====================
    ROZPOZNANY INTENT
    ====================

    Intent: {intent_result.intent.value}
    Confidence: {intent_result.confidence.value}
    Scope: {intent_result.scope}
    Reasoning: {intent_result.reasoning}

    Suggested actions: {suggested}

    IMPORTANT: Your response should align with this detected intent.
    """

    def _show_impact_and_semantic(self: "AIAgent", actions: list, user_input: str):
        """Wyświetl analizę wpływu i decyzje semantyczne."""
        if self.impact:
            impact_report = self.impact.analyze_impact(actions)
            if impact_report["severity"] in ["medium", "high", "critical"]:
                print()
                self.ui.section("Analiza wpływu")
                print(self.impact.format_impact_report(impact_report))

        if self.semantic:
            semantic_decision = self.semantic.detect_semantic_change(actions, user_input)
            if semantic_decision:
                print()
                self.ui.section("Decyzja semantyczna")
                self.ui.success(f"{semantic_decision.type}: {semantic_decision.old} → {semantic_decision.new}")
                suggestions = self.semantic.suggest_related_changes(semantic_decision)
                if suggestions:
                    self.ui.verbose("Sugerowane dodatkowe zmiany:")
                    for s in suggestions[:3]:
                        self.ui.verbose(f"  • {s}")
                self.semantic.add_decision(semantic_decision)

    def _append_iteration_messages(
        self: "AIAgent",
        messages: list,
        raw: str,
        actions: list,
        results: list,
        force_action: bool = False
    ):
        """Dodaj wyniki iteracji do historii - skrótowo."""
        action_summary = [
            {"type": a.get("type"), "path": a.get("path") or a.get("from", "")}
            for a in actions
        ]
        messages.append({
            "role": "assistant",
            "content": json.dumps({"actions": action_summary}, ensure_ascii=False)
        })

        short_results = []
        for r in results:
            if isinstance(r, str):
                short_results.append(r[:300])
            elif isinstance(r, dict):
                if r.get("type") == "file_content":
                    content_str = r.get("content", "")
                    path = r.get("path", "")
                    is_config = any(path.endswith(ext) for ext in (".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".env"))
                    limit = len(content_str) if (is_config and len(content_str) < 8000) else 2000
                    short_results.append({
                        "type": "file_content",
                        "path": path,
                        "content": content_str[:limit],
                        "instruction": "Masz treść pliku. TERAZ wykonaj żądaną modyfikację używając patch_file. NIE czytaj pliku ponownie — masz już jego zawartość."
                    })
                elif r.get("type") == "web_search_results":
                    raw_results = r.get("results", [])
                    formatted = []
                    for idx, res in enumerate(raw_results[:5], 1):
                        t = res.get("title", "")
                        u = res.get("url", "")
                        s = res.get("snippet", "")
                        formatted.append(f"[{idx}] TYTUŁ: {t}\n    URL: {u}\n    SNIPPET: {s[:200]}")
                    short_results.append({
                        "type": "web_search_results",
                        "query": r.get("query", ""),
                        "count": r.get("count", len(raw_results)),
                        "INSTRUKCJA_KRYTYCZNA": (
                            "Podając nagłówki lub wyniki: używaj DOKŁADNYCH tytułów i URL z listy poniżej. "
                            "NIE parafrazuj tytułów. NIE konstruuj URL z głowy."
                        ),
                        "wyniki": formatted,
                    })
                else:
                    short_results.append(r)
            else:
                short_results.append(str(r)[:300])

        if force_action:
            short_results.append({
                "type": "system_instruction",
                "instruction": (
                    "MASZ JUŻ WSZYSTKIE POTRZEBNE DANE. "
                    "TERAZ wykonaj zadanie: utwórz pliki (create_file) i zakończ z message. "
                    "NIE rób kolejnych run_command ani read_file."
                )
            })

        messages.append({
            "role": "user",
            "content": json.dumps(short_results, ensure_ascii=False)
        })

        # Ogranicz historię do 6 wiadomości (3 pary)
        system_msgs = [m for m in messages if m["role"] == "system"]
        other_msgs = [m for m in messages if m["role"] != "system"]
        if len(other_msgs) > 6:
            other_msgs = other_msgs[-6:]
        messages.clear()
        messages.extend(system_msgs)
        messages.extend(other_msgs)

    def _results_need_followup(self: "AIAgent", results: list, read_counts: dict | None = None) -> bool:
        """Czy wyniki akcji wymagają kolejnej iteracji?"""
        MODIFICATION_SIGNALS = ["Zaktualizowano", "Utworzono", "Usunięto", "Przeniesiono", "template_applied"]
        has_modification = any(
            isinstance(r, str) and any(sig in r for sig in MODIFICATION_SIGNALS)
            for r in results
        )
        if has_modification:
            return False

        ANALYSIS_NEEDED = {
            "file_list", "semantic_result", "clipboard_content",
            "web_search_results", "web_scrape_result", "web_scrape_blocked",
            "web_search_disabled", "web_search_missing_deps", "image_info_result",
            # Usprawnienie 4: timeout komendy wymaga iteracji żeby model
            # poinformował użytkownika — bez tego agent milczał po timeoucie
            "command_timeout", "command_error",
        }
        has_file_content = False

        for r in results:
            if isinstance(r, dict):
                rtype = r.get("type", "")
                if rtype == "file_content":
                    path = r.get("path", "")
                    if read_counts and read_counts.get(path, 0) >= 2:
                        return False
                    has_file_content = True
                elif rtype in ANALYSIS_NEEDED:
                    return True
                elif rtype == "command_result" and r.get("stdout", "").strip():
                    return True
            elif isinstance(r, str) and r.startswith("[BŁĄD]"):
                return True

        return has_file_content
