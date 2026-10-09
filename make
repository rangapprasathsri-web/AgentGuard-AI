#!/usr/bin/env python3
import sys
import subprocess
import os

target = sys.argv[1] if len(sys.argv) > 1 else "all"

if target in ["seed"]:
    print("Seeding tools database...")
    from tools.db import init_tools_db
    init_tools_db()
elif target in ["test", "all"]:
    print("Running all tests offline with MockLLM (no external network)...")
    env = os.environ.copy()
    env["LLM_MODE"] = "mock"
    res = subprocess.run(["python3", "-m", "pytest", "-v", "tests/"], env=env)
    sys.exit(res.returncode)
elif target in ["demo"]:
    print("Starting all five processes for AgentGuard AI...")
    subprocess.run(["bash", "scripts/run_all.sh"])
elif target in ["clean"]:
    print("Cleaning temporary files...")
    for f in ["tools.db", "guard.db", "audit.db"]:
        if os.path.exists(f):
            os.remove(f)
elif target in ["scan"]:
    print("Scanning for secrets...")
    res = subprocess.run(["python3", "scripts/secret_scan.py"])
    sys.exit(res.returncode)
elif target in ["package"]:
    print("Packaging codebase...")
    if os.path.exists("release.zip"):
        os.remove("release.zip")
    res = subprocess.run(["zip", "-r", "release.zip", ".", "-x", "*.env*", "*.db*", "*api keys.docx*", "*/node_modules/*", "*/.git/*", "*/.pytest_cache/*", "*__pycache__/*"])
    sys.exit(res.returncode)
else:
    print(f"Unknown target '{target}'. Available: seed, test, demo, clean, scan, package")
    sys.exit(1)
