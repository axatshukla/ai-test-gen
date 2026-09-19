"""vLLM: reuses OpenAIClient pointed at a local endpoint."""
from __future__ import annotations
from testgen.clients.openai_client import OpenAIClient


class VLLMClient(OpenAIClient):
    """Self-hosted vLLM. api_key required by SDK but ignored by vLLM."""
    def __init__(self, model: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
                 base_url: str = "http://localhost:8000/v1", cache_dir=None):
        super().__init__(model=model, base_url=base_url, api_key="not-needed", cache_dir=cache_dir)
