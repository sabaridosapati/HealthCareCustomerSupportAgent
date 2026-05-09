from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import chromadb
from chromadb.utils import embedding_functions

from .config import settings


@dataclass
class RetrievedDoc:
    doc_id: str
    text: str
    source: str


class KnowledgeBase:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self.embedder = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="acmecloud_kb",
            embedding_function=self.embedder,
        )

    def ingest_directory(self, kb_dir: Path) -> int:
        files = list(kb_dir.glob("*.txt")) + list(kb_dir.glob("*.md"))
        count = 0
        for file in files:
            text = file.read_text(encoding="utf-8", errors="ignore")
            chunks = self._chunk_text(text)
            for idx, chunk in enumerate(chunks):
                doc_id = f"{file.stem}-{idx}"
                self.collection.upsert(
                    ids=[doc_id],
                    documents=[chunk],
                    metadatas=[{"source": str(file.name)}],
                )
                count += 1
        return count

    def query(self, text: str, top_k: int = 4) -> List[RetrievedDoc]:
        result = self.collection.query(query_texts=[text], n_results=top_k)
        docs = result.get("documents", [[]])[0]
        ids = result.get("ids", [[]])[0]
        metas = result.get("metadatas", [[]])[0]

        out: List[RetrievedDoc] = []
        for doc_id, doc_text, meta in zip(ids, docs, metas):
            out.append(RetrievedDoc(doc_id=doc_id, text=doc_text, source=meta.get("source", "unknown")))
        return out

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> List[str]:
        text = text.strip()
        if not text:
            return []
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - overlap
        return chunks
