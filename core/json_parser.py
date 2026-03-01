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
            if isinstance(data, dict) and not data.get("message") and not data.get("actions") and not data.get("plan"):
                data = self._try_recover_malformed_action(data)

            return data
        except json.JSONDecodeError:
            fixed = self.fix_json(raw)
            if fixed is not None:
                return fixed

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
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                fixed = self.fix_json(match.group(1))
                if fixed is not None:
                    return fixed

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
            return json.loads(raw[json_start:json_end])
        except json.JSONDecodeError as e:
            fixed = self.fix_json(raw[json_start:json_end])
            if fixed is not None:
                return fixed
            raise ValueError(f"Niepoprawny JSON: {e}")

    def fix_json(self, text: str) -> dict | None:
        """
        Naprawia typowe błędy JSON generowane przez lokalne modele:
        - Komentarze // i /* */
        - Trailing commas (,} lub ,])
        - Pojedyncze cudzysłowy zamiast podwójnych
        - Niezakończone stringi (model urwał odpowiedź)
        """
        s = text

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
