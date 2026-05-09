from __future__ import annotations

import email
import imaplib
import json
from email.header import decode_header
from pathlib import Path
from typing import Any

from .agent import AcmeCloudSupportAgent, AgentRequest
from .audit import write_audit
from .config import settings

SAMPLE_EMAILS = [
    {
        "from": "member1@example.com",
        "subject": "Need help with portal login",
        "body": "I cannot access my account. Please open ticket.",
        "role": "member",
        "verified": False,
    },
    {
        "from": "member2@example.com",
        "subject": "Billing policy question",
        "body": "What is your claim submission timeline?",
        "role": "member",
        "verified": True,
    },
]


def _decode(value: str) -> str:
    decoded = decode_header(value)
    parts = []
    for chunk, enc in decoded:
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="ignore"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in cdisp:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")


def poll_imap_messages(limit: int) -> list[dict[str, Any]]:
    if not settings.imap_host or not settings.imap_username or not settings.imap_password:
        return SAMPLE_EMAILS

    out: list[dict[str, Any]] = []
    with imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port) as mail:
        mail.login(settings.imap_username, settings.imap_password)
        mail.select(settings.imap_folder)
        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            return out

        ids = data[0].split()[-limit:]
        for msg_id in ids:
            f_status, f_data = mail.fetch(msg_id, "(RFC822)")
            if f_status != "OK":
                continue
            raw = f_data[0][1]
            msg = email.message_from_bytes(raw)
            sender = _decode(msg.get("From", "unknown@example.com"))
            subject = _decode(msg.get("Subject", "No Subject"))
            body = _extract_body(msg)
            out.append(
                {
                    "from": sender,
                    "subject": subject,
                    "body": body,
                    "role": "member",
                    "verified": False,
                }
            )
    return out


def run_email_intake() -> None:
    agent = AcmeCloudSupportAgent()
    inbox_file = Path("./logs/email_results.json")

    results = []
    emails = poll_imap_messages(settings.imap_poll_limit)
    for inbound in emails:
        req = AgentRequest(
            channel="email",
            user_id=inbound["from"],
            user_role=inbound.get("role", "member"),
            message=f"Subject: {inbound['subject']}\nBody: {inbound['body']}",
            verified=inbound.get("verified", False),
        )
        resp = agent.handle_request(req)
        item = {"email": inbound, "response": resp.__dict__}
        results.append(item)
        write_audit("email.processed", "email_ingestor", item)

    inbox_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Processed {len(results)} emails. Results saved to {inbox_file}")


if __name__ == "__main__":
    run_email_intake()
