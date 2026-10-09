import os
from cryptography.fernet import Fernet
import base64

def get_vault_key() -> bytes:
    key = os.getenv("AGENTGUARD_VAULT_KEY")
    if not key:
        # Fallback for tests/dev, but should fail in prod if missing
        key = base64.urlsafe_b64encode(b"0" * 32).decode('utf-8')
    return key.encode('utf-8')

def encrypt_credential(plaintext: str) -> str:
    key = get_vault_key()
    f = Fernet(key)
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')

def decrypt_credential(ciphertext: str) -> str:
    key = get_vault_key()
    f = Fernet(key)
    return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
