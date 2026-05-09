from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from openai import OpenAI

from .audit import write_audit
from .config import settings
from .policy import SafetyPolicy, is_tool_allowed, mask_possible_phi, verification_prompt
from .rag import KnowledgeBase
from .tools import ServiceNowTools


@dataclass
class AgentRequest:
    channel: str
    user_id: str
    user_role: str
    message: str
    verified: bool = False
    ticket_id: Optional[str] = None


@dataclass
class AgentResponse:
    message: str
    action: str
    requires_human: bool = False
    requires_approval: bool = False
    pending_action_id: Optional[str] = None
    pending_action_payload: Optional[dict[str, Any]] = None


class AcmeCloudSupportAgent:
    def __init__(self) -> None:
        self.kb = KnowledgeBase()
        self.tools = ServiceNowTools()
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def handle_request(self, req: AgentRequest) -> AgentResponse:
        safe_message = mask_possible_phi(req.message)
        decision = SafetyPolicy.evaluate(safe_message)
        write_audit(
            "request.received",
            req.user_id,
            {"channel": req.channel, "message": safe_message, "role": req.user_role},
        )

        if decision.blocked:
            write_audit("request.blocked", "agent", {"reason": decision.reason})
            return AgentResponse(
                message=(
                    "I may be seeing an emergency situation. Please call 911 immediately (or local emergency services). "
                    "I am escalating this to a human support representative now."
                ),
                action="emergency_handoff",
                requires_human=True,
            )

        if decision.requires_verification and not req.verified:
            return AgentResponse(
                message=verification_prompt(req.user_id),
                action="request_verification",
                requires_approval=True,
            )

        lowered = req.message.lower()
        if "create ticket" in lowered or "open ticket" in lowered or "issue" in lowered:
            if not is_tool_allowed(req.user_role, "create_ticket"):
                return AgentResponse(
                    message="Your role is not permitted to create tickets automatically. Handing off to support.",
                    action="access_denied_handoff",
                    requires_human=True,
                )
            return self._create_ticket_flow(req)

        if "update ticket" in lowered and req.ticket_id:
            if not is_tool_allowed(req.user_role, "update_ticket"):
                return AgentResponse(
                    message="Your role is not permitted to update tickets automatically. Handing off to support.",
                    action="access_denied_handoff",
                    requires_human=True,
                )
            pending_id = str(uuid4())
            pending_payload = {
                "type": "update_ticket",
                "ticket_id": req.ticket_id,
                "updates": {"comments": req.message},
                "user_id": req.user_id,
            }
            write_audit("approval.requested", "agent", {"pending_action_id": pending_id, "payload": pending_payload})
            return AgentResponse(
                message="This ticket update requires approval. A support rep can approve or reject it below.",
                action="approval_required",
                requires_approval=True,
                pending_action_id=pending_id,
                pending_action_payload=pending_payload,
            )

        # Fast response path from RAG first.
        docs = self.kb.query(req.message, top_k=3)
        citations = "\n".join([f"- {d.source}" for d in docs]) if docs else "- No KB source matched"

        ai_text = self._answer_with_llm(req.message, docs)
        write_audit(
            "response.generated",
            "agent",
            {"action": "rag_answer", "sources": [d.source for d in docs]},
        )
        return AgentResponse(
            message=f"{ai_text}\n\nSources:\n{citations}",
            action="rag_answer",
        )

    def _create_ticket_flow(self, req: AgentRequest) -> AgentResponse:
        if req.user_role not in {"member", "provider", "admin"}:
            return AgentResponse(
                message="I cannot validate your access level for ticket actions. Handing off to human support.",
                action="access_denied_handoff",
                requires_human=True,
            )

        created = self.tools.create_ticket(req.user_id, "Support Request", req.message)
        status = created.get("status", "unknown")

        if status.startswith("failed"):
            return AgentResponse(
                message="I could not create the ticket automatically. I am handing this to a support representative.",
                action="tool_failed_handoff",
                requires_human=True,
            )

        ticket_id = created.get("ticket_id") or created.get("result", {}).get("result", {}).get("number", "UNKNOWN")
        return AgentResponse(
            message=(
                f"I created your support ticket: {ticket_id}. "
                "A human rep can review and approve sensitive changes if needed."
            ),
            action="ticket_created",
        )

    def execute_approved_action(self, payload: dict[str, Any]) -> AgentResponse:
        action_type = payload.get("type")
        if action_type == "update_ticket":
            updated = self.tools.update_ticket(payload["ticket_id"], payload["updates"])
            return AgentResponse(
                message=f"Approved action executed. Ticket update result: {updated.get('status', 'unknown')}.",
                action="ticket_updated",
            )
        return AgentResponse(
            message="Unsupported approved action. Handing off to human support.",
            action="unsupported_action_handoff",
            requires_human=True,
        )

    def _answer_with_llm(self, query: str, docs: list) -> str:
        context = "\n\n".join([d.text for d in docs][:3])

        if not self.client:
            return (
                "Here is what I found in the knowledge base. "
                "If you want, I can also open a ticket for deeper investigation."
            )

        system_prompt = (
            "You are AcmeCloud healthcare support agent. "
            "Never provide diagnosis or prescription advice. "
            "Answer only with grounded context. If uncertain, recommend human handoff."
        )
        user_prompt = f"User question: {query}\n\nGrounding context:\n{context}"

        try:
            response = self.client.responses.create(
                model=settings.openai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_output_tokens=350,
            )
            text = getattr(response, "output_text", "").strip()
            return text or "I could not generate a reliable answer. I recommend human support review."
        except Exception as exc:
            write_audit("llm.failure", "agent", {"error": str(exc)})
            return "I had trouble generating a final answer. I can create a support ticket or hand off to a human rep."
