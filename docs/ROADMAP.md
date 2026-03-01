# AI CLI Agent — Roadmap

**Aktualna wersja:** `1.4.6`  
**Cel:** `2.0.0` (Production Ready)

---

## Legenda

- 🔴 **CRITICAL** — bloker, pilne
- 🟠 **HIGH** — ważne, następny release
- 🟡 **MEDIUM** — przydatne, można odłożyć
- 🟢 **LOW** — miłe w posiadaniu
- 🔵 **FUTURE** — pomysły na v2.0+

---

## ✅ v1.2.x → v1.3.0 — UKOŃCZONO

Web Search, Transaction Manager, Intent/Command Classification, stabilność.

Ukończone: HTTP 429 + retry/backoff, Transaction Manager z rollbackiem, Web Search (DuckDuckGo/Brave, cache, whitelist, rate limit), Intent Classifier, Command Classifier, walidacja config, nowoczesny panel webowy.

---

## ✅ v1.3.x → v1.4.0 — UKOŃCZONO

Global Memory, poprawki zachowania agenta.

Ukończone: Global Memory (`~/.config/ai/memory.json`), `ai memory` CLI, early intercept "zapamiętaj że...", warstwowy PromptBuilder, poprawka "nie pytaj o potwierdzenie" przy jasnym poleceniu.

---

## 🚀 v1.4.x → v1.5.0

**Priorytet:** Model Fallback + Smart Package Management

### 🟠 Model Fallback

Auto-przełączanie modelu przy HTTP 429 / timeout:

```json
{
  "models": {
    "primary": "qwen3-coder:480b-cloud",
    "fallback": ["qwen2.5-coder:7b", "deepseek-coder:6.7b"],
    "auto_fallback": { "on_http_429": true, "on_timeout": true },
    "auto_revert": true
  }
}
```

- [ ] Fallback logic (primary → fallback[0] → fallback[1] → error)
- [ ] `ai model install <model>` z progress barem i sprawdzeniem RAM
- [ ] `ai model benchmark <model>`
- [ ] Rekomendacje modeli wg sprzętu

### 🟠 Smart Package Management

- [ ] `ai check dependencies` — aktualne wersje, luki bezpieczeństwa
- [ ] `ai update dependencies` — update requirements.txt
- [ ] Detekcja brakujących importów w kodzie
- [ ] Obsługa: pip/poetry, npm/yarn, cargo, go.mod

### 🟡 Quality of Life

- [ ] WebSocket w panelu (live logs)
- [ ] Auto-cleanup embeddings cache >7 dni
- [ ] Bash completion

---

## 🚀 v1.5.x → v1.6.0

**Priorytet:** Integracje — Home Assistant + Minecraft

### 🟠 Home Assistant

```bash
ai włącz światło w sypialni
ai ustaw termostat na 22 stopnie
ai wyłącz wszystkie światła
```

- [ ] Setup wizard (`ai ha setup`), discovery, entity cache
- [ ] HA API wrapper, natural language → API calls
- [ ] Confirmations dla krytycznych akcji (zamki, alarm)

### 🟠 Minecraft Server Manager

```bash
ai minecraft setup / start / stop / status
ai zmień max graczy na 10
ai minecraft plugin install EssentialsX
ai minecraft backup create
```

- [ ] Instalacja serwera (Paper/Vanilla/Spigot/Forge)
- [ ] Kontrola via tmux, natural language config
- [ ] Plugin management, backup system

---

## 🚀 v1.6.x → v1.7.0

**Priorytet:** Plugin System

```
~/.config/ai/plugins/
├── my-plugin/
│   ├── plugin.json
│   ├── actions.py
│   └── requirements.txt
```

- [ ] Plugin loader + registry
- [ ] `ai plugin list/install/enable/disable/create`
- [ ] Capability checking, hook system (before/after execute)
- [ ] Izolacja zależności

---

## 🚀 v1.7.x → v1.8.0

**Priorytet:** Workflows + Templates + AI Code Review

- [ ] `ai workflow create/run` — multi-step pipelines
- [ ] `ai template use <name> <dest>` — rozbudowany template system
- [ ] `ai review <plik>` — issues, score, auto-fixes

---

## 🚀 v1.8.x → v2.0.0

**Priorytet:** Production Ready

- [ ] Testy automatyczne >80% coverage + CI/CD
- [ ] Security audit (sandboxing, path traversal, key encryption)
- [ ] Pełna dokumentacja (user guide, API docs, FAQ, video)
- [ ] i18n (EN/PL/DE)
- [ ] Team features (shared knowledge base, role-based capabilities)

---

## 🔵 Future (Post v2.0)

Multi-agent system, voice interface (Whisper + TTS), fine-tuning na własnej codebase, mobile app, cloud sync konfiguracji (E2E encrypted), GUI (Electron/Tauri).

---

**Ostatnia aktualizacja:** 2026-02-28 | **Maintainer:** Paffcio
