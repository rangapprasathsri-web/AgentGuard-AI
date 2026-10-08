import json
import hashlib
import hmac
from typing import Any, Dict


def canonical_json(data: Any) -> str:
    """
    Produce canonical JSON representation:
    - sorted keys
    - separators (',', ':') without whitespace
    - ensure_ascii=True
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_action_hash(agent_id: str, action: str, target: str, params: Dict[str, Any]) -> str:
    """
    Canonical action payload: {agent_id, action, target, params}.
    source and approval_id are NOT included in the hash.
    record_count is within params and is therefore hashed.
    """
    payload = {
        "action": action,
        "agent_id": agent_id,
        "params": params,
        "target": target,
    }
    canonical_str = canonical_json(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def compute_sha256(content: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sign_payload(secret_key: str, payload_dict: Dict[str, Any]) -> str:
    """
    Compute HMAC-SHA256 signature for a response payload dict.
    The 'sig' field itself is excluded from the signed payload if present.
    """
    clean_payload = {k: v for k, v in payload_dict.items() if k != "sig"}
    canonical_str = canonical_json(clean_payload)
    return hmac.new(
        secret_key.encode("utf-8"),
        canonical_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_signature(secret_key: str, payload_dict: Dict[str, Any], signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature against payload dict.
    """
    expected_sig = sign_payload(secret_key, payload_dict)
    return hmac.compare_digest(expected_sig, signature)
