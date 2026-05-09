from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    chroma_dir: Path = Path(os.getenv("CHROMA_DIR", "./vector_store"))
    kb_dir: Path = Path(os.getenv("KB_DIR", "./data/kb"))
    audit_log_file: Path = Path(os.getenv("AUDIT_LOG_FILE", "./logs/audit.log"))
    support_email_dl: str = os.getenv("SUPPORT_EMAIL_DL", "support@acmecloudsupport.com")
    servicenow_instance: str = os.getenv("SERVICENOW_INSTANCE", "https://acmecloud.servicenow.com")
    servicenow_username: str = os.getenv("SERVICENOW_USERNAME", "dummy_user")
    servicenow_password: str = os.getenv("SERVICENOW_PASSWORD", "dummy_password")
    enable_external_tool_calls: bool = os.getenv("ENABLE_EXTERNAL_TOOL_CALLS", "false").lower() == "true"
    imap_host: str = os.getenv("IMAP_HOST", "")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    imap_username: str = os.getenv("IMAP_USERNAME", "")
    imap_password: str = os.getenv("IMAP_PASSWORD", "")
    imap_folder: str = os.getenv("IMAP_FOLDER", "INBOX")
    imap_poll_limit: int = int(os.getenv("IMAP_POLL_LIMIT", "10"))


settings = Settings()
settings.chroma_dir.mkdir(parents=True, exist_ok=True)
settings.kb_dir.mkdir(parents=True, exist_ok=True)
settings.audit_log_file.parent.mkdir(parents=True, exist_ok=True)
