#!/usr/bin/env python3
"""
Web Panel Server - lokalny serwer HTTP dla panelu administracyjnego.

BEZPIECZEŃSTWO:
- Binduje się TYLKO do 127.0.0.1 (localhost)
- NIE wystawia się na WAN
- NIE wykonuje komend
- NIE interpretuje promptów użytkownika
- Read & config surface, nie execution surface
"""

import http.server
import socketserver
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import mimetypes

# POPRAWKA: requests jest opcjonalny (tylko dla Ollama check)
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Ścieżki
CONFIG_DIR = Path.home() / ".config" / "ai"
CONFIG_FILE = CONFIG_DIR / "config.json"
PROMPT_FILE = CONFIG_DIR / "prompt.txt"
WEB_DIR = Path(__file__).parent

# Port
PORT = 21650
HOST = "127.0.0.1"

class PanelHandler(http.server.SimpleHTTPRequestHandler):
    """Handler dla panelu webowego"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)
    
    def do_GET(self):
        """Obsługa GET requests"""
        parsed_path = urlparse(self.path)
        
        # API endpoints
        if parsed_path.path.startswith('/api/'):
            self.handle_api_get(parsed_path.path)
        else:
            # Static files
            super().do_GET()
    
    def do_POST(self):
        """Obsługa POST requests"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path.startswith('/api/'):
            self.handle_api_post(parsed_path.path)
        else:
            self.send_error(404)
    
    def handle_api_get(self, path):
        """Obsługa API GET"""
        
        if path == '/api/status':
            self.api_status()
        
        elif path == '/api/config':
            self.api_get_config()
        
        elif path == '/api/prompt':
            self.api_get_prompt()
        
        elif path == '/api/logs':
            self.api_get_logs()
        
        else:
            self.send_error(404)
    
    def handle_api_post(self, path):
        """Obsługa API POST"""
        
        # Czytaj body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json_response({'error': 'Invalid JSON'}, 400)
            return
        
        if path == '/api/config':
            self.api_save_config(data)
        
        elif path == '/api/prompt':
            self.api_save_prompt(data)
        
        else:
            self.send_error(404)
    
    # === API METHODS ===
    
    def api_status(self):
        """Zwróć status agenta"""
        try:
            # Wczytaj config
            config = self.load_config()
            
            # Sprawdź Ollama (tylko jeśli requests dostępny)
            ollama_available = self.check_ollama(config) if REQUESTS_AVAILABLE else False
            
            # Wczytaj capabilities z pamięci projektu (jeśli istnieje)
            capabilities = self.load_capabilities()
            
            response = {
                'version': self.get_version(),
                'mode': 'project',  # TODO: wykryj tryb
                'chat_model': config.get('chat_model', 'unknown'),
                'embed_model': config.get('embed_model', 'unknown'),
                'ollama_host': config.get('ollama_host', '127.0.0.1'),
                'ollama_port': config.get('ollama_port', 11434),
                'ollama_available': ollama_available,
                'capabilities': capabilities
            }
            
            self.send_json_response(response)
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def api_get_config(self):
        """Zwróć konfigurację"""
        try:
            config = self.load_config()
            self.send_json_response({'config': config})
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def api_save_config(self, data):
        """
        Zapisz konfigurację z walidacją.
        
        POPRAWKI:
        - Walidacja składni JSON
        - Walidacja wymaganych pól
        - Walidacja typów
        - Fallback do domyślnych wartości
        """
        try:
            config = data.get('config', {})
            
            # Walidacja JSON
            if not isinstance(config, dict):
                self.send_json_response({'error': 'Config must be object'}, 400)
                return
            
            # Walidacja kluczowych pól
            required = ["nick", "ollama_host", "ollama_port", "chat_model", "embed_model"]
            missing = [k for k in required if k not in config or not config[k]]
            
            if missing:
                self.send_json_response({
                    'error': f'Missing required fields: {", ".join(missing)}',
                    'hint': 'Reinstall using: ~/.local/share/ai-cli-agent/install-cli.sh',
                    'required_fields': required
                }, 400)
                return
            
            # Walidacja typów
            if not isinstance(config.get('ollama_port'), int):
                try:
                    config['ollama_port'] = int(config['ollama_port'])
                except (ValueError, TypeError):
                    self.send_json_response({
                        'error': 'ollama_port must be integer',
                        'hint': 'Expected: 11434, got: ' + str(config.get('ollama_port'))
                    }, 400)
                    return
            
            # Merge z domyślnymi wartościami (deep merge)
            default_config = self.get_default_config()
            merged_config = self.deep_merge(default_config, config)
            
            # Zapisz
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(merged_config, f, indent=2)
            
            self.send_json_response({
                'success': True,
                'message': 'Configuration saved successfully'
            })
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def api_get_prompt(self):
        """Zwróć system prompt"""
        try:
            exists = PROMPT_FILE.exists()
            content = ""
            modified = None
            
            if exists:
                # Wczytaj i usuń komentarze
                full_content = PROMPT_FILE.read_text()
                lines = [
                    line for line in full_content.splitlines()
                    if line.strip() and not line.strip().startswith('#')
                ]
                content = '\n'.join(lines) if lines else ''
                
                modified_ts = PROMPT_FILE.stat().st_mtime
                from datetime import datetime
                modified = datetime.fromtimestamp(modified_ts).strftime('%Y-%m-%d %H:%M:%S')
            
            self.send_json_response({
                'exists': exists,
                'content': content,
                'full_content': PROMPT_FILE.read_text() if exists else '',  # Z komentarzami
                'modified': modified
            })
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def api_save_prompt(self, data):
        """Zapisz system prompt"""
        try:
            content = data.get('content', '')
            
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            if content:
                PROMPT_FILE.write_text(content)
            else:
                # Wyczyść (usuń plik)
                if PROMPT_FILE.exists():
                    PROMPT_FILE.unlink()
            
            self.send_json_response({'success': True})
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def api_get_logs(self):
        """Zwróć ostatnie logi diagnostyczne"""
        try:
            cache_dir = Path.home() / ".cache" / "ai-cli" / "logs"
            
            if not cache_dir.exists():
                self.send_json_response({'logs': 'Brak logów'})
                return
            
            # Wczytaj ostatnie 100 linii z debug.log
            debug_log = cache_dir / "debug.log"
            
            if not debug_log.exists():
                self.send_json_response({'logs': 'Brak pliku debug.log'})
                return
            
            # Ogon pliku (ostatnie 100 linii)
            with open(debug_log, 'r') as f:
                lines = f.readlines()
                last_lines = lines[-100:]
            
            self.send_json_response({
                'logs': ''.join(last_lines),
                'total_lines': len(lines),
                'file_size_kb': round(debug_log.stat().st_size / 1024, 2)
            })
        
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    # === HELPERS ===
    
    def load_config(self):
        """Wczytaj config.json"""
        if not CONFIG_FILE.exists():
            return self.get_default_config()
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Fallback do domyślnego
            return self.get_default_config()
    
    def get_default_config(self):
        """Zwróć domyślną konfigurację"""
        return {
            "nick": "user",
            "ollama_host": "127.0.0.1",
            "ollama_port": 11434,
            "chat_model": "qwen3-coder:480b-cloud",
            "embed_model": "nomic-embed-text-v2-moe:latest",
            "behavior": {},
            "semantic": {},
            "ui": {},
            "execution": {},
            "project": {},
            "debug": {}
        }
    
    def deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge dwóch dict"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def check_ollama(self, config):
        """Sprawdź czy Ollama jest dostępna"""
        if not REQUESTS_AVAILABLE:
            return False  # Nie można sprawdzić bez requests
        
        try:
            host = config.get('ollama_host', '127.0.0.1')
            port = config.get('ollama_port', 11434)
            url = f"http://{host}:{port}/api/tags"
            
            response = requests.get(url, timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def load_capabilities(self):
        """Wczytaj capabilities z .ai-context.json"""
        # Szukaj w cwd
        context_file = Path.cwd() / ".ai-context.json"
        
        if not context_file.exists():
            # Default capabilities
            return {
                'allow_execute': True,
                'allow_delete': True,
                'allow_git': False,
                'allow_network': False
            }
        
        try:
            with open(context_file, 'r') as f:
                data = json.load(f)
                return data.get('capabilities', {})
        except Exception:
            return {}
    
    def get_version(self):
        """Pobierz wersję z main.py"""
        try:
            # Szukaj main.py w instalacji
            install_dir = Path.home() / ".local" / "share" / "ai-cli-agent"
            main_file = install_dir / "main.py"
            
            if main_file.exists():
                content = main_file.read_text()
                import re
                match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        
        return 'unknown'
    
    def send_json_response(self, data, status=200):
        """Wyślij JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(json_data.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Przesłoń domyślne logowanie (mniej verbose)"""
        pass


def main():
    """Uruchom serwer panelu"""
    
    # Ostrzeżenie jeśli brak requests
    if not REQUESTS_AVAILABLE:
        print("⚠ Biblioteka 'requests' nie jest zainstalowana - status Ollama będzie niedostępny")
        print("  Zainstaluj: pip install requests --break-system-packages")
        print()
    
    try:
        with socketserver.TCPServer((HOST, PORT), PanelHandler) as httpd:
            print(f"╔══════════════════════════════════════════════════════════════╗")
            print(f"║           AI CLI Agent - Panel Administracyjny               ║")
            print(f"╚══════════════════════════════════════════════════════════════╝")
            print()
            print(f"  URL:  http://{HOST}:{PORT}")
            print(f"  Host: {HOST} (localhost only)")
            print(f"  Port: {PORT}")
            print()
            print(f"  ⚠ Panel NIE wykonuje poleceń")
            print(f"  ⚠ CLI pozostaje jedynym interfejsem wykonawczym")
            print()
            print(f"  Naciśnij Ctrl+C aby zatrzymać serwer")
            print()
            
            httpd.serve_forever()
    
    except KeyboardInterrupt:
        print("\n\nZatrzymano serwer panelu")
        sys.exit(0)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"✗ Port {PORT} jest już zajęty")
            print(f"  Sprawdź czy serwer już działa lub zmień port w server.py")
        else:
            print(f"✗ Błąd: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()