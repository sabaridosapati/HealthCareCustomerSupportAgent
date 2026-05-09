from __future__ import annotations

from .config import settings
from .rag import KnowledgeBase


def main() -> None:
    kb = KnowledgeBase()
    count = kb.ingest_directory(settings.kb_dir)
    print(f"Ingested {count} chunks from {settings.kb_dir}")


if __name__ == "__main__":
    main()
