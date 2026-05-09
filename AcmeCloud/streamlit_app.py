from __future__ import annotations

import streamlit as st

from app.agent import AcmeCloudSupportAgent, AgentRequest
from app.audit import write_audit

st.set_page_config(page_title="AcmeCloud Support Agent", page_icon=":hospital:", layout="wide")
st.title("AcmeCloud Customer Support Agent")
st.caption("Healthcare-safe support assistant with RAG, tool calling, and HITL patterns")

if "agent" not in st.session_state:
    st.session_state.agent = AcmeCloudSupportAgent()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "approval_queue" not in st.session_state:
    st.session_state.approval_queue = []

with st.sidebar:
    st.subheader("Session")
    user_id = st.text_input("User ID", value="member_demo")
    user_role = st.selectbox("Role", options=["member", "provider", "admin", "guest"], index=0)
    verified = st.checkbox("Identity Verified", value=False)
    ticket_id = st.text_input("Ticket ID (optional)")

    st.divider()
    st.subheader("Approval Queue")
    if not st.session_state.approval_queue:
        st.caption("No pending approvals.")
    else:
        remove_idx = None
        for i, item in enumerate(st.session_state.approval_queue):
            st.write(f"Request {i + 1}: `{item['id']}`")
            st.code(str(item["payload"]), language="text")
            col1, col2 = st.columns(2)
            if col1.button("Approve", key=f"approve_{item['id']}"):
                resp = st.session_state.agent.execute_approved_action(item["payload"])
                st.session_state.messages.append({"role": "assistant", "content": resp.message})
                write_audit("approval.approved", "human_reviewer", {"id": item["id"], "payload": item["payload"]})
                remove_idx = i
            if col2.button("Reject", key=f"reject_{item['id']}"):
                msg = "Request rejected by human reviewer. A support representative will follow up."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                write_audit("approval.rejected", "human_reviewer", {"id": item["id"], "payload": item["payload"]})
                remove_idx = i
        if remove_idx is not None:
            st.session_state.approval_queue.pop(remove_idx)
            st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Enter your support request...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        ph = st.empty()
        ph.info("Working on a quick response...")

        req = AgentRequest(
            channel="chat",
            user_id=user_id,
            user_role=user_role,
            message=prompt,
            verified=verified,
            ticket_id=ticket_id or None,
        )
        resp = st.session_state.agent.handle_request(req)

        if resp.requires_human:
            ph.warning(resp.message)
        elif resp.requires_approval:
            ph.info(resp.message)
            if resp.pending_action_id and resp.pending_action_payload:
                st.session_state.approval_queue.append(
                    {"id": resp.pending_action_id, "payload": resp.pending_action_payload}
                )
                write_audit(
                    "approval.queued",
                    "agent",
                    {"id": resp.pending_action_id, "payload": resp.pending_action_payload},
                )
        else:
            ph.success(resp.message)

        st.caption(f"Action: {resp.action}")

    st.session_state.messages.append({"role": "assistant", "content": resp.message})
