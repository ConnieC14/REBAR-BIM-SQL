"""
LLM provider configuration shared by all agents.

Set in .env:
    LLM_PROVIDER  "anthropic" (default), "openai", or "ollama" (local, free)
    LLM_MODEL     overrides the provider's default model
    LLM_EFFORT    optional Claude effort level (low | medium | high | xhigh | max)
    LLM_BASE_URL  optional OpenAI-compatible endpoint (defaults to the local
                  Ollama server for the "ollama" provider)
"""
import os
import time
from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from utils.tracing import record

load_dotenv()

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "openai": "gpt-3.5-turbo",
    "ollama": "qwen2.5-coder:7b",
}
OLLAMA_BASE_URL = "http://localhost:11434/v1"

# Claude models that support the server-side refusal fallback ("default" routing)
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5",
                   "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_anthropic_client = None


def get_provider() -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use one of {list(DEFAULT_MODELS)}.")
    return provider


def get_model() -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODELS[get_provider()]


def get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def claude_request_options() -> dict:
    """
    Extra request parameters for Claude calls: the refusal fallback on
    models that support it, and the effort level if LLM_EFFORT is set.
    """
    options = {}
    if get_model() in FALLBACK_MODELS:
        options["betas"] = [FALLBACK_BETA]
        options["fallbacks"] = "default"
    effort = os.getenv("LLM_EFFORT")
    if effort:
        options["output_config"] = {"effort": effort}
    return options


def record_claude_usage(response, purpose: str, latency_ms: float):
    """
    Records token usage of a Claude response in the active trace (if any).
    """
    usage = response.usage
    record("llm_call", purpose=purpose, model=get_model(),
           tokens_in=usage.input_tokens, tokens_out=usage.output_tokens,
           cache_read=getattr(usage, "cache_read_input_tokens", 0) or 0,
           cache_write=getattr(usage, "cache_creation_input_tokens", 0) or 0,
           stop_reason=response.stop_reason, latency_ms=round(latency_ms))


class TraceCallbackHandler(BaseCallbackHandler):
    """
    Records token usage of LangChain chat model calls in the active trace.
    """

    def __init__(self, purpose: str):
        self.purpose = purpose
        self.started = None

    def on_chat_model_start(self, *args, **kwargs):
        self.started = time.time()

    def on_llm_end(self, response, **kwargs):
        usage = {}
        try:
            usage = response.generations[0][0].message.usage_metadata or {}
        except (IndexError, AttributeError):
            pass
        latency_ms = (time.time() - self.started) * 1000 if self.started else None
        record("llm_call", purpose=self.purpose, model=get_model(),
               tokens_in=usage.get("input_tokens", 0),
               tokens_out=usage.get("output_tokens", 0),
               cache_read=0, cache_write=0, latency_ms=latency_ms and round(latency_ms))


def get_openai_chat_model(purpose: str = "orchestrator"):
    """
    LangChain chat model for OpenAI or any OpenAI-compatible server (Ollama).
    """
    from langchain_openai import ChatOpenAI
    base_url = os.getenv("LLM_BASE_URL") or \
        (OLLAMA_BASE_URL if get_provider() == "ollama" else None)
    # Local servers ignore the key, but the client requires one
    api_key = os.getenv("OPENAI_API_KEY") or ("ollama" if base_url else None)
    return ChatOpenAI(model=get_model(), temperature=0,
                      base_url=base_url, api_key=api_key,
                      callbacks=[TraceCallbackHandler(purpose)])


def complete(prompt: str, system: str = None, max_tokens: int = 16000,
             purpose: str = "completion") -> str:
    """
    Sends a single prompt to the configured LLM and returns the text reply.
    """
    if get_provider() == "anthropic":
        kwargs = {"system": system} if system else {}
        started = time.time()
        response = get_anthropic_client().beta.messages.create(
            model=get_model(),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
            **claude_request_options(),
        )
        record_claude_usage(response, purpose, (time.time() - started) * 1000)
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Model declined the request: {response.stop_details}")
        return "".join(b.text for b in response.content if b.type == "text").strip()

    messages = ([{"role": "system", "content": system}] if system else []) + \
        [{"role": "user", "content": prompt}]
    return get_openai_chat_model(purpose).invoke(messages).content.strip()
