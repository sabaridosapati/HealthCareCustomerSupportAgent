from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .config import settings


def write_audit(event_type: str, actor: str, payload: dict[str, Any]) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor": actor,
        "payload": payload,
    }
    with settings.audit_log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
