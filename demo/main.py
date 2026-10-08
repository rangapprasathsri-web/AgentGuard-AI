import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from common.clock import clock
from demo.runner import ScenarioRunner

if os.getenv("DEMO_MODE", "false").lower() != "true":
    # In live execution demo process requires DEMO_MODE
    pass

app = FastAPI(title="AgentGuard AI - Operator Demo Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runner = ScenarioRunner(
    guard_url=os.getenv("GUARD_URL", "http://localhost:8001"),
    gateway_url=os.getenv("GATEWAY_URL", "http://localhost:8002"),
    agents_url=os.getenv("AGENTS_URL", "http://localhost:8003"),
)


@app.post("/demo/run/{scenario_id}")
async def run_scenario_endpoint(scenario_id: int):
    try:
        result = await runner.run_scenario(scenario_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/demo/clock")
async def adjust_clock(offset_seconds: float = Query(...)):
    clock.set_offset(offset_seconds)
    return {"status": "clock_updated", "now_iso": clock.now_iso()}


@app.post("/demo/reset")
async def reset_demo_state():
    from tools.db import reseed_tools_db
    reseed_tools_db()
    clock.reset()
    return {"status": "demo_environment_reset_complete"}
