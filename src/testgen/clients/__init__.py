"""Client factory: select backend by name."""
from __future__ import annotations
from testgen.clients.base import LLMClient, LLMError, LLMResponse  # noqa: F401


def get_client(backend: str, model: str, cache_dir=None) -> LLMClient:
    if backend == "fake":
        from testgen.clients.fake_client import FakeLLMClient
        return FakeLLMClient()
    if backend == "openai":
        from testgen.clients.openai_client import OpenAIClient
        return OpenAIClient(model=model, cache_dir=cache_dir)
    if backend == "openrouter":
        from testgen.clients.openrouter_client import OpenRouterClient
        return OpenRouterClient(model=model, cache_dir=cache_dir)
    if backend == "vllm":
        from testgen.clients.vllm_client import VLLMClient
        return VLLMClient(model=model, cache_dir=cache_dir)
    if backend == "hf":
        from testgen.clients.hf_client import HFInferenceClient
        return HFInferenceClient(model=model)
    raise ValueError(f"Unknown backend: {backend!r}. Choose: fake, openai, openrouter, vllm, hf")
