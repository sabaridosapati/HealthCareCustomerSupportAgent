from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


EMERGENCY_KEYWORDS = {
    "chest pain",
    "suicidal",
    "suicide",
    "overdose",
    "not breathing",
    "stroke",
    "heart attack",
}

ACCOUNT_CHANGE_KEYWORDS = {
    "change address",
    "update insurance",
    "change phone",
    "reset account",
}


@dataclass
class PolicyDecision:
    blocked: bool
    reason: str
    requires_human: bool = False
    requires_verification: bool = False


class SafetyPolicy:
    @staticmethod
    def evaluate(message: str) -> PolicyDecision:
        content = message.lower()

        if any(keyword in content for keyword in EMERGENCY_KEYWORDS):
            return PolicyDecision(
                blocked=True,
                reason=(
                    "Potential emergency detected. Advise user to call emergency services (911) "
                    "or local crisis line immediately, and handoff to human support."
                ),
                requires_human=True,
            )

        if any(keyword in content for keyword in ACCOUNT_CHANGE_KEYWORDS):
            return PolicyDecision(
                blocked=False,
                reason="Sensitive account change detected; verification required.",
                requires_verification=True,
            )

        return PolicyDecision(blocked=False, reason="Allowed")


TOOL_ACCESS_MATRIX = {
    "member": {"create_ticket": True, "update_ticket": False, "kb_access": True},
    "provider": {"create_ticket": True, "update_ticket": True, "kb_access": True},
    "admin": {"create_ticket": True, "update_ticket": True, "kb_access": True},
    "guest": {"create_ticket": False, "update_ticket": False, "kb_access": True},
}


def is_tool_allowed(role: str, tool_name: str) -> bool:
    return TOOL_ACCESS_MATRIX.get(role, {}).get(tool_name, False)


def mask_possible_phi(text: str) -> str:
    # Lightweight placeholder masking strategy for demo usage.
    # In production, replace with stronger PHI/PII detection service.
    redactions = ["ssn", "social security", "dob", "date of birth", "member id"]
    out = text
    for token in redactions:
        out = out.replace(token, "[REDACTED_FIELD]")
        out = out.replace(token.upper(), "[REDACTED_FIELD]")
    return out


def verification_prompt(user_id: Optional[str]) -> str:
    uid = user_id or "unknown-user"
    return (
        f"Before I make account-level changes, I need verification for {uid}. "
        "Please confirm last name and date of birth (MM/DD) or request a human representative."
    )
