import os
import json
import requests
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "ai"
CONFIG_FILE = CONFIG_DIR / "config.json"

def get_default_config():
    return {
        "nick": "user",
        "ollama_host": "127.0.0.1",
        "ollama_port": 11434,
        "chat_model": "qwen3-coder:480b-cloud",
        "embed_model": "nomic-embed-text-v2-moe:latest",
        
        "behavior": {
            "default_confirm": True,
            "max_actions_per_run": 10,
            "prefer_read_before_edit": True,
            "allow_multi_step_reasoning": True
        },
        
        "semantic": {
            "enabled": True,
            "max_files": 50,
            "max_file_size_kb": 100,
            "cache_embeddings": True,
            "prefer_frequently_edited": True,
            "boost_paths": ["src/", "app/", "lib/"]
        },
        
        "ui": {
            "spinner": True,
            "show_diff_preview": True,
            "color_output": True,
            "show_action_summary": True,
            "silent_safe_actions": False
        },
        
        "execution": {
            "auto_confirm_safe": True,
            "auto_confirm_safe_commands": True,
            "auto_confirm_modify_under": 3,
            "timeout_seconds": 120,
            "shell": "/bin/bash"
        },
        
        "project": {
            "auto_analyze_on_start": True,
            "auto_analyze_on_change": True,
            "remember_intents": True,
            "max_history": 20
        },
        
        "debug": {
            "log_level": "info",
            "log_semantic_queries": False,
            "log_model_raw_output": False,
            "save_failed_responses": True
        },

        "rag": {
            "enabled": True,          # Włącz/wyłącz RAG
            "top_k": 4,               # Ile fragmentów wiedzy dołączyć do promptu
            "min_score": 0.1,         # Minimalne podobieństwo (0.0–1.0)
            "embed_model": ""         # Zostaw puste = użyj embed_model z głównej sekcji
        },

        # Smart routing i fallback (ustawiane przez `ai model`)
        # "fallback_model": "",       # Model przy HTTP 429 / timeout
        # "coder_model": "",          # Model dla zadań kodowania
        # "vision_model": "",         # Model dla zadań z obrazami (VL)


        "web_search": {
            "enabled": False,              # Domyślnie OFF (bezpieczeństwo)
            "engine": "duckduckgo",        # "duckduckgo" | "brave" | "google"
            "max_results": 5,
            "cache_ttl_hours": 1,
            "allowed_domains": [           # Whitelist zaufanych domen
                "pypi.org",
                "npmjs.com",
                "github.com",
                "stackoverflow.com",
                "docs.python.org",
                "developer.mozilla.org",
                "wikipedia.org",
                "readthedocs.io",
                "crates.io",
                "packagist.org",
                "rubygems.org",
                "pkg.go.dev"
            ],
            "require_confirmation": True,  # Pytaj przed przeszukaniem nieznanych domen
            "brave_api_key": "",           # Tylko dla engine="brave"
            "auto_trigger": True           # Auto-wykrywaj frazy wyzwalające
        }
    }

def validate_and_repair_config(config: dict) -> tuple:
    """
    Waliduj i napraw config.
    
    Returns:
        (repaired_config, list_of_repairs)
    """
    repairs = []
    default = get_default_config()
    
    # Sprawdź czy to dict
    if not isinstance(config, dict):
        repairs.append("Config nie jest obiektem JSON - odtworzono domyślny")
        return default, repairs
    
    # Sprawdź kluczowe pola
    required_keys = ["nick", "ollama_host", "ollama_port", "chat_model", "embed_model"]
    
    for key in required_keys:
        if key not in config or not config[key]:
            config[key] = default[key]
            repairs.append(f"Odtworzono brakujące pole: {key}")
    
    # Deep merge dla zagnieżdżonych dict
    for key, value in default.items():
        if isinstance(value, dict):
            if key not in config:
                config[key] = value
                repairs.append(f"Odtworzono brakującą sekcję: {key}")
            else:
                # Merge subkeys
                for subkey, subvalue in value.items():
                    if subkey not in config[key]:
                        config[key][subkey] = subvalue
                        repairs.append(f"Odtworzono {key}.{subkey}")
    
    # Walidacja typów
    if not isinstance(config.get("ollama_port"), int):
        try:
            config["ollama_port"] = int(config["ollama_port"])
        except (ValueError, TypeError):
            config["ollama_port"] = default["ollama_port"]
            repairs.append("Naprawiono typ ollama_port")

    # Migracja timeout: lokalne modele potrzebują >= 120s
    current_timeout = config.get("execution", {}).get("timeout_seconds", 30)
    if isinstance(current_timeout, int) and current_timeout < 120:
        config.setdefault("execution", {})["timeout_seconds"] = 120
        repairs.append(f"Zwiększono timeout {current_timeout}s → 120s (lokalne modele wymagają więcej czasu)")

    return config, repairs

def load_config():
    """
    Wczytaj konfigurację z walidacją i fallbackiem.
    
    POPRAWKI:
    - Walidacja składni JSON
    - Fallback do domyślnych wartości
    - Jawne komunikaty o błędach
    """
    if not CONFIG_FILE.exists():
        print(f"[INFO] Brak pliku konfiguracji: {CONFIG_FILE}")
        print(f"[INFO] Tworzę nową konfigurację...")
        return setup_wizard()
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        # POPRAWKA: Jawny komunikat o błędzie JSON
        print(f"[BŁĄD] Uszkodzony plik konfiguracji (błąd JSON): {e}")
        print(f"[INFO] Lokalizacja: {CONFIG_FILE}")
        print(f"[INFO] Linia {e.lineno}, kolumna {e.colno}: {e.msg}")
        print()
        print(f"[INFO] Aby naprawić:")
        print(f"  1. Edytuj plik: nano {CONFIG_FILE}")
        print(f"  2. Lub usuń i utwórz nowy: rm {CONFIG_FILE} && ai config")
        print(f"  3. Lub uruchom ponownie instalator:")
        print(f"     ~/.local/share/ai-cli-agent/install-cli.sh")
        print()
        
        # FALLBACK: Użyj domyślnej konfiguracji
        print(f"[INFO] Używam DOMYŚLNEJ konfiguracji (tymczasowo)")
        print(f"[INFO] Napraw plik konfiguracji aby zachować ustawienia")
        print()
        
        return get_default_config()
    
    # Walidacja i naprawa
    config, repairs = validate_and_repair_config(config)
    
    if repairs:
        print("[INFO] Naprawiono konfigurację:")
        for repair in repairs:
            print(f"  • {repair}")
        print()
        print("[INFO] Rozważ ponowną instalację dla pełnej konfiguracji:")
        print("  ~/.local/share/ai-cli-agent/install-cli.sh")
        print()
        save_config(config)
    
    return config

def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def setup_wizard():
    print("--- Kreator konfiguracji AI CLI ---")
    config = get_default_config()
    
    try:
        config['nick'] = input(f"Podaj nick [{config['nick']}]: ") or config['nick']
        config['ollama_host'] = input(f"IP Ollamy [{config['ollama_host']}]: ") or config['ollama_host']
        config['ollama_port'] = int(input(f"Port Ollamy [{config['ollama_port']}]: ") or config['ollama_port'])
    except (KeyboardInterrupt, EOFError):
        print()
        print("Anulowano kreator konfiguracji.")
        return config
    
    base_url = f"http://{config['ollama_host']}:{config['ollama_port']}"
    try:
        resp = requests.get(f"{base_url}/api/tags")
        models = [m['name'] for m in resp.json().get('models', [])]
        
        print("\nDostępne modele:")
        for i, m in enumerate(models):
            print(f"{i}. {m}")
        
        c_idx = int(input("Wybierz model główny (indeks): "))
        config['chat_model'] = models[c_idx]
        
        e_idx = int(input("Wybierz model embeddingów (indeks): "))
        config['embed_model'] = models[e_idx]
        
    except Exception as e:
        print(f"Błąd połączenia z Ollamą: {e}")
        print("Zapisuję domyślne wartości...")

    save_config(config)
    return config