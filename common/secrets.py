import os
from typing import Optional

def validate_secret(name: str, val: Optional[str]) -> str:
    """
    Validates that a secret is present, not empty, meets minimum length,
    and does not contain placeholder/default strings.
    Returns the validated secret or raises RuntimeError (fail-closed).
    """
    if not val:
        raise RuntimeError(f"Startup failed: secret {name} is missing or empty")
    
    if len(val) < 16:
        raise RuntimeError(f"Startup failed: secret {name} is too short (must be >= 16 chars)")
    
    lower_val = val.lower()
    bad_substrings = ["default", "changeme", "example", "placeholder", "dev", "demo", "mock", "test"]
    for bad in bad_substrings:
        if bad in lower_val:
            raise RuntimeError(f"Startup failed: secret {name} contains insecure placeholder '{bad}'")
            
    return val

def get_validated_secret(name: str) -> str:
    """Gets a secret from environment and validates it."""
    val = os.getenv(name)
    return validate_secret(name, val)
