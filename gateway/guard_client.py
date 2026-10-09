import os
from typing import Any, Dict, Optional, Tuple
import httpx
from common.canonical import canonical_json, compute_sha256, verify_signature


class GuardClient:
    def __init__(
        self,
        guard_url: Optional[str] = None,
        service_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.guard_url = guard_url or os.getenv("GUARD_URL", "http://localhost:8001")
        self.service_key = service_key or os.getenv("SERVICE_KEY")
        if not self.service_key:
            raise RuntimeError("SERVICE_KEY missing")
        self.timeout = timeout

    async def evaluate(
        self, request_payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Calls Guard /guard/evaluate.
        Returns: (success, response_dict_or_none, error_type)
        """
        url = f"{self.guard_url}/guard/evaluate"
        headers = {
            "Content-Type": "application/json",
            "X-Service-Key": self.service_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=request_payload, headers=headers)
                if resp.status_code != 200:
                    return False, None, f"guard_status_{resp.status_code}"
                data = resp.json()

                # Verify Guard signature
                sig = data.get("sig")
                if not sig or not verify_signature(self.service_key, data, sig):
                    return False, None, "bad_signature"

                return True, data, None
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
            return False, None, "guard_unreachable"
        except Exception:
            return False, None, "guard_unreachable"

    async def authorize(
        self, request_payload: Dict[str, Any], approval_id: str
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Calls Guard /guard/authorize.
        Returns: (success, response_dict_or_none, error_type)
        """
        url = f"{self.guard_url}/guard/authorize"
        headers = {
            "Content-Type": "application/json",
            "X-Service-Key": self.service_key,
        }
        body = {"request": request_payload, "approval_id": approval_id}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code not in [200, 403]:
                    return False, None, f"guard_status_{resp.status_code}"
                data = resp.json()

                sig = data.get("sig")
                if not sig or not verify_signature(self.service_key, data, sig):
                    return False, None, "bad_signature"

                return True, data, None
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
            return False, None, "guard_unreachable"
        except Exception:
            return False, None, "guard_unreachable"

    async def confirm(self, decision_id: str, outcome: str) -> bool:
        """
        Calls Guard /guard/confirm.
        """
        url = f"{self.guard_url}/guard/confirm"
        headers = {
            "Content-Type": "application/json",
            "X-Service-Key": self.service_key,
        }
        body = {"decision_id": decision_id, "outcome": outcome}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

    async def get_approval_status(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Calls Guard /approvals/{id} to get status.
        """
        url = f"{self.guard_url}/approvals/{approval_id}"
        headers = {
            "Content-Type": "application/json",
            "X-Service-Key": self.service_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None
