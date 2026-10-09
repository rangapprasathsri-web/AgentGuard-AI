import asyncio
import os
from dotenv import load_dotenv

# Load env file
load_dotenv(".env.guard")
os.environ["LLM_MODE"] = "live"

from common.llm_client import LLMClient
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class AnalyzerResponseSchema(BaseModel):
    consequences: List[str]
    suspicion_flags: List[str]
    confidence: float
    recommended_risk_delta: int
    status: Optional[str] = "success"

class ProposerResponseSchema(BaseModel):
    action: str
    target: str
    params: Dict[str, Any]
    explanation: str

async def run_smoke_test():
    print("Initializing LLMClient in live mode...")
    client = LLMClient(mode="live", timeout=15.0)
    
    print("\n1. Testing Analyzer (Gemini / OpenRouter)...")
    system_prompt = "You are a risk analyzer. Output JSON in the format: {'consequences': [], 'suspicion_flags': [], 'confidence': 0.9, 'recommended_risk_delta': 5}"
    user_prompt = "The user is attempting to CREATE a new record in payments_api with amount 50000."
    
    try:
        resp, provider, p_hash = await client.complete(
            system=system_prompt,
            user_prompt=user_prompt,
            schema_model=AnalyzerResponseSchema
        )
        print(f"Analyzer Response (Provider: {provider}): {resp}")
    except Exception as e:
        print(f"Analyzer failed: {e}")
        
    print("\n2. Testing Proposer (Agent / OpenRouter)...")
    proposer_system = "You are a finance agent. Choose an action from CREATE, READ, UPDATE. Output JSON with action, target, params, explanation."
    proposer_user = "Create a payment for customer 123 for 500 dollars."
    
    try:
        resp, provider, p_hash = await client.complete(
            system=proposer_system,
            user_prompt=proposer_user,
            schema_model=ProposerResponseSchema
        )
        print(f"Proposer Response (Provider: {provider}): {resp}")
    except Exception as e:
        print(f"Proposer failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
