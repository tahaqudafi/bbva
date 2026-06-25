"""Local knowledge base: load TXT, DOCX, PDF and search by keyword scoring."""

import logging
import math
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf"}


def _load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_docx(path: Path) -> str:
    try:
        import docx  # python-docx

        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.warning(f"Could not read DOCX {path.name}: {e}")
        return ""


def _load_pdf(path: Path) -> str:
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except Exception as e:
        logger.warning(f"Could not read PDF {path.name}: {e}")
        return ""


_STOPWORDS = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
    "and", "or", "are", "was", "be", "this", "that", "with", "from", "by",
    "as", "do", "did", "can", "will", "how", "what", "when", "where",
    "who", "why", "not", "we", "i", "you", "my", "our", "your",
}


class KnowledgeBase:
    def __init__(self, knowledge_dir: Path):
        self.knowledge_dir = knowledge_dir
        self._documents: list[dict] = []

    def load(self) -> None:
        """Scan knowledge_dir and load all supported files into memory."""
        if not self.knowledge_dir.exists():
            self.knowledge_dir.mkdir(parents=True)
            logger.warning(f"Created empty knowledge directory: {self.knowledge_dir}")

        files = sorted(
            f
            for f in self.knowledge_dir.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        if not files:
            logger.warning(
                "Knowledge folder is empty — customer support answers will not be available."
            )
            return

        for path in files:
            text = self._read_file(path)
            if text.strip():
                chunks = self._chunk(text)
                self._documents.append(
                    {"name": path.name, "text": text, "chunks": chunks}
                )
                logger.info(f"Loaded: {path.name} ({len(text):,} chars, {len(chunks)} chunks)")
            else:
                logger.warning(f"No text extracted from: {path.name}")

    def _read_file(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".txt":
            return _load_txt(path)
        if ext == ".docx":
            return _load_docx(path)
        if ext == ".pdf":
            return _load_pdf(path)
        return ""

    def _chunk(self, text: str, max_chars: int = 600) -> list[str]:
        """Split text on double newlines; merge short paragraphs into chunks."""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            if current_len + len(para) > max_chars and current:
                chunks.append("\n\n".join(current))
                current = current[-1:]
                current_len = len(current[0])
            current.append(para)
            current_len += len(para)

        if current:
            chunks.append("\n\n".join(current))

        return chunks or [text[:max_chars]]

    def search(self, query: str, top_k: int = 3) -> str | None:
        """
        Keyword-based search across all loaded chunks.
        Returns the top matching excerpts, or None if nothing is loaded.
        """
        if not self._documents:
            return None

        query_terms = self._tokenize(query)
        if not query_terms:
            return None

        scored: list[tuple[float, str, str]] = []
        for doc in self._documents:
            for chunk in doc["chunks"]:
                score = self._score(chunk, query_terms)
                if score > 0:
                    scored.append((score, chunk, doc["name"]))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        parts = [f"[Source: {name}]\n{chunk}" for _, chunk, name in top]
        return "\n\n---\n\n".join(parts)

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
        return [t for t in tokens if t not in _STOPWORDS]

    def _score(self, chunk: str, query_terms: list[str]) -> float:
        lower = chunk.lower()
        chunk_tokens = self._tokenize(chunk)
        denom = len(chunk_tokens) or 1
        score = 0.0
        for term in query_terms:
            count = lower.count(term)
            if count:
                score += (count / denom) * (1 + math.log(count))
        return score

    @property
    def is_empty(self) -> bool:
        return len(self._documents) == 0

    @property
    def loaded_files(self) -> list[str]:
        return [d["name"] for d in self._documents]
