import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Type
import httpx
from pydantic import BaseModel
from common.canonical import compute_sha256


class MockLLM:
    """
    Deterministic scripted mock LLM provider for tests and offline execution.
    Never selected implicitly in production mode (requires LLM_MODE=mock).
    """

    def __init__(self):
        self.scripted_responses: Dict[str, Dict[str, Any]] = {}
        self.call_history: List[Dict[str, Any]] = []

    def register_response(self, keyword_or_key: str, response_dict: Dict[str, Any]) -> None:
        self.scripted_responses[keyword_or_key] = response_dict

    def complete(self, system: str, user_prompt: str) -> Dict[str, Any]:
        self.call_history.append({"system": system, "user_prompt": user_prompt})

        # Match registered keywords
        for key, resp in self.scripted_responses.items():
            if key in user_prompt or key in system:
                return resp

        # Default fallback responses for analyzer and departments
        if "Analyzer" in system or "analyzer" in system.lower():
            if "payments_api" in user_prompt:
                return {
                    "consequences": ["Disbursement touches live payments gateway"],
                    "suspicion_flags": [],
                    "confidence": 0.95,
                    "recommended_risk_delta": 5,
                }
            elif "mystery_db" in user_prompt:
                return {
                    "consequences": ["Accessing unknown database resource"],
                    "suspicion_flags": ["unregistered_asset"],
                    "confidence": 0.85,
                    "recommended_risk_delta": 5,
                }
            else:
                return {
                    "consequences": ["Standard operational read access"],
                    "suspicion_flags": [],
                    "confidence": 0.90,
                    "recommended_risk_delta": 0,
                }

        # Proposer fallback
        return {
            "action": "READ",
            "target": "sales_db",
            "params": {"record_count": 1},
            "explanation": "Default mocked proposer action",
        }


class LLMProviderConfig:
    def __init__(self, name: str, base_url: str, api_key: str, model: str = "qwen/qwen-2.5-72b-instruct"):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.model = model


class LLMClient:
    def __init__(
        self,
        mode: Optional[str] = None,
        timeout: float = 4.0,
    ):
        self.mode = mode or os.getenv("LLM_MODE", "mock").lower()
        self.timeout = timeout
        self.mock_llm = MockLLM()
        self.providers: List[LLMProviderConfig] = self._load_providers()

    def _load_providers(self) -> List[LLMProviderConfig]:
        """Loads primary provider and failover providers from environment."""
        providers = []
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        default_model = os.getenv("LLM_MODEL", "qwen/qwen-2.5-72b-instruct")

        primary_key = os.getenv("OPENROUTER_API_KEY")
        if primary_key:
            providers.append(
                LLMProviderConfig(
                    name="openrouter_primary",
                    base_url=base_url,
                    api_key=primary_key,
                    model=default_model,
                )
            )

        # Failover pool
        for i in range(1, 8):
            key = os.getenv(f"OPENROUTER_API_KEY_FAILOVER_{i}")
            if key:
                providers.append(
                    LLMProviderConfig(
                        name=f"openrouter_failover_{i}",
                        base_url=base_url,
                        api_key=key,
                        model=default_model,
                    )
                )

        return providers

    @staticmethod
    def _strip_fences(content: str) -> str:
        """Strip markdown code fences (e.g. ```json ... ```)."""
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        return content.strip()

    async def complete(
        self,
        system: str,
        user_prompt: str,
        schema_model: Optional[Type[BaseModel]] = None,
        model_override: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], str, str]:
        """
        Completes prompt with failover across provider pool.
        Returns: (result_dict, provider_name_used, prompt_hash)
        """
        prompt_hash = compute_sha256(system + user_prompt)

        # 1. Mock mode
        if self.mode == "mock":
            resp_dict = self.mock_llm.complete(system, user_prompt)
            if schema_model:
                validated = schema_model.model_validate(resp_dict).model_dump()
                return validated, "mock", prompt_hash
            return resp_dict, "mock", prompt_hash

        # 2. Live LLM execution with provider failover
        if not self.providers:
            raise RuntimeError("No LLM providers configured in live mode")

        for provider in self.providers:
            try:
                model_name = model_override or provider.model
                headers = {
                    "Authorization": f"Bearer {provider.api_key}",
                    "Content-Type": "application/json",
                }
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ]
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.1,
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{provider.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )

                    if resp.status_code == 429 or resp.status_code >= 500:
                        # Failover to next provider
                        continue

                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    cleaned = self._strip_fences(content)

                    # Validate with JSON and Schema
                    try:
                        parsed = json.loads(cleaned)
                    except json.JSONDecodeError:
                        # Retry once with explicit json fix instruction
                        fix_payload = {
                            "model": model_name,
                            "messages": messages + [
                                {"role": "assistant", "content": content},
                                {"role": "user", "content": "Your response was not valid JSON. Return ONLY the raw JSON object, no commentary, no markdown."},
                            ],
                            "temperature": 0.1,
                        }
                        retry_resp = await client.post(
                            f"{provider.base_url}/chat/completions",
                            json=fix_payload,
                            headers=headers,
                        )
                        if retry_resp.status_code == 200:
                            retry_content = retry_resp.json()["choices"][0]["message"]["content"]
                            parsed = json.loads(self._strip_fences(retry_content))
                        else:
                            continue

                    if schema_model:
                        validated = schema_model.model_validate(parsed).model_dump()
                        return validated, provider.name, prompt_hash
                    return parsed, provider.name, prompt_hash

            except (httpx.TimeoutException, httpx.NetworkError, Exception):
                # Failover to next provider in listed order
                continue

        # All providers failed
        return None, "all_providers_failed", prompt_hash
