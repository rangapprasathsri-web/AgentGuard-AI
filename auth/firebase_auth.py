"""Firebase Authentication module for AgentGuard AI.

Provides server-side ID token verification using Firebase Admin SDK and
FastAPI dependencies for Owner authentication.
"""
import logging
import os
from typing import Any, Callable, Dict, Optional
from fastapi import Depends, Header, HTTPException

logger = logging.getLogger("agentguard.auth")

# Type definition for token verifier callable: (id_token: str, check_revoked: bool) -> dict
VerifierFunc = Callable[[str, bool], Dict[str, Any]]
_override_verifier: Optional[VerifierFunc] = None
_firebase_app_initialized = False


def _get_firebase_app():
    """Initializes and returns the Firebase Admin SDK app using FIREBASE_CREDENTIALS_PATH."""
    global _firebase_app_initialized
    import firebase_admin
    from firebase_admin import credentials

    if _firebase_app_initialized or firebase_admin._apps:
        _firebase_app_initialized = True
        return firebase_admin.get_app()

    # Rule: Read credentials exclusively from FIREBASE_CREDENTIALS_PATH. Never log or print the path.
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        app = firebase_admin.initialize_app(cred)
        _firebase_app_initialized = True
        return app
    else:
        # Fallback to default application credentials if available, fail closed on verification
        try:
            app = firebase_admin.initialize_app()
            _firebase_app_initialized = True
            return app
        except Exception:
            return None


def default_verify_id_token(id_token: str, check_revoked: bool = False) -> Dict[str, Any]:
    """Default token verifier using Firebase Admin SDK.
    
    Fail closed: missing/expired/invalid token -> 401, unreachable -> 503.
    Never caches revoked tokens or exposes token strings in logs or exceptions.
    """
    try:
        from firebase_admin import auth
        _get_firebase_app()
        decoded = auth.verify_id_token(id_token, check_revoked=check_revoked)
        return decoded
    except Exception as exc:
        logger.warning("Token verification rejected")
        from firebase_admin import exceptions
        from firebase_admin import auth as fb_auth

        if isinstance(exc, (fb_auth.CertificateFetchError, exceptions.UnavailableError)):
            raise HTTPException(status_code=503, detail="auth_service_unavailable")
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")


def get_token_verifier() -> VerifierFunc:
    """Dependency provider returning the active token verifier."""
    if _override_verifier is not None:
        return _override_verifier
    return default_verify_id_token


def set_token_verifier(verifier: Optional[VerifierFunc]) -> None:
    """Injectable override for tests to use a fake verifier."""
    global _override_verifier
    _override_verifier = verifier


def reset_token_verifier() -> None:
    """Resets the override token verifier to default."""
    global _override_verifier
    _override_verifier = None


async def verify_owner_token(
    authorization: Optional[str] = Header(None),
    check_revoked: bool = False,
    require_verified: bool = False,
    verifier: VerifierFunc = Depends(get_token_verifier),
) -> Dict[str, Any]:
    """Extracts and verifies Bearer ID token, upserts owner, and returns owner profile."""
    if not authorization:
        raise HTTPException(status_code=401, detail="missing_authorization_header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid_authorization_header_format")

    id_token = parts[1]
    if not id_token or not id_token.strip():
        raise HTTPException(status_code=401, detail="empty_token")

    try:
        claims = verifier(id_token, check_revoked)
    except HTTPException:
        raise
    except Exception:
        logger.warning("Unexpected error during token verification")
        raise HTTPException(status_code=401, detail="token_verification_failed")

    if not isinstance(claims, dict):
        raise HTTPException(status_code=401, detail="invalid_token_claims")

    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="missing_uid_in_token")

    email = claims.get("email") or ""
    firebase_meta = claims.get("firebase", {})
    provider = firebase_meta.get("sign_in_provider", "password")
    if provider == "google.com":
        provider = "google"

    # Google accounts are email_verified by default
    email_verified = bool(claims.get("email_verified", False) or provider == "google")

    if require_verified and not email_verified:
        raise HTTPException(status_code=403, detail="email_not_verified")

    # Upsert owner in database
    from guard.tenants import TenantStore
    try:
        store = TenantStore()
        store.upsert_owner(uid, email)
    except Exception as e:
        logger.warning("Failed to record owner login")

    return {
        "uid": uid,
        "email": email,
        "email_verified": email_verified,
        "provider": provider,
    }


class OwnerDependency:
    """FastAPI dependency for owner verification."""
    def __init__(self, sensitive: bool = False):
        self.sensitive = sensitive

    async def __call__(
        self,
        authorization: Optional[str] = Header(None),
        verifier: VerifierFunc = Depends(get_token_verifier),
    ) -> Dict[str, Any]:
        return await verify_owner_token(
            authorization=authorization,
            check_revoked=self.sensitive,
            require_verified=self.sensitive,
            verifier=verifier,
        )


current_owner = OwnerDependency(sensitive=False)
sensitive_owner = OwnerDependency(sensitive=True)
current_sensitive_owner = sensitive_owner
