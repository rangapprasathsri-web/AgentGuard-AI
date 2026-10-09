import os
import queue
import threading
import time
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import hashlib

# We lazily import firebase_admin to avoid dependency issues if disabled
firebase_app = None
firestore_client = None
init_lock = threading.Lock()

# State
dropped_events = 0
last_error = None
last_success_ts = None
mirror_queue = queue.Queue(maxsize=1000)
worker_thread = None

logger = logging.getLogger("firebase_mirror")

def is_enabled() -> bool:
    return os.getenv("FIREBASE_ENABLED", "false").lower() == "true"

def _lazy_init():
    global firebase_app, firestore_client, last_error
    if not is_enabled():
        return False
        
    with init_lock:
        if firestore_client is not None:
            return True
            
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
            if not cred_path or not os.path.exists(cred_path):
                raise ValueError(f"Credentials missing at {cred_path}")
                
            project_id = os.getenv("FIREBASE_PROJECT_ID")
            
            # Lazy initialize
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_app = firebase_admin.initialize_app(cred, {"projectId": project_id})
            else:
                firebase_app = firebase_admin.get_app()
                
            firestore_client = firestore.client()
            return True
        except Exception as e:
            last_error = f"init_error: {str(e)}"
            logger.warning(f"Firebase mirror init failed: {e}")
            return False

def _process_queue():
    global dropped_events, last_error, last_success_ts
    while True:
        try:
            item = mirror_queue.get()
            if item is None:
                break # stop signal
                
            collection, doc_id, data, op = item
            
            if not _lazy_init():
                continue
                
            # Timeout logic using a simple executor or grpc timeout
            # firestore library allows setting timeout on requests
            try:
                # 2s timeout
                if op == "set":
                    firestore_client.collection(collection).document(doc_id).set(data, timeout=2.0)
                elif op == "update":
                    firestore_client.collection(collection).document(doc_id).update(data, timeout=2.0)
                elif op == "increment":
                    # metrics/summary increments
                    from google.cloud.firestore import Increment
                    inc_data = {k: Increment(v) for k, v in data.items()}
                    firestore_client.collection(collection).document(doc_id).set(inc_data, merge=True, timeout=2.0)
                
                last_success_ts = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                last_error = f"write_error: {str(e)}"
                logger.warning(f"Firebase mirror write failed: {e}")
                
        except Exception as e:
            last_error = f"worker_error: {str(e)}"
        finally:
            if 'item' in locals() and item is not None:
                mirror_queue.task_done()

def _enqueue(collection: str, doc_id: str, data: Dict[str, Any], op: str = "set"):
    global dropped_events, worker_thread
    if not is_enabled():
        return
        
    with init_lock:
        if worker_thread is None or not worker_thread.is_alive():
            worker_thread = threading.Thread(target=_process_queue, daemon=True)
            worker_thread.start()
            
    try:
        mirror_queue.put_nowait((collection, doc_id, data, op))
    except queue.Full:
        # Drop oldest
        try:
            mirror_queue.get_nowait()
            dropped_events += 1
            mirror_queue.put_nowait((collection, doc_id, data, op))
        except (queue.Empty, queue.Full):
            dropped_events += 1
            logger.warning("Firebase mirror queue full, dropped event.")

def _hash_params(params: Dict[str, Any]) -> str:
    s = json.dumps(params, sort_keys=True).encode("utf-8")
    return hashlib.sha256(s).hexdigest()

def _redact_params(params: Dict[str, Any]) -> Dict[str, str]:
    # Return a redacted summary
    return {k: "[REDACTED]" for k in params.keys()}

def mirror_decision(decision_id: str, agent_id: str, action: str, target: str, 
                    decision: str, risk_score: int, reasons: list, rule_ids: list,
                    amount: int, params: dict, approval_id: Optional[str], latency_ms: float):
    if not is_enabled():
        return
    data = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "action": action,
        "target": target,
        "decision": decision,
        "risk_score": risk_score,
        "reasons": reasons,
        "rule_ids": rule_ids,
        "amount": amount,
        "currency": "INR",
        "params_hash": _hash_params(params),
        "params_summary": _redact_params(params),
        "approval_id": approval_id,
        "latency_ms": latency_ms
    }
    _enqueue("decisions", decision_id, data)
    
    # Update metrics
    metrics_inc = {}
    if decision == "ALLOW":
        metrics_inc["allow_count"] = 1
    elif decision == "REVIEW":
        metrics_inc["review_count"] = 1
    elif decision == "BLOCK":
        metrics_inc["block_count"] = 1
        metrics_inc["blocked_amount_inr"] = amount
        
    if metrics_inc:
        _enqueue("metrics", "summary", metrics_inc, op="increment")

def mirror_approval(approval_id: str, state: str, request_hash: str, 
                    decided_by_role: Optional[str], created_at: str, 
                    decided_at: Optional[str], consumed_at: Optional[str]):
    if not is_enabled():
        return
    data = {
        "state": state,
        "request_hash": request_hash,
        "decided_by_role": decided_by_role,
        "created_at": created_at,
        "decided_at": decided_at,
        "consumed_at": consumed_at
    }
    _enqueue("approvals", approval_id, data)
    
    if state == "PENDING":
        _enqueue("metrics", "summary", {"pending_approvals": 1}, op="increment")
    elif state in ("APPROVED", "REJECTED", "EXPIRED", "VOIDED"):
        _enqueue("metrics", "summary", {"pending_approvals": -1}, op="increment")

def mirror_audit(seq: int, entry_hash: str, prev_hash: str, event_type: str, ts: str):
    if not is_enabled():
        return
    data = {
        "seq": seq,
        "entry_hash": entry_hash,
        "prev_hash": prev_hash,
        "event_type": event_type,
        "ts": ts
    }
    _enqueue("audit", str(seq), data)

def mirror_health(service_name: str, version: str, status: str):
    if not is_enabled():
        return
    data = {
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "status": status
    }
    _enqueue("health", service_name, data)

def get_status() -> Dict[str, Any]:
    return {
        "enabled": is_enabled(),
        "queue_depth": mirror_queue.qsize(),
        "dropped": dropped_events,
        "last_error": last_error,
        "last_success_ts": last_success_ts
    }
