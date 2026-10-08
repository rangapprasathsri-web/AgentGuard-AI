import asyncio
import os
from typing import Any, Dict, Optional, Tuple
import httpx
from pydantic import BaseModel, Field
from agents.config_loader import load_department_config
from common.llm_client import LLMClient


class ProposedAction(BaseModel):
    action: str
    target: str
    params: Dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None


class AgentRuntime:
    """
    Generic AgentRuntime supporting all five departments:
    analytics, database, coding, finance, devops.
    Proposes actions to the Gateway only.
    Holds ZERO credentials to enterprise tools.
    """

    def __init__(
        self,
        department: str,
        gateway_url: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        poll_interval: float = 2.0,
    ):
        self.department = department
        self.config = load_department_config(department)
        self.agent_id: str = self.config["agent_id"]
        self.system_prompt: str = self.config["system_prompt"]
        self.allowed_tools = self.config.get("allowed_tools", [])
        self.gateway_url = gateway_url or os.getenv("GATEWAY_URL", "http://localhost:8002")
        self.llm_client = llm_client or LLMClient()
        self.poll_interval = poll_interval

    async def propose_and_execute(
        self,
        request_text: str,
        source_type: str = "user",
        content_excerpt: Optional[str] = None,
        direct_proposal: Optional[Dict[str, Any]] = None,
        max_poll_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """
        1. Translates natural language request into a proposed action via LLM (or direct proposal).
        2. Submits proposed action to POST /gateway/execute.
        3. On 202 pending_approval: polls GET /gateway/status/{id} until terminal status.
        4. On APPROVED: resubmits stored action unchanged with approval_id.
        """
        # Step 1: Generate proposed action
        if direct_proposal is not None:
            proposed = direct_proposal
        else:
            prompt = (
                f"User Request: {request_text}\n"
                f"Allowed Department Tools: {self.allowed_tools}\n"
                "Propose the single next action to take in JSON format matching schema: "
                "{action: str, target: str, params: dict, explanation: str}."
            )
            raw_proposal, _, _ = await self.llm_client.complete(
                system=self.system_prompt,
                user_prompt=prompt,
                schema_model=ProposedAction,
            )
            if not raw_proposal:
                return {"status": "error", "message": "Failed to generate action proposal"}
            proposed = raw_proposal

        action_payload = {
            "agent_id": self.agent_id,
            "action": proposed["action"],
            "target": proposed["target"],
            "params": proposed.get("params", {}),
            "source": {
                "type": source_type,
                "content_excerpt": content_excerpt or request_text[:200],
            },
        }

        # Step 2: Submit to Gateway
        headers = {
            "Content-Type": "application/json",
            "X-Actor": self.agent_id,
            "X-Role": "agent",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.gateway_url}/gateway/execute",
                json=action_payload,
                headers=headers,
            )

            # Executed directly (ALLOW)
            if resp.status_code == 200:
                return resp.json()

            # Blocked (BLOCK)
            if resp.status_code == 403:
                return resp.json()

            # Pending approval (REVIEW)
            if resp.status_code == 202:
                review_data = resp.json()
                approval_id = review_data.get("approval_id")

                # Step 3: Poll Gateway status until terminal state
                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < max_poll_seconds:
                    await asyncio.sleep(self.poll_interval)
                    status_resp = await client.get(
                        f"{self.gateway_url}/gateway/status/{approval_id}",
                        headers=headers,
                    )
                    if status_resp.status_code != 200:
                        continue

                    current_status = status_resp.json().get("status")
                    if current_status == "APPROVED":
                        # Resubmit exact action with approval_id
                        action_payload["approval_id"] = approval_id
                        resubmit_resp = await client.post(
                            f"{self.gateway_url}/gateway/execute",
                            json=action_payload,
                            headers=headers,
                        )
                        return resubmit_resp.json()

                    elif current_status in ["REJECTED", "EXPIRED", "VOIDED", "CONSUMED"]:
                        return {
                            "status": "terminated",
                            "approval_id": approval_id,
                            "terminal_status": current_status,
                        }

                return {
                    "status": "pending_timeout",
                    "approval_id": approval_id,
                    "message": "Timed out waiting for approver decision",
                }

            # Other error/status
            return {"status": "gateway_error", "code": resp.status_code, "body": resp.text}
