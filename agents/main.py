import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.runtime import AgentRuntime

app = FastAPI(title="AgentGuard AI - Department Agents Runtime")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




class AgentRunRequest(BaseModel):
    request_text: str
    source_type: str = "user"
    content_excerpt: Optional[str] = None
    direct_proposal: Optional[Dict[str, Any]] = None


@app.post("/agents/{department}/run")
async def run_agent(department: str, body: AgentRunRequest):
    valid_deps = ["analytics", "database", "coding", "finance", "devops"]
    if department not in valid_deps:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown department '{department}'. Supported: {valid_deps}",
        )

    runtime = AgentRuntime(department=department)
    result = await runtime.propose_and_execute(
        request_text=body.request_text,
        source_type=body.source_type,
        content_excerpt=body.content_excerpt,
        direct_proposal=body.direct_proposal,
    )
    return result


@app.get("/agents/departments")
async def list_departments():
    return {
        "departments": [
            {"id": "analytics", "agent_id": "analytics-agent-01"},
            {"id": "database", "agent_id": "database-agent-01"},
            {"id": "coding", "agent_id": "coding-agent-01"},
            {"id": "finance", "agent_id": "finance-agent-01"},
            {"id": "devops", "agent_id": "devops-agent-01"},
        ]
    }
