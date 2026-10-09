#!/usr/bin/env python3
import sys
import subprocess
import os
import re

target = sys.argv[1] if len(sys.argv) > 1 else "all"

if target == "seed":
    print("Seeding tools database...")
    from tools.db import init_tools_db
    init_tools_db()
elif target in ["test", "all"]:
    print("Running all tests offline with MockLLM (no external network)...")
    env = os.environ.copy()
    env["LLM_MODE"] = "mock"
    env["PYTHONPATH"] = "."
    res = subprocess.run(["python3", "-m", "pytest", "-v", "tests/"], env=env)
    sys.exit(res.returncode)
elif target == "demo":
    print("Starting all five processes for AgentGuard AI...")
    subprocess.run(["bash", "scripts/run_all.sh"])
elif target == "clean":
    print("Cleaning temporary files...")
    for f in ["tools.db", "guard.db", "audit.db", "tenants.db", "release.zip", "test_output.txt"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
elif target == "scan":
    print("Scanning for secrets...")
    res = subprocess.run(["python3", "scripts/secret_scan.py"])
    sys.exit(res.returncode)
elif target == "package":
    print("Packaging codebase...")
    if os.path.exists("release.zip"):
        os.remove("release.zip")
    res = subprocess.run(["zip", "-r", "release.zip", ".", "-x", "*.env*", "*.db*", "*api keys.docx*", "*/node_modules/*", "*/.git/*", "*/.pytest_cache/*", "*__pycache__/*", "*credentials*.json*", "*service_account*.json*"])
    sys.exit(res.returncode)
elif target == "check-package":
    print("Packaging codebase...")
    if os.path.exists("release.zip"):
        os.remove("release.zip")
    res = subprocess.run(["zip", "-r", "release.zip", ".", "-x", "*.env*", "*.db*", "*api keys.docx*", "*/node_modules/*", "*/.git/*", "*/.pytest_cache/*", "*__pycache__/*", "*credentials*.json*", "*service_account*.json*"])
    if res.returncode != 0:
        sys.exit(res.returncode)
    print("Checking package for secrets and databases...")
    unzip_res = subprocess.run(["unzip", "-l", "release.zip"], capture_output=True, text=True)
    bad = re.findall(r'(\.env|\.db|api keys\.docx|credentials\.json)', unzip_res.stdout)
    if bad:
        print(f"ERROR: Package contains sensitive files: {bad}")
        sys.exit(1)
    print("Package is clean.")
elif target == "lint":
    try:
        subprocess.run(["flake8", "."])
    except FileNotFoundError:
        print("flake8 not found, skipping")
elif target == "verify":
    print("Scanning for secrets...")
    scan_res = subprocess.run(["python3", "scripts/secret_scan.py"])
    if scan_res.returncode != 0:
        sys.exit(scan_res.returncode)
    print("Running full verification suite...")
    env = os.environ.copy()
    env["LLM_MODE"] = "mock"
    env["PYTHONPATH"] = "."
    res = subprocess.run(["python3", "-m", "pytest", "-q", "tests/"], env=env, capture_output=True, text=True)
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    m = re.search(r'(\d+) passed', res.stdout)
    count = int(m.group(1)) if m else 0
    if count < 57 or res.returncode != 0:
        print(f"ERROR: Test verification failed! Found {count} passed (expected at least 57).")
        sys.exit(1)
    print(f"All verification checks passed! ({count} passed)")
    sys.exit(0)
else:
    print(f"Unknown target '{target}'. Available: seed, test, demo, clean, scan, package, check-package, lint, verify")
    sys.exit(1)
