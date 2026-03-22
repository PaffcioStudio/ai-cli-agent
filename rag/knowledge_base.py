"""
RAG – Knowledge Base dla AI CLI Agent.

Indeksuje pliki .md i .txt z katalogu knowledge/ i udostępnia
wyszukiwanie semantyczne jako kontekst dla agenta.

Katalog wiedzy: <project_root>/knowledge/  lub  ~/.config/ai/knowledge/
Baza wektorowa: ~/.cache/ai/rag/knowledge_vectors.*
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import requests


# ─── Ścieżki ──────────────────────────────────────────────────────────────────

GLOBAL_KNOWLEDGE_DIR = Path.home() / ".config" / "ai" / "knowledge"
CACHE_DIR             = Path.home() / ".cache"  / "ai" / "rag"
DB_PATH               = str(CACHE_DIR / "knowledge_vectors")


# ─── Modele danych ────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    file_path: str
    chunk_id: int
    text: str


@dataclass
class SearchResult:
    file_path: str
    chunk_id: int
    text: str
    score: float


# ─── Chunker ──────────────────────────────────────────────────────────────────

class KnowledgeChunker:
    """Dzieli pliki tekstowe na fragmenty do indeksowania."""

    def __init__(self, chunk_size: int = 800, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap    = overlap

    def chunk_text(self, text: str, file_path: str) -> list[Chunk]:
        """Podziel tekst na chunki z nakładaniem."""
        # Normalizuj białe znaki
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if not text:
            return []

        chunks: list[Chunk] = []
        start = 0
        chunk_id = 0

        while start < len(text):
            end = start + self.chunk_size

            # Przesuwaj koniec do granicy zdania/linii
            if end < len(text):
                # Szukaj ostatniego \n lub . przed end
                boundary = max(
                    text.rfind('\n', start, end),
                    text.rfind('. ', start, end),
                )
                if boundary > start + self.chunk_size // 2:
                    end = boundary + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    file_path=file_path,
                    chunk_id=chunk_id,
                    text=chunk_text,
                ))
                chunk_id += 1

            start = max(start + 1, end - self.overlap)

        return chunks

    def chunk_files(self, knowledge_dir: Path) -> list[Chunk]:
        """Znajdź i podziel wszystkie pliki .md i .txt."""
        all_chunks: list[Chunk] = []

        for ext in ("*.md", "*.txt"):
            for path in sorted(knowledge_dir.rglob(ext)):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    rel  = str(path.relative_to(knowledge_dir))
                    chunks = self.chunk_text(text, rel)
                    all_chunks.extend(chunks)
                except Exception as e:
                    print(f"  [WARN] Nie można odczytać {path}: {e}")

        return all_chunks


# ─── Baza wektorowa ───────────────────────────────────────────────────────────

class VectorDB:
    """Prosta baza wektorowa – numpy + JSON."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path    = db_path
        self.embeddings: np.ndarray | list = []
        self.metadatas: list[dict]          = []

    def add(self, embedding: list[float], metadata: dict):
        self.embeddings.append(embedding)
        self.metadatas.append(metadata)

    def save(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        arr = np.array(self.embeddings, dtype=np.float32)
        np.save(self.db_path + ".npy", arr)
        with open(self.db_path + ".json", "w", encoding="utf-8") as f:
            json.dump(self.metadatas, f, ensure_ascii=False, indent=2)

    def load(self) -> bool:
        npy  = self.db_path + ".npy"
        meta = self.db_path + ".json"
        if not (Path(npy).exists() and Path(meta).exists()):
            return False
        self.embeddings = np.load(npy).astype(np.float32)
        with open(meta, encoding="utf-8") as f:
            self.metadatas = json.load(f)
        return True

    @property
    def size(self) -> int:
        if isinstance(self.embeddings, np.ndarray):
            return self.embeddings.shape[0]
        return len(self.embeddings)

    def search(self, query_emb: list[float], top_k: int = 5) -> list[SearchResult]:
        if self.size == 0:
            return []

        arr = (
            self.embeddings
            if isinstance(self.embeddings, np.ndarray)
            else np.array(self.embeddings, dtype=np.float32)
        )

        qv  = np.array(query_emb, dtype=np.float32)
        # Cosine similarity
        norms = np.linalg.norm(arr, axis=1) * np.linalg.norm(qv) + 1e-8
        sims  = arr @ qv / norms

        top_k  = min(top_k, self.size)
        top_idx = np.argsort(sims)[::-1][:top_k]

        results: list[SearchResult] = []
        for i in top_idx:
            m = self.metadatas[i]
            results.append(SearchResult(
                file_path=m["file"],
                chunk_id=m["chunk_id"],
                text=m["text"],
                score=float(sims[i]),
            ))
        return results


# ─── Klient embedów (bezpośredni do Ollamy) ───────────────────────────────────

def _embed_text(text: str, base_url: str, embed_model: str) -> list[float]:
    """Generuj embedding przez Ollama API."""
    r = requests.post(
        f"{base_url}/api/embed",
        json={"model": embed_model, "input": text},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["embeddings"][0]


# ─── Główna klasa RAG ────────────────────────────────────────────────────────

class KnowledgeBase:
    """
    Baza wiedzy RAG dla AI CLI Agent.

    Użycie:
        kb = KnowledgeBase(config)
        kb.load()                          # załaduj z cache

        # Indeksowanie (raz lub po zmianach)
        kb.index(knowledge_dir)

        # Wyszukiwanie
        results = kb.search("jak zatrzymać usługę systemd?", top_k=4)
        context = kb.format_context(results)
    """

    def __init__(self, config: dict):
        self.config      = config
        self.base_url    = f"http://{config['ollama_host']}:{config['ollama_port']}"
        self.embed_model = config.get("embed_model", "nomic-embed-text")
        self.db          = VectorDB(DB_PATH)
        self._loaded     = False

        # Używaj modelu embeddingów z sekcji RAG jeśli zdefiniowany
        rag_cfg = config.get("rag", {})
        if rag_cfg.get("embed_model"):
            self.embed_model = rag_cfg["embed_model"]

    # ── Ładowanie ────────────────────────────────────────────────────────────

    def load(self) -> bool:
        """Załaduj bazę z cache. Zwraca True jeśli załadowano."""
        if self.db.load():
            self._loaded = True
            return True
        return False

    @property
    def is_ready(self) -> bool:
        return self._loaded and self.db.size > 0

    @property
    def chunk_count(self) -> int:
        return self.db.size

    # ── Indeksowanie ─────────────────────────────────────────────────────────

    def index(self, knowledge_dir: Path, verbose: bool = True) -> int:
        """
        Zaindeksuj wszystkie pliki z knowledge_dir.
        Zawsze buduje bazę od nowa (czyści stary cache przed indeksowaniem).
        Zwraca liczbę zaindeksowanych chunków.
        """
        import os
        if not knowledge_dir.exists():
            raise FileNotFoundError(f"Katalog wiedzy nie istnieje: {knowledge_dir}")

        chunker = KnowledgeChunker()
        chunks  = chunker.chunk_files(knowledge_dir)

        if not chunks:
            return 0

        if verbose:
            print(f"  Znaleziono {len(chunks)} chunków w {knowledge_dir}")

        # Wyczyść stary cache przed indeksowaniem (zawsze buduj od nowa)
        for ext in (".npy", ".json"):
            old_file = DB_PATH + ext
            if os.path.exists(old_file):
                os.remove(old_file)
                if verbose:
                    print(f"  Wyczyszczono stary cache: {old_file}")

        # Generuj embeddingi
        db = VectorDB(DB_PATH)
        errors = 0

        for i, chunk in enumerate(chunks):
            if verbose:
                # Prosty progress bar
                pct   = int((i + 1) / len(chunks) * 30)
                bar   = "█" * pct + "░" * (30 - pct)
                print(f"\r  [{bar}] {i+1}/{len(chunks)}  {chunk.file_path[:40]:<40}", end="", flush=True)
            try:
                emb = _embed_text(chunk.text, self.base_url, self.embed_model)
                db.add(emb, {
                    "file":     chunk.file_path,
                    "chunk_id": chunk.chunk_id,
                    "text":     chunk.text,
                })
            except Exception as e:
                errors += 1
                if verbose:
                    print(f"\n  [WARN] Błąd embeddingu {chunk.file_path}#{chunk.chunk_id}: {e}")

        if verbose:
            print()  # newline po progress bar

        db.save()

        # Przeładuj bieżącą instancję
        self.db      = db
        self._loaded = True

        return len(chunks) - errors

    # ── Wyszukiwanie ──────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 4, min_score: float = 0.1,
               max_per_file: int = 2) -> list[SearchResult]:
        """
        Wyszukaj najlepiej pasujące fragmenty wiedzy.

        Args:
            query:        zapytanie użytkownika
            top_k:        ile fragmentów zwrócić łącznie
            min_score:    minimalne podobieństwo (0.0–1.0)
            max_per_file: maks. fragmentów z jednego pliku (zapobiega dominacji jednego pliku)
        """
        if not self.is_ready:
            return []

        try:
            qv = _embed_text(query, self.base_url, self.embed_model)
        except Exception:
            return []

        # Pobierz więcej kandydatów żeby po deduplikacji zostało top_k
        candidates = self.db.search(qv, top_k=top_k * 4)
        filtered = [r for r in candidates if r.score >= min_score]

        # Deduplikacja: maks. max_per_file fragmentów z tego samego pliku
        file_counts: dict[str, int] = {}
        results = []
        for r in filtered:
            count = file_counts.get(r.file_path, 0)
            if count < max_per_file:
                results.append(r)
                file_counts[r.file_path] = count + 1
            if len(results) >= top_k:
                break

        return results

    # ── Formatowanie kontekstu dla promptu ───────────────────────────────────

    def format_context(self, results: list[SearchResult], max_chars: int = 4000) -> str:
        """
        Sformatuj wyniki wyszukiwania jako blok kontekstu do wstrzyknięcia w prompt.
        """
        if not results:
            return ""

        parts: list[str] = []
        total = 0

        for r in results:
            header = f"[{r.file_path}]"
            block  = f"{header}\n{r.text}"
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)

        return "\n\n---\n\n".join(parts)

    # ── Informacje ────────────────────────────────────────────────────────────

    def get_info(self) -> dict:
        """Zwróć informacje o bazie wiedzy."""
        return {
            "loaded":      self._loaded,
            "chunks":      self.db.size,
            "db_path":     DB_PATH,
            "embed_model": self.embed_model,
        }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def find_knowledge_dir(project_root: Optional[Path] = None) -> Optional[Path]:
    """
    Znajdź katalog knowledge/ w kolejności:
    1. <project_root>/knowledge/
    2. ~/.config/ai/knowledge/
    3. ~/.local/share/ai-cli-agent/knowledge/
    """
    if project_root:
        local = project_root / "knowledge"
        if local.exists():
            return local

    if GLOBAL_KNOWLEDGE_DIR.exists():
        return GLOBAL_KNOWLEDGE_DIR

    # Fallback: katalog instalacyjny agenta
    agent_knowledge = Path.home() / ".local" / "share" / "ai-cli-agent" / "knowledge"
    if agent_knowledge.exists():
        return agent_knowledge

    return None


def build_rag_context_section(results: list[SearchResult], kb: KnowledgeBase) -> str:
    """
    Zbuduj sekcję RAG do wstrzyknięcia w system prompt agenta.
    """
    if not results:
        return ""

    context = kb.format_context(results)
    if not context:
        return ""

    sources = sorted(set(r.file_path for r in results))
    sources_str = ", ".join(sources)

    return f"""
====================
WIEDZA Z BAZY (RAG)
====================

Poniższe fragmenty zostały automatycznie wyszukane z lokalnej bazy wiedzy.
Użyj ich jako kontekstu do odpowiedzi. Źródła: {sources_str}

{context}

====================
KONIEC WIEDZY Z BAZY
====================
"""
