from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from .audit import write_audit
from .config import settings


class ServiceNowTools:
    def __init__(self) -> None:
        self.instance = settings.servicenow_instance.rstrip("/")
        self.auth = (settings.servicenow_username, settings.servicenow_password)
        self.external_calls = settings.enable_external_tool_calls

    def create_ticket(self, user_id: str, summary: str, details: str) -> dict[str, Any]:
        payload = {
            "short_description": summary,
            "description": details,
            "caller_id": user_id,
            "category": "customer_support",
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
        if not self.external_calls:
            ticket = {
                "status": "mock_created",
                "ticket_id": f"INC-MOCK-{int(datetime.now().timestamp())}",
                "instance": self.instance,
                "payload": payload,
            }
            write_audit("tool.create_ticket", "agent", ticket)
            return ticket

        url = f"{self.instance}/api/now/table/incident"
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(url, auth=self.auth, json=payload)
                response.raise_for_status()
                data = response.json()
                write_audit("tool.create_ticket", "agent", data)
                return {"status": "created", "result": data}
        except Exception as exc:
            err = {"status": "failed", "reason": str(exc), "fallback": "human_handoff"}
            write_audit("tool.create_ticket_failed", "agent", err)
            return err

    def update_ticket(self, ticket_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if not self.external_calls:
            resp = {"status": "mock_updated", "ticket_id": ticket_id, "updates": updates}
            write_audit("tool.update_ticket", "agent", resp)
            return resp

        url = f"{self.instance}/api/now/table/incident/{ticket_id}"
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.patch(url, auth=self.auth, json=updates)
                response.raise_for_status()
                data = response.json()
                write_audit("tool.update_ticket", "agent", data)
                return {"status": "updated", "result": data}
        except Exception as exc:
            err = {"status": "failed", "reason": str(exc), "fallback": "human_handoff"}
            write_audit("tool.update_ticket_failed", "agent", err)
            return err

    def add_worknote(self, ticket_id: str, note: str) -> dict[str, Any]:
        return self.update_ticket(ticket_id=ticket_id, updates={"work_notes": note})
