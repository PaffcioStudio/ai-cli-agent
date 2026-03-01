import requests
import hashlib
import json
from pathlib import Path
from typing import Optional, List, Any
from core.model_manager import ModelRouter

class OllamaConnectionError(Exception):
    """Błąd połączenia z Ollama - czytelny dla użytkownika"""
    def __init__(self, host: str, port: int, reason: str):
        self.host = host
        self.port = port
        self.reason = reason
        super().__init__(f"Nie można połączyć się z Ollamą! ({host}:{port})")

class EmbeddingCache:
    """Cache embeddingów na dysku"""
    
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "ai-cli" / "embeddings"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _hash_text(self, text: str) -> str:
        """Hash tekstu dla cache key"""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def get(self, text: str):
        """Pobierz embedding z cache"""
        key = self._hash_text(text)
        cache_file = self.cache_dir / f"{key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    def set(self, text: str, embedding):
        """Zapisz embedding do cache"""
        key = self._hash_text(text)
        cache_file = self.cache_dir / f"{key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(embedding, f)
        except Exception:
            pass

class OllamaClient:
    def __init__(self, config, logger=None):
        self.base = f"http://{config['ollama_host']}:{config['ollama_port']}"
        self.chat_model = config['chat_model']
        self.embed_model = config['embed_model']
        self.config = config
        self.logger = logger

        # Dla komunikatów błędów
        self.host = config['ollama_host']
        self.port = config['ollama_port']

        # Cache embeddingów
        cache_enabled = config.get('semantic', {}).get('cache_embeddings', True)
        self.embed_cache = EmbeddingCache() if cache_enabled else None

        # ModelRouter – fallback + smart routing
        self.router = ModelRouter(config)

    def _handle_connection_error(self, e: Exception, operation: str) -> None:
        """
        Ujednolicona obsługa błędów połączenia.
        
        Tłumaczy surowe błędy requests na czytelne komunikaty.
        """
        import requests.exceptions
        
        # Określ typ błędu
        if isinstance(e, requests.exceptions.HTTPError):
            # ===== NOWE: Obsługa HTTP 429 (Rate Limiting) =====
            if hasattr(e, 'response') and e.response.status_code == 429:
                reason = "HTTP 429 - Rate Limit Exceeded"
                
                # Sprawdź czy to cloud model
                is_cloud = ':cloud' in self.chat_model or ':cloud' in self.embed_model
                
                if is_cloud:
                    suggestion = (
                        f"Używasz cloud modelu: {self.chat_model}\n"
                        f"Cloud modele mają limity API (rate limiting).\n\n"
                        f"Rozwiązania:\n"
                        f"  1. Poczekaj 1-2 minuty i spróbuj ponownie\n"
                        f"  2. Zmień na lokalny model:\n"
                        f"     ai model\n"
                        f"     # Wybierz model bez ':cloud' w nazwie\n"
                        f"  3. Sprawdź swój Usage Limit na Ollama (po zalogowaniu):\n"
                        f"     https://ollama.com/settings/usage\n"
                        f"  4. Sprawdź limity cloud modelu:\n"
                        f"     https://ollama.com/library/{self.chat_model.split(':')[0]}\n"
                        f"  5. Jeśli problem się powtarza:\n"
                        f"     - Zwiększ timeout w config:\n"
                        f'       "execution": {{"timeout_seconds": 60}}\n'
                        f"     - Lub użyj lokalnego modelu (bez rate limitów)"
                    )
                else:
                    suggestion = (
                        f"Ollama zwróciła HTTP 429 (za dużo requestów).\n\n"
                        f"Możliwe przyczyny:\n"
                        f"  1. Zbyt wiele równoczesnych zapytań\n"
                        f"  2. Rate limiting w Ollama proxy\n"
                        f"  3. Ollama jest przeciążona\n\n"
                        f"Rozwiązania:\n"
                        f"  1. Poczekaj chwilę i spróbuj ponownie\n"
                        f"  2. Sprawdź logi Ollama:\n"
                        f"     journalctl -u ollama -f\n"
                        f"  3. Restart Ollama:\n"
                        f"     systemctl restart ollama\n"
                        f"  4. Sprawdź konfigurację rate limitów w Ollama"
                    )
                
                # Log
                if self.logger:
                    self.logger.error(
                        f"Ollama rate limit (429) during {operation}: {self.chat_model}",
                        exc_info=True
                    )
                
                # Rzuć czytelny wyjątek
                raise OllamaConnectionError(
                    self.host,
                    self.port,
                    f"{reason}\n\n{suggestion}"
                )
            
            # Inne HTTP błędy
            status_code = e.response.status_code if hasattr(e, 'response') else "unknown"
            reason = f"HTTP {status_code}"
            
            if status_code == 404:
                suggestion = (
                    f"Model nie znaleziony.\n"
                    f"  Sprawdź dostępne modele: ollama list\n"
                    f"  Pobierz model: ollama pull {self.chat_model}"
                )
            elif status_code == 500:
                suggestion = (
                    f"Ollama zwróciła błąd wewnętrzny.\n"
                    f"  Sprawdź logi: journalctl -u ollama -f"
                )
            else:
                suggestion = f"Sprawdź status Ollama:\n  curl http://{self.host}:{self.port}/api/tags"
        
        elif isinstance(e, requests.exceptions.ConnectionError):
            # Wyciągnij szczegóły
            error_str = str(e)
            
            if "No route to host" in error_str:
                reason = "Serwer jest nieosiągalny (No route to host)"
                suggestion = (
                    f"Sprawdź:\n"
                    f"  1. Czy serwer {self.host} jest włączony\n"
                    f"  2. Czy firewall nie blokuje połączenia\n"
                    f"  3. Czy adres IP jest poprawny\n"
                    f"  4. Czy Ollama działa na tym serwerze:\n"
                    f"     curl http://{self.host}:{self.port}/api/tags"
                )
            
            elif "Connection refused" in error_str:
                reason = "Połączenie odrzucone (Connection refused)"
                suggestion = (
                    f"Ollama nie nasłuchuje na porcie {self.port}.\n"
                    f"  1. Sprawdź czy Ollama działa: systemctl status ollama\n"
                    f"  2. Jeśli nie - uruchom: systemctl start ollama\n"
                    f"  3. Sprawdź port: lsof -i :{self.port}"
                )
            
            elif "timed out" in error_str or "Timeout" in error_str:
                reason = "Timeout - serwer nie odpowiada"
                suggestion = (
                    f"Serwer {self.host} jest zbyt wolny lub przeciążony.\n"
                    f"  1. Sprawdź obciążenie serwera\n"
                    f"  2. Zwiększ timeout w config:\n"
                    f"     nano ~/.config/ai/config.json\n"
                    f'     "execution": {{"timeout_seconds": 60}}\n'
                    f"  3. Rozważ lokalną instancję Ollama"
                )
            
            else:
                reason = f"Błąd połączenia: {str(e)[:100]}"
                suggestion = (
                    f"Sprawdź:\n"
                    f"  1. Konfigurację: ai config\n"
                    f"  2. Czy Ollama działa:\n"
                    f"     curl http://{self.host}:{self.port}/api/tags\n"
                    f"  3. Logi: journalctl -u ollama -f"
                )
        
        elif isinstance(e, requests.exceptions.Timeout):
            reason = "Timeout - serwer nie odpowiedział w czasie"
            suggestion = (
                f"Zwiększ timeout w ~/.config/ai/config.json:\n"
                f'  "execution": {{"timeout_seconds": 60}}'
            )
        
        else:
            reason = str(e)
            suggestion = "Nieznany błąd - sprawdź logi: ai logs"
        
        # Log
        if self.logger:
            self.logger.error(
                f"Ollama connection failed during {operation}: {reason}",
                exc_info=True
            )
        
        # Rzuć czytelny wyjątek
        raise OllamaConnectionError(
            self.host,
            self.port,
            f"{reason}\n\n{suggestion}"
        )

    def _is_thinking_model(self, model: str = "") -> bool:
        """Sprawdź czy model używa extended thinking (zwraca <think>...</think>)."""
        thinking_models = ["qwen3", "deepseek-r", "deepseek-v3", "r1", "marco-o1", "skywork-o1"]
        model_lower = (model or self.chat_model).lower()
        return any(m in model_lower for m in thinking_models)

    def _strip_thinking(self, content: str) -> str:
        """
        Usuń bloki <think>...</think> z odpowiedzi modelu thinking.
        Modele thinking (qwen3, deepseek-r1 itp.) zwracają najpierw rozumowanie,
        a dopiero potem właściwą odpowiedź JSON.
        """
        import re
        # Usuń wszystkie bloki <think>...</think> (mogą być wieloliniowe)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        return content.strip()

    def chat(self, messages, user_input: str = "", has_image: bool = False, image_paths: list = None):
        """
        Obsługa KeyboardInterrupt i błędów połączenia podczas żądania do Ollama.
        Automatycznie obsługuje modele z thinking (qwen3, deepseek-r1 itp.)
        Używa ModelRouter dla fallback i smart routing (vision, coder, fallback).
        """
        try:
            timeout = self.config.get('execution', {}).get('timeout_seconds', 30)

            # ── ModelRouter: wybierz model ────────────────────────────────────
            selected_model, route_reason = self.router.select_model(user_input, has_image=has_image)
            effective_model = selected_model

            # Loguj routing jeśli nie jest domyślny
            if route_reason != "chat_model" and self.logger:
                self.logger.info(f"ModelRouter: {route_reason}")

            is_thinking = any(m in effective_model.lower()
                              for m in ["qwen3", "deepseek-r", "deepseek-v3", "r1", "marco-o1", "skywork-o1"])

            # Modele thinking NIE obsługują "format": "json" poprawnie
            is_cloud = ':cloud' in effective_model
            use_json_format = not is_thinking and not is_cloud

            # ── Wstrzyknij obrazy do ostatniej wiadomości (vision) ───────────
            if image_paths:
                import base64, os
                encoded_images = []
                for img_path in image_paths:
                    img_path = os.path.expanduser(img_path)
                    if os.path.isfile(img_path):
                        with open(img_path, "rb") as f:
                            encoded_images.append(base64.b64encode(f.read()).decode("utf-8"))
                if encoded_images:
                    # Dodaj images do ostatniej wiadomości user
                    messages = list(messages)
                    last = dict(messages[-1])
                    last["images"] = encoded_images
                    messages[-1] = last

            payload = {
                "model": effective_model,
                "messages": messages,
                "stream": False,
            }
            
            # Dla modeli thinking: wyłącz thinking w opcjach (szybciej, mniej tokenów)
            if is_thinking:
                payload["options"] = {"think": False}
            
            if use_json_format:
                payload["format"] = "json"
            
            r = requests.post(
                f"{self.base}/api/chat",
                json=payload,
                timeout=timeout
            )
            
            r.raise_for_status()  # Rzuć wyjątek dla 4xx/5xx

            response_data    = r.json()
            response_content = response_data["message"]["content"]

            # Usuń thinking bloki jeśli model je zwrócił
            if is_thinking and response_content:
                response_content = self._strip_thinking(response_content)

            # Log API call
            if self.logger and self.config.get('debug', {}).get('log_model_raw_output', False):
                self.logger.log_api_call(
                    request={"model": effective_model, "messages": messages},
                    response=response_content
                )

            # Jeśli byliśmy na fallback i się udało – deaktywuj (opcjonalne, zostaw fallback do końca okna)
            return response_content

        except KeyboardInterrupt:
            raise

        except requests.exceptions.RequestException as e:
            # ── Automatyczny fallback przy 429 / timeout ──────────────────────
            is_rate_limit = (
                hasattr(e, 'response') and
                e.response is not None and
                getattr(e.response, 'status_code', 0) == 429
            )
            is_timeout = isinstance(e, requests.exceptions.Timeout)

            if (is_rate_limit or is_timeout) and self.router.fallback_model:
                fb = self.router.fallback_model
                if self.logger:
                    self.logger.warning(f"Auto-fallback: {effective_model} → {fb} ({'rate limit' if is_rate_limit else 'timeout'})")
                self.router.activate_fallback(duration_minutes=60)
                reason_str = 'Rate limit (429)' if is_rate_limit else 'Timeout'
                print(f"\n⚠  {reason_str} – przełączam na fallback: {fb} (60 min)")
                # Ponów zapytanie z modelem fallback
                try:
                    r2 = requests.post(
                        f"{self.base}/api/chat",
                        json={"model": fb, "messages": messages, "stream": False},
                        timeout=timeout,
                    )
                    r2.raise_for_status()
                    return r2.json()["message"]["content"]
                except Exception as e2:
                    self._handle_connection_error(e2, f"chat (fallback: {fb})")

            # Normalny błąd połączenia
            self._handle_connection_error(e, "chat")

    def embed(self, text):
        """
        Embedding z cache i obsługą błędów połączenia
        """
        # Sprawdź cache
        if self.embed_cache:
            cached = self.embed_cache.get(text)
            if cached is not None:
                return cached
        
        # Generuj nowy
        try:
            timeout = self.config.get('execution', {}).get('timeout_seconds', 30)
            
            r = requests.post(
                f"{self.base}/api/embed",
                json={
                    "model": self.embed_model,
                    "input": text
                },
                timeout=timeout
            )
            
            r.raise_for_status()
            
            embedding = r.json()["embeddings"][0]
            
            # Zapisz do cache
            if self.embed_cache:
                self.embed_cache.set(text, embedding)
            
            return embedding
        
        except KeyboardInterrupt:
            # Użytkownik przerwał - rzuć dalej
            raise
        
        except requests.exceptions.RequestException as e:
            # Błąd połączenia - tłumacz na czytelny komunikat
            self._handle_connection_error(e, "embed")

    def semantic_search(self, query, documents):
        """
        Ulepszone semantic search z obsługą błędów
        """
        semantic_config = self.config.get('semantic', {})
        
        if not semantic_config.get('enabled', True):
            # Fallback: zwróć pliki w kolejności alfabetycznej
            return [doc['path'] for doc in documents[:10]]
        
        max_files = semantic_config.get('max_files', 50)
        boost_paths = semantic_config.get('boost_paths', [])
        
        # Ogranicz dokumenty
        documents = documents[:max_files]
        
        try:
            # Embedding query
            qv = self.embed(query)
            scored: List[tuple[float, str]] = []
            
            for doc in documents:
                path = doc['path']
                content = doc['content']
                
                # Osobne embeddingi dla path i content
                path_embedding = self.embed(path)
                content_embedding = self.embed(content[:1000])  # Krótszy snippet
                
                # Oblicz similarity - POPRAWKA: type hints dla Pylance
                path_score = sum(
                    float(a) * float(b) 
                    for a, b in zip(qv or [], path_embedding or [])
                    if a is not None and b is not None
                )
                
                content_score = sum(
                    float(a) * float(b)
                    for a, b in zip(qv or [], content_embedding or [])
                    if a is not None and b is not None
                )
                
                # Ważenie: path ważniejsza niż content
                final_score = (path_score * 0.6) + (content_score * 0.4)
                
                # Boost dla priorytetowych ścieżek
                for boost_path in boost_paths:
                    if boost_path in path:
                        final_score *= 1.3
                
                scored.append((final_score, path))
            
            scored.sort(reverse=True)
            return [path for _, path in scored]
        
        except KeyboardInterrupt:
            # Użytkownik przerwał - rzuć dalej
            raise
        
        except OllamaConnectionError:
            # Już obsłużone w embed() - rzuć dalej
            raise