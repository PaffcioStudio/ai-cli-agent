"""
model_catalog.py – detekcja sprzętu, katalog modeli i stałe routingu.

Wydzielony z model_manager.py (refaktoryzacja: > 1100 linii).
"""
from __future__ import annotations

import re
import subprocess


# ─── Detekcja sprzętu ────────────────────────────────────────────────────────

def get_system_ram_gb() -> float:
    """Zwraca całkowity RAM systemu w GB."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb / 1024 / 1024
    except Exception:
        pass
    try:
        import psutil
        return psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        return 0.0


def get_gpu_vram_gb() -> float:
    """Zwraca VRAM GPU w GB (0 jeśli brak / błąd)."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL, text=True, timeout=3
        )
        mb = int(out.strip().splitlines()[0])
        return mb / 1024
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showmeminfo", "vram"], stderr=subprocess.DEVNULL, text=True, timeout=3
        )
        for line in out.splitlines():
            if "Total Memory" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.isdigit():
                        return int(p) / 1024 / 1024
    except Exception:
        pass
    return 0.0


# ─── Baza rekomendacji modeli ─────────────────────────────────────────────────

# Format: (min_ram_gb, min_vram_gb, name, opis, tagi)
_MODEL_CATALOG: list[tuple[float, float, str, str, list[str]]] = [
    (4,  0,  "qwen2.5:0.5b",          "Ultra-lekki, 0.5B parametrów",          ["chat", "szybki"]),
    (4,  0,  "qwen2.5:1.5b",          "Bardzo lekki, 1.5B parametrów",         ["chat", "szybki"]),
    (6,  0,  "qwen2.5:3b",            "Lekki model ogólny, 3B",                 ["chat"]),
    (8,  0,  "llama3.2:3b",           "Meta Llama 3.2 3B, szybki",             ["chat"]),
    (8,  4,  "qwen2.5-coder:7b",      "Coder 7B – dobry do kodu",              ["coder", "szybki"]),
    (8,  4,  "deepseek-coder:6.7b",   "DeepSeek Coder 6.7B",                   ["coder"]),
    (12, 6,  "qwen2.5:7b",            "Ogólny 7B – balans jakości/szybkości",  ["chat"]),
    (12, 6,  "llama3.1:8b",           "Meta Llama 3.1 8B",                     ["chat"]),
    (16, 8,  "qwen2.5-coder:14b",     "Coder 14B – mocny do kodu",             ["coder"]),
    (16, 8,  "qwen3-vl:8b",           "Vision 8B – obrazy i tekst",            ["vision"]),
    (24, 10, "qwen2.5:14b",           "14B – wysoka jakość ogólna",            ["chat"]),
    (24, 10, "deepseek-r1:14b",       "DeepSeek R1 14B – reasoning",           ["chat", "reasoning"]),
    (32, 16, "qwen2.5:32b",           "32B – bardzo wysoka jakość",            ["chat"]),
    (32, 16, "deepseek-r1:32b",       "DeepSeek R1 32B – zaawansowany reasoning", ["chat", "reasoning"]),
    (48, 24, "qwen2.5:72b",           "72B – flagship lokalny",                ["chat"]),
    (64, 48, "qwen3-coder:480b-cloud","480B cloud – najsilniejszy coder",      ["coder", "cloud"]),
]


def get_model_recommendations(ram_gb: float, vram_gb: float) -> list[dict]:
    """Zwraca listę rekomendowanych modeli wg dostępnego sprzętu."""
    recs = []
    for min_ram, min_vram, name, desc, tags in _MODEL_CATALOG:
        fits_ram  = ram_gb  >= min_ram
        fits_vram = vram_gb >= min_vram or min_vram == 0
        if fits_ram and fits_vram:
            recs.append({
                "name":     name,
                "desc":     desc,
                "tags":     tags,
                "min_ram":  min_ram,
                "min_vram": min_vram,
            })
    return recs


# ─── Stałe routingu ──────────────────────────────────────────────────────────

_CODE_PATTERNS = re.compile(
    r"\b(napisz|stwórz|utwórz|zrefaktoruj|zoptymalizuj|"
    r"debug|przetestuj|funkcj[aę]|klas[aę]|metod[aę]|"
    r"napisz.*skrypt|napisz.*kod|nowy.*skrypt|nowy.*kod|"
    r"python script|javascript|typescript|rust code|bash script|"
    r"def |class |import |return )\b",
    re.IGNORECASE,
)

_VISION_PATTERNS = re.compile(
    r"\b(obraz|obrazek|zdjęcie|zdjęcia|foto|fotografia|screenshot|screen|"
    r"obrazu|zdjęcia|plik png|plik jpg|plik jpeg|plik webp|plik gif|"
    r"opisz|przeanalizuj|co widać|co jest na|rozpoznaj|odczytaj z|"
    r"image|picture|photo|vision|visual|\.png|\.jpg|\.jpeg|\.webp|\.gif|\.bmp)\b",
    re.IGNORECASE,
)

_CODER_HINTS  = ["coder", "code", "starcoder", "codellama", "deepseek-coder", "qwen2.5-coder"]
_EMBED_HINTS  = ["embed", "embedding", "bge", "minilm", "e5-"]
_VISION_HINTS = ["vl", "vision", "visual", "llava", "minicpm", "qwen3-vl", "qwen2-vl", "bakllava", "moondream", "image"]
_CLOUD_SUFFIX = ":cloud"

_CUSTOM_NAMESPACE_RE = re.compile(r"^[a-zA-Z0-9_.-]+/")


def estimate_model_ram(model_name: str) -> float:
    """Szacuje wymagany RAM w GB na podstawie nazwy modelu (heurystyka)."""
    name = model_name.lower()
    m = re.search(r":?(\d+(\.\d+)?)\s*b\b", name)
    if m:
        params = float(m.group(1))
        if "q4" in name or "4bit" in name:
            return params * 0.6
        if "q8" in name or "8bit" in name:
            return params * 1.1
        return params * 0.65
    if "480b" in name:
        return 0  # cloud
    return 0.0
