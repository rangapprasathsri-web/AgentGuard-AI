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


_cached_certs: Dict[str, str] = {}
_certs_expiry: float = 0.0


def _get_google_public_certs() -> Dict[str, str]:
    """Fetches Google's public key certificates for Firebase ID token verification."""
    global _cached_certs, _certs_expiry
    import time
    import urllib.request
    import json

    now = time.time()
    if _cached_certs and now < _certs_expiry:
        return _cached_certs

    url = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
    req = urllib.request.Request(url, headers={"User-Agent": "AgentGuard-Auth/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode("utf-8")
            certs = json.loads(data)
            cache_ctrl = resp.headers.get("Cache-Control", "")
            max_age = 3600
            for part in cache_ctrl.split(","):
                part = part.strip()
                if part.startswith("max-age="):
                    try:
                        max_age = int(part.split("=")[1])
                    except ValueError:
                        pass
            _cached_certs = certs
            _certs_expiry = now + max_age
            return _cached_certs
    except Exception:
        logger.warning("Failed to reach Google public cert endpoint")
        raise HTTPException(status_code=503, detail="auth_service_unavailable")


def _verify_with_public_certs(id_token: str, project_id: str) -> Dict[str, Any]:
    """Cryptographically verifies a Firebase ID token using Google public certificates."""
    import jwt
    from cryptography.x509 import load_pem_x509_certificate

    try:
        headers = jwt.get_unverified_header(id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")

    if headers.get("alg") != "RS256":
        raise HTTPException(status_code=401, detail="invalid_token_algorithm")

    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="missing_token_kid")

    certs = _get_google_public_certs()
    cert_pem = certs.get(kid)
    if not cert_pem:
        global _certs_expiry
        _certs_expiry = 0
        certs = _get_google_public_certs()
        cert_pem = certs.get(kid)
        if not cert_pem:
            raise HTTPException(status_code=401, detail="invalid_or_expired_token")

    try:
        cert_obj = load_pem_x509_certificate(cert_pem.encode("utf-8"))
        pub_key = cert_obj.public_key()
        issuer = f"https://securetoken.google.com/{project_id}"
        decoded = jwt.decode(
            id_token,
            key=pub_key,
            algorithms=["RS256"],
            audience=project_id,
            issuer=issuer,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
        # Firebase convention: ensure sub is set as uid if uid is missing
        if "uid" not in decoded and "sub" in decoded:
            decoded["uid"] = decoded["sub"]
        return decoded
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")


def _get_firebase_app():
    """Initializes and returns the Firebase Admin SDK app using FIREBASE_CREDENTIALS_PATH."""
    global _firebase_app_initialized
    import firebase_admin
    from firebase_admin import credentials

    if _firebase_app_initialized or firebase_admin._apps:
        _firebase_app_initialized = True
        return firebase_admin.get_app()

    project_id = os.getenv("FIREBASE_PROJECT_ID", "agentguard---ai")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        app = firebase_admin.initialize_app(cred, options={"projectId": project_id})
        _firebase_app_initialized = True
        return app
    else:
        try:
            app = firebase_admin.initialize_app(options={"projectId": project_id})
            _firebase_app_initialized = True
            return app
        except Exception:
            return None


def default_verify_id_token(id_token: str, check_revoked: bool = False) -> Dict[str, Any]:
    """Default token verifier using Firebase Admin SDK or Google public certificates.
    
    Fail closed: missing/expired/invalid token -> 401, unreachable -> 503.
    Never caches revoked tokens or exposes token strings in logs or exceptions.
    """
    project_id = os.getenv("FIREBASE_PROJECT_ID", "agentguard---ai")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

    # If service account credentials file exists, use Firebase Admin SDK
    if cred_path and os.path.exists(cred_path):
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

    # If credentials file is not configured, verify cryptographically against Google public certificates
    return _verify_with_public_certs(id_token, project_id)


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
