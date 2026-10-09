#!/usr/bin/env python3
import os
import re
import sys

# Define regex for key-shaped strings
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),               # Common API key format
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),              # 32+ hex chars (hashes, some keys)
    re.compile(r"ak-[a-zA-Z0-9]{16,}"),               # Custom ak- keys
]

# Patterns to ignore based on user request and normal project files
IGNORE_DIRS = {".git", "node_modules", ".pytest_cache", "venv", "__pycache__"}
IGNORE_FILES = {
    "package-lock.json", 
    "audit.db", 
    "tools.db", 
    "audit.db-wal", 
    "audit.db-shm",
    "tools.db-wal",
    "tools.db-shm",
    "api keys.docx",
    "api_keys.docx",
    "strict.docx"
}

def is_ignored(path):
    parts = path.split(os.sep)
    for part in parts:
        if part in IGNORE_DIRS:
            return True
    filename = os.path.basename(path)
    if filename in IGNORE_FILES:
        return True
    if filename.startswith(".env"):
        return True
    if filename.endswith(".pyc") or ".db" in filename or filename.endswith(".sqlite"):
        return True
    return False

def scan_directory(root_dir):
    found_secrets = []
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Prune ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if is_ignored(filepath):
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f):
                        for pattern in SECRET_PATTERNS:
                            matches = pattern.findall(line)
                            for match in matches:
                                # Whitelist specific test strings we just added
                                if match in ["sk_valid_service_key_16bytes", "ak_valid_hmac_key_16bytes"]:
                                    continue
                                found_secrets.append(f"{filepath}:{i+1} -> {match}")
            except Exception as e:
                pass
                
    return found_secrets

if __name__ == "__main__":
    print("Scanning for secrets...")
    secrets = scan_directory(".")
    if secrets:
        print("ERROR: Found potential secrets in the codebase:")
        for s in secrets:
            print(f"  {s}")
        sys.exit(1)
    else:
        print("Scan complete. No secrets found.")
        sys.exit(0)
