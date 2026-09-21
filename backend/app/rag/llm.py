"""
LLM generation, provider-configurable via settings.LLM_PROVIDER.

- "mock": deterministic, offline, non-generative — synthesizes an answer
  directly from the supplied context blocks (no fabrication possible by
  construction). Safe default for pilot/tests with no network/API key.
- "anthropic": real grounded generation via the Anthropic API. Requires
  LLM_API_KEY to be set via environment (never hardcoded here).
"""
from abc import ABC, abstractmethod

from app.core.config import settings

GROUNDING_SYSTEM_PROMPT = (
    "You are a UDS (ISO 14229) diagnostic engineering assistant. Answer the "
    "engineer's question using ONLY the approved source context provided below. "
    "Do not use outside knowledge. Do not invent UDS service IDs, subfunctions, "
    "DIDs, RIDs, NRC meanings, or OEM-specific values that are not present in the "
    "context. If the context does not contain enough information to answer, say "
    "so explicitly rather than guessing. This is engineering decision-support "
    "only — never suggest or imply automatic execution against a real ECU."
)


class LLMProviderError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, question: str, context_blocks: list[str]) -> str:
        """Return an answer to `question`, grounded only in `context_blocks`."""


class MockLLMProvider(LLMProvider):
    """
    Deterministic, non-generative provider: stitches the retrieved context
    into a clearly-labeled answer without adding any information beyond
    what was supplied. Used as the offline pilot/test default.
    """

    def generate(self, question: str, context_blocks: list[str]) -> str:
        if not context_blocks:
            return "Evidence Not Found. Review Required."
        joined = "\n\n".join(context_blocks)
        return (
            f"Based on the approved source material provided:\n\n{joined}\n\n"
            "(This is a mock, non-generative response used for offline pilot/testing; "
            "it reflects only the retrieved context above and adds no outside information.)"
        )


class AnthropicLLMProvider(LLMProvider):
    """Real grounded generation via the Anthropic API."""

    def __init__(self, model: str, api_key: str):
        if not api_key:
            raise LLMProviderError(
                "LLM_API_KEY is not configured. Set it via environment variables "
                "before selecting LLM_PROVIDER=anthropic."
            )
        import anthropic  # lazy import

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(self, question: str, context_blocks: list[str]) -> str:
        context = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no context retrieved)"
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1000,
                system=GROUNDING_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Approved source context:\n\n{context}\n\nEngineer's question:\n{question}",
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001 — surface any SDK/network failure uniformly
            raise LLMProviderError(f"LLM request failed: {exc}") from exc

        text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(text_parts).strip()


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        return MockLLMProvider()
    if provider == "anthropic":
        return AnthropicLLMProvider(model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY)
    raise LLMProviderError(f"Unknown LLM_PROVIDER: {provider!r}. Supported: mock, anthropic")
