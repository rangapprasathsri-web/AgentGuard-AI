#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " Starting AgentGuard AI - Vertical Slice (5 Processes)    "
echo "=========================================================="

# Ensure tools database is seeded
python3 -c "from tools.db import init_tools_db; init_tools_db()"

# Kill background processes on exit
cleanup() {
    echo "Stopping all AgentGuard AI processes..."
    kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 1. Guard Service (:8001)
echo "Starting Guard service on port 8001..."
env -i PATH="$PATH" PYTHONPATH="." $(cat .env.guard | xargs) python3 -m uvicorn guard.main:app --port 8001 --host 0.0.0.0 &

# 2. Execution Gateway (:8002)
echo "Starting Execution Gateway on port 8002..."
env -i PATH="$PATH" PYTHONPATH="." $(cat .env.gateway | xargs) python3 -m uvicorn gateway.main:app --port 8002 --host 0.0.0.0 &

# Security check: verify agent processes cannot see secrets
if env -i PATH="$PATH" PYTHONPATH="." $(cat .env.agents | xargs) env | grep -qE "SERVICE_KEY|AUDIT_HMAC_KEY|TOOL_CREDENTIAL"; then
    echo "Security violation: Agent runtime environment contains Guard/Gateway secrets!"
    exit 1
fi

# 3. Department Agents Runtime (:8003)
echo "Starting Department Agents on port 8003..."
env -i PATH="$PATH" PYTHONPATH="." $(cat .env.agents | xargs) python3 -m uvicorn agents.main:app --port 8003 --host 0.0.0.0 &

# 4. Operator Demo Service (:8004)
echo "Starting Operator Demo service on port 8004..."
env -i PATH="$PATH" PYTHONPATH="." $(cat .env.demo | xargs) python3 -m uvicorn demo.main:app --port 8004 --host 0.0.0.0 &

# 5. Dashboard (:5173)
echo "Starting Governance Dashboard on port 5173..."
cd dashboard && npm run dev -- --host 127.0.0.1 --port 5173 &

wait
