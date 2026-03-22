"""
JSON Parser – wyciąganie i naprawa JSON z odpowiedzi modeli LLM.
Wyekstrahowany z core/agent.py dla lepszej czytelności i testowalności.
"""
import json
import re


class JSONParser:
    """
    Parsuje i naprawia JSON zwracany przez lokalne modele LLM.
    Obsługuje: markdown code blocks, trailing commas, komentarze,
    urwane odpowiedzi, bloki kodu (HTML/JS/Python → create_file actions).
    """

    # Frazy odmowy modelu
    REFUSAL_PHRASES = [
        "przykro mi, ale nie", "nie jestem w stanie",
        "odmawiam wykonania", "i'm unable", "i cannot",
        "nie mogę wykonać", "nie mogę pomóc w"
    ]

    def extract_json(self, raw: str) -> dict:
        """
        Wyciągnij czysty JSON z odpowiedzi modelu.
        Wykrywa odmowy modelu i rzuca czytelny wyjątek.
        """
        # Próba 1: bezpośredni parse (ZANIM wykryjemy odmowę)
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                # Normalizuj niestandardowe klucze które lokalne modele czasem zwracają
                _ALIASES = ("response", "text", "answer", "output", "reply", "result")
                if not data.get("message") and not data.get("actions"):
                    for alias in _ALIASES:
                        if alias in data and isinstance(data[alias], str):
                            data["message"] = data.pop(alias)
                            break
            if isinstance(data, dict) and data.get("message") and not data.get("actions"):
                msg_lower = data["message"].lower()
                if any(x in msg_lower for x in self.REFUSAL_PHRASES):
                    raise ValueError(
                        f"Model odmówił wykonania zadania: {data['message'][:120]}\n"
                        f"  Wskazówka: zmień sformułowanie zapytania lub użyj lokalnego modelu."
                    )

            # Napraw: model zwrócił fragment akcji bez "type" lub bez "actions" wrappera
            # oraz normalizuj akcje wewnątrz listy
            return self._postprocess(data)
        except json.JSONDecodeError:
            fixed = self.fix_json(raw)
            if fixed is not None:
                return self._postprocess(fixed)

        # Wykryj odmowę w surowym tekście (gdy JSON był niepoprawny)
        if '"message"' in raw and any(x in raw.lower() for x in [
            "przykro mi, ale nie", "nie jestem w stanie", "odmawiam wykonania"
        ]):
            msg_match = re.search(r'"message"\s*:\s*"([^"]{10,})', raw)
            if msg_match:
                raise ValueError(
                    f"Model odmówił wykonania zadania: {msg_match.group(1)[:120]}\n"
                    f"  Wskazówka: zmień sformułowanie zapytania lub użyj lokalnego modelu."
                )

        # Próba 2: markdown code block
        markdown_pattern = r'```(?:json)?\s*\n(.*?)\n```'
        match = re.search(markdown_pattern, raw, re.DOTALL)
        if match:
            try:
                return self._postprocess(json.loads(match.group(1)))
            except json.JSONDecodeError:
                fixed = self.fix_json(match.group(1))
                if fixed is not None:
                    return self._postprocess(fixed)

        # Próba 3: znajdź pierwszy { ... }
        json_start = -1
        json_char = None
        for i, char in enumerate(raw):
            if char == '{':
                json_start = i; json_char = '{'; break
            elif char == '[':
                json_start = i; json_char = '['; break

        if json_start == -1:
            raise ValueError("Nie znaleziono JSON w odpowiedzi modelu")

        bracket_count = 0
        json_end = -1
        closing_char = '}' if json_char == '{' else ']'

        for i in range(json_start, len(raw)):
            if raw[i] == json_char:
                bracket_count += 1
            elif raw[i] == closing_char:
                bracket_count -= 1
                if bracket_count == 0:
                    json_end = i + 1
                    break

        if json_end == -1:
            raise ValueError(
                "JSON nie ma zamkniętego nawiasu — model prawdopodobnie urwał odpowiedź.\n"
                f"  Fragment: {raw[:200]!r}"
            )

        try:
            return self._postprocess(json.loads(raw[json_start:json_end]))
        except json.JSONDecodeError as e:
            fixed = self.fix_json(raw[json_start:json_end])
            if fixed is not None:
                return self._postprocess(fixed)
            raise ValueError(f"Niepoprawny JSON: {e}")

    def _postprocess(self, data: dict) -> dict:
        """Normalizuje sparsowany JSON - naprawa typów, generowanie content itp."""
        if not isinstance(data, dict):
            return data
        if not data.get("message") and not data.get("actions") and not data.get("plan"):
            data = self._try_recover_malformed_action(data)
        if isinstance(data.get("actions"), list):
            data["actions"] = self._normalize_actions_list(data["actions"])
        return data

    @staticmethod
    def _escape_control_chars(s: str) -> str:
        """
        Zamienia dosłowne znaki kontrolne (0x00-0x1F) wewnatrz JSON stringow
        na prawidlowe sekwencje escape.

        To jest glowna przyczyna bledu:
          "Invalid control character at: line 1 column 68 (char 67)"
        Lokalne modele (glm, qwen, llama) czesto wstawiaja dosłowny 0x0A (newline)
        do stringa JSON zamiast sekwencji dwuznakowej backslash-n.

        Implementacja: state machine zamiast regex - poprawnie obsluguje
        znaki cudzyslowu i backslasha wewnatrz stringow.
        """
        ESCAPES = {'\n': '\\n', '\r': '\\r', '\t': '\\t',
                   '\b': '\\b', '\f': '\\f'}
        result = []
        in_string = False
        escape_next = False
        for c in s:
            if escape_next:
                result.append(c)
                escape_next = False
            elif c == '\\' and in_string:
                result.append(c)
                escape_next = True
            elif c == '"':
                in_string = not in_string
                result.append(c)
            elif in_string and ord(c) < 0x20:
                result.append(ESCAPES.get(c, f'\\u{ord(c):04x}'))
            else:
                result.append(c)
        return ''.join(result)

    def fix_json(self, text: str) -> dict | None:
        """
        Naprawia typowe błędy JSON generowane przez lokalne modele:
        - Znaki kontrolne wewnątrz stringów (\n, \t dosłownie zamiast \\n, \\t)
        - Komentarze // i /* */
        - Trailing commas (,} lub ,])
        - Pojedyncze cudzysłowy zamiast podwójnych
        - Niezakończone stringi (model urwał odpowiedź)
        """
        s = text

        # 0. Zawsze escapuj znaki kontrolne PRZED wszystkim innym.
        #    To najczęstsza przyczyna błędu:
        #      "Invalid control character at: line 1 column N"
        #    Lokalne modele (glm, qwen, llama) wstawiają dosłowny 0x0A/0x09
        #    w środek stringa JSON. Operacja jest bezpieczna — nie zmienia
        #    znaków poza stringami JSON.
        s = self._escape_control_chars(s)

        # 1. Usuń komentarze //
        s = re.sub(r'//[^\n"]*\n', '\n', s)
        # 2. Usuń komentarze blokowe /* ... */
        s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
        # 3. Trailing commas przed } lub ]
        s = re.sub(r',\s*([}\]])', r'\1', s)

        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

        # 4. Pojedyncze cudzysłowy → podwójne (tylko gdy brak podwójnych)
        if "'" in s and '"' not in s:
            try:
                return json.loads(s.replace("'", '"'))
            except json.JSONDecodeError:
                pass

        # 5. Napraw urwany JSON – dołącz brakujące nawiasy
        depth_curly = s.count('{') - s.count('}')
        depth_square = s.count('[') - s.count(']')
        if depth_curly > 0 or depth_square > 0:
            s3 = s.rstrip()
            if s3 and s3[-1] not in ('}', ']', '"'):
                s3 += '"'
            s3 += ']' * max(0, depth_square)
            s3 += '}' * max(0, depth_curly)
            try:
                return json.loads(s3)
            except json.JSONDecodeError:
                pass

        return None

    def extract_json_or_wrap(self, raw: str, rescue_fn=None) -> dict:
        """
        Próbuje wyciągnąć JSON z odpowiedzi modelu.
        Gdy model zwróci tekst zamiast JSON:
        - Wykrywa bloki kodu (```html, ```js itp.) → tworzy akcje create_file
        - Czysty tekst → owija w {"message": "..."}

        rescue_fn: opcjonalna funkcja rescue_code_from_message(str) -> dict | None
        """
        if not raw or not raw.strip():
            raise ValueError("Pusta odpowiedź modelu")

        try:
            return self.extract_json(raw)
        except ValueError as e:
            err_msg = str(e)
            if "Nie znaleziono JSON" not in err_msg \
               and "JSON nie ma zamkniętego" not in err_msg:
                raise

        # Model zwrócił tekst zamiast JSON
        if rescue_fn:
            rescued = rescue_fn(raw)
            if rescued:
                return rescued

        # Ostateczny fallback: owij w message
        cleaned = raw.strip()
        if len(cleaned) > 2000:
            cleaned = cleaned[:2000] + "..."
        return {"message": cleaned}

    # Znane pola dla każdego typu akcji — pozwala rozpoznać typ po zawartości
    _ACTION_FIELD_HINTS = {
        "read_file":   {"path"},
        "create_file": {"path", "content"},
        "edit_file":   {"path", "content"},
        "patch_file":  {"path", "patches"},
        "run_command": {"command", "code", "cmd", "shell", "bash"},
        "list_files":  {"pattern"},
        "mkdir":       {"path"},
        "delete_file": {"path"},
        "move_file":   {"from", "to"},
        "web_search":  {"query"},
        "save_memory": {"content", "fact", "note", "text"},
    }

    def _try_recover_malformed_action(self, data: dict) -> dict:
        """
        Próbuje naprawić JSON który wygląda jak akcja ale:
        - brakuje klucza "type" (model podał same parametry)
        - lub brakuje wrappera "actions": [...]

        Przykład wejścia:  { "path": "/home/user", "exclude": [".Trash"] }
        Przykład wyjścia:  { "message": "..." } lub { "actions": [...] }
        """
        keys = set(data.keys())

        # Specjalny przypadek: model zwrócił {"memory": {...}} lub {"memory": "..."}
        if "memory" in keys and len(keys) == 1:
            mem_val = data["memory"]
            if isinstance(mem_val, dict):
                # Spłaszcz wartości słownika do jednej notatki lub wielu faktów
                facts = []
                for k, v in mem_val.items():
                    if isinstance(v, str) and v.strip():
                        facts.append({"type": "save_memory", "content": v.strip(), "category": k})
                if facts:
                    return {"actions": facts}
            elif isinstance(mem_val, str) and mem_val.strip():
                return {"actions": [{"type": "save_memory", "content": mem_val.strip()}]}


        # Sprawdź czy pasuje do któregoś znanych typów akcji
        best_match = None
        best_score = 0
        for action_type, required_fields in self._ACTION_FIELD_HINTS.items():
            overlap = len(keys & required_fields)
            if overlap > best_score:
                best_score = overlap
                best_match = action_type

        if best_match and best_score >= 1:
            # Uzupełnij brakujący "type" i opakuj w "actions"
            action = dict(data)
            action["type"] = best_match

            # Normalizuj aliasy pól do wymaganych nazw
            if best_match == "run_command":
                for alias in ("code", "cmd", "shell", "bash"):
                    if alias in action and "command" not in action:
                        action["command"] = action.pop(alias)
                        break

            # Jeśli path wskazuje na katalog zamiast pliku — nie próbuj go czytać,
            # zamiast tego zwróć message żeby model dostał szansę na korektę
            if best_match in ("read_file", "create_file", "edit_file", "patch_file"):
                import os as _os
                path_val = str(action.get("path", ""))
                if path_val and _os.path.isdir(path_val):
                    import json as _json
                    return {"message": (
                        f"[Parser] Model podał katalog zamiast pliku: {path_val!r}. "
                        f"Oryginalny JSON: {_json.dumps(data, ensure_ascii=False)[:200]}"
                    )}

            return {"actions": [action]}

        # Nie rozpoznano — owij w message żeby przynajmniej coś wyświetlić
        import json as _json
        return {"message": f"[Parser] Model zwrócił nierozpoznany JSON: {_json.dumps(data, ensure_ascii=False)[:200]}"}

    # Aliasy nieznanych type → znane (synchronizowane z ActionValidator._TYPE_ALIASES)
    _TYPE_ALIASES = {
        "create_shortcut":     "create_file",
        "create-shortcut":     "create_file",
        "create_desktop_file": "create_file",
        "add_to_menu":         "create_file",
        "register_app":        "run_command",
        "install":             "run_command",
        "install_app":         "run_command",
        "pin":                 "run_command",
        "make_executable":     "chmod",
        "set_executable":      "chmod",
        "write_file":          "create_file",
        "save_file":           "create_file",
        "append_file":         "edit_file",
        "update_file":         "edit_file",
        "execute":             "run_command",
        "shell":               "run_command",
        "bash":                "run_command",
        "cmd":                 "run_command",
        "command":             "run_command",
        "search":              "web_search",
        "copy_file":           "run_command",
        "rename_file":         "move_file",
    }

    def _normalize_actions_list(self, actions: list) -> list:
        """
        Iteruje po liście akcji i dla każdej bez pola 'type' próbuje go
        wydedukować na podstawie obecnych pól - używając tej samej logiki
        co ActionValidator._guess_type, ale bez importu circular.
        """
        _FIELD_TYPE_HINTS = [
            ({"path", "content"},            "create_file"),
            ({"path", "patches"},            "patch_file"),
            ({"path", "match", "replace"},   "edit_file"),
            ({"path", "diff"},               "patch_file"),
            ({"from", "to"},                 "move_file"),
            ({"command"},                    "run_command"),
            ({"cmd"},                        "run_command"),
            ({"bash"},                       "run_command"),
            ({"shell"},                      "run_command"),
            ({"query"},                      "web_search"),
            ({"url"},                        "web_scrape"),
            ({"input_path", "output_format"}, "convert_media"),
            ({"input_path", "operation"},    "process_image"),
            ({"content", "category"},        "save_memory"),
            ({"content", "fact"},            "save_memory"),
            ({"path", "mode"},               "chmod"),
            ({"pattern"},                    "list_files"),
            ({"path"},                       "read_file"),
        ]
        result = []
        for action in actions:
            if not isinstance(action, dict):
                result.append(action)
                continue
            if "type" not in action:
                keys = set(action.keys())
                for required, guessed_type in _FIELD_TYPE_HINTS:
                    if keys >= set(required):
                        action = dict(action)
                        action["type"] = guessed_type
                        # Normalizuj aliasy run_command
                        if guessed_type == "run_command":
                            for alias in ("cmd", "bash", "shell"):
                                if alias in action and "command" not in action:
                                    action["command"] = action.pop(alias)
                                    break
                        break
            elif action["type"] in self._TYPE_ALIASES:
                action = dict(action)
                action["type"] = self._TYPE_ALIASES[action["type"]]
            elif action["type"] not in {
                "read_file","create_file","edit_file","patch_file","delete_file",
                "move_file","list_files","mkdir","chmod","open_path","run_command",
                "semantic_search","download_media","convert_media","process_image",
                "batch_images","image_info","web_search","web_scrape",
                "clipboard_read","clipboard_write","use_template","save_memory",
            }:
                # Całkowicie nieznany typ - próbuj odgadnąć z pól
                guessed = self._guess_type_from_fields(action)
                if guessed:
                    action = dict(action)
                    action["type"] = guessed

            # Auto-generuj content dla plików .desktop bez content
            if (
                action.get("type") == "create_file"
                and not action.get("content")
                and str(action.get("path", "")).endswith(".desktop")
            ):
                action = dict(action)
                action["content"] = self._generate_desktop_content(action)

            # Auto-generuj path dla create_file .desktop gdy brak path ale jest name
            if (
                action.get("type") == "create_file"
                and not action.get("path")
                and action.get("name")
            ):
                action = dict(action)
                action["path"] = self._desktop_path_from_name(action["name"])
                if not action.get("content"):
                    action["content"] = self._generate_desktop_content(action)

            result.append(action)
        return result

    def _guess_type_from_fields(self, action: dict) -> str | None:
        """
        Dla akcji z nieznanym type próbuje odgadnąć właściwy typ na podstawie pól.
        Rozszerzona wersja obsługująca aliasy pól (target, exec_command itp.).
        """
        keys = set(action.keys()) - {"type"}

        # Skróty .desktop: name + (exec|exec_command|target) → create_file
        if action.get("name") and (
            action.get("exec") or action.get("exec_command")
            or action.get("target") or action.get("command")
        ):
            return "create_file"

        # Standardowe dopasowania po polach
        hints = [
            ({"path", "content"},             "create_file"),
            ({"path", "patches"},             "patch_file"),
            ({"path", "match", "replace"},    "edit_file"),
            ({"path", "diff"},                "patch_file"),
            ({"from", "to"},                  "move_file"),
            ({"command"},                     "run_command"),
            ({"cmd"},                         "run_command"),
            ({"bash"},                        "run_command"),
            ({"shell"},                       "run_command"),
            ({"query"},                       "web_search"),
            ({"url"},                         "web_scrape"),
            ({"input_path", "output_format"}, "convert_media"),
            ({"input_path", "operation"},     "process_image"),
            ({"content", "category"},         "save_memory"),
            ({"path", "mode"},                "chmod"),
            ({"pattern"},                     "list_files"),
            ({"path"},                        "read_file"),
        ]
        for required, guessed in hints:
            if keys >= set(required):
                return guessed
        return None

    def _generate_desktop_content(self, action: dict) -> str:
        """
        Generuje treść pliku .desktop z pól podanych przez model zamiast 'content'.
        Obsługuje pola: name, exec, exec_command, target, comment, icon, terminal, categories, keywords
        """
        name     = action.get("name") or action.get("app_name") or "Aplikacja"
        exec_cmd = (action.get("exec") or action.get("exec_command")
                    or action.get("target") or action.get("command") or "")
        comment  = action.get("comment") or action.get("description") or f"Uruchom {name}"
        icon     = action.get("icon") or "applications-games"
        terminal = "true" if action.get("terminal") else "false"
        cats     = action.get("categories") or action.get("category") or "Game;"
        if not cats.endswith(";"):
            cats += ";"

        lines = [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={name}",
            f"Comment={comment}",
            f"Exec={exec_cmd}",
            f"Icon={icon}",
            f"Terminal={terminal}",
            f"Categories={cats}",
        ]
        if action.get("keywords"):
            lines.append(f"Keywords={action['keywords']}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _desktop_path_from_name(name: str) -> str:
        """Generuje ścieżkę .desktop z nazwy aplikacji."""
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return f"/home/{__import__('os').getenv('USER', 'user')}/.local/share/applications/{slug}.desktop"

    def rescue_code_from_message(self, message: str) -> dict | None:
        """
        Wykrywa bloki kodu w wiadomości tekstowej i tworzy akcje create_file.
        Używane gdy model zwrócił kod zamiast JSON.
        """
        # Ścieżka 1: bloki ```lang ... ```
        code_block_pattern = r'```(\w+)?\s*\n(.*?)\n```'
        blocks = re.findall(code_block_pattern, message, re.DOTALL)

        if blocks:
            actions = []
            ext_map = {
                'html': 'index.html', 'javascript': 'script.js', 'js': 'script.js',
                'css': 'style.css', 'python': 'main.py', 'py': 'main.py',
                'bash': 'script.sh', 'sh': 'script.sh', 'typescript': 'main.ts',
                'ts': 'main.ts', 'json': 'data.json', 'yaml': 'config.yaml',
                'yml': 'config.yaml', 'sql': 'query.sql', 'rust': 'main.rs',
            }
            for lang, code in blocks:
                lang = (lang or '').lower()
                filename = ext_map.get(lang, f'code.{lang}' if lang else 'code.txt')
                actions.append({
                    "type": "create_file",
                    "path": filename,
                    "content": code.strip()
                })
            if actions:
                return {"actions": actions}

        # Ścieżka 2: raw HTML bez backticks
        if message.strip().startswith('<!DOCTYPE') or message.strip().startswith('<html'):
            return {"actions": [{"type": "create_file", "path": "index.html", "content": message.strip()}]}

        # Ścieżka 3: wiadomość zawiera duży blok HTML
        html_match = re.search(r'(<!DOCTYPE.*?</html>)', message, re.DOTALL | re.IGNORECASE)
        if html_match and len(html_match.group(1)) > 200:
            return {"actions": [{"type": "create_file", "path": "index.html", "content": html_match.group(1).strip()}]}

        return None
