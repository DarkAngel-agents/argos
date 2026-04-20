"""
ARGOS LLM Providers - Pure async wrappers for LLM API calls.

Used by agent/loop.py and (future) chat.py refactor.
No FastAPI dependencies, no DB access, no pool. Pure I/O.

Session 2 MVP: Claude only. Grok/Ollama come later.
"""
import os
import asyncio
import anthropic
from typing import Optional


# Default model - override via ARGOS_AGENT_MODEL env var.
# Fallback matches chat.py SONNET constant for consistency with live chat.
DEFAULT_MODEL = os.getenv("ARGOS_AGENT_MODEL", "claude-sonnet-4-6")

# Retry policy for transient errors (529 overloaded, 429 rate limit, connection).
# Exponential backoff capped at 120s, max 10 attempts.
# Worst case: 10+20+40+80+120+120+120+120+120+120 = 870s (~14.5 min).
MAX_RETRIES = 10
BASE_DELAY = 10
MAX_DELAY = 120


class LLMError(Exception):
    """Raised on fatal LLM call failure (non-retryable or retries exhausted)."""
    pass


def _get_client() -> anthropic.AsyncAnthropic:
    """
    Build AsyncAnthropic client from env.
    Supports both ANTHROPIC_API_KEY and legacy CLAUDE_TOKEN.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_TOKEN")
    if not api_key:
        raise LLMError("No API key found (ANTHROPIC_API_KEY or CLAUDE_TOKEN)")
    return anthropic.AsyncAnthropic(api_key=api_key)


def _backoff_delay(attempt: int) -> int:
    """Exponential backoff capped at MAX_DELAY."""
    return min(BASE_DELAY * (2 ** attempt), MAX_DELAY)


async def call_claude(
    messages: list,
    tools: Optional[list] = None,
    system: Optional[str] = None,
    max_tokens: int = 8096,
    model: Optional[str] = None,
) -> dict:
    """
    Call Claude messages API with retry on transient errors.

    Retries on: 529 overloaded, 429 rate limit (respects retry-after header),
    connection errors. Fails fast on other errors.

    Args:
        messages: list of {"role": ..., "content": ...} dicts
        tools: optional list of tool definitions
        system: optional system prompt string
        max_tokens: max output tokens (default 8096)
        model: override model (default DEFAULT_MODEL)

    Returns:
        dict with standardized shape:
        {
            "content_blocks": [...],     # raw content blocks from Anthropic SDK
            "stop_reason": str,          # "end_turn" | "tool_use" | "max_tokens" | ...
            "usage": {
                "input_tokens": int,
                "output_tokens": int,
            },
            "model": str,                # actual model used
        }

    Raises:
        LLMError: on fatal error or retries exhausted.
    """
    client = _get_client()
    chosen_model = model or DEFAULT_MODEL

    kwargs = {
        "model": chosen_model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    if system:
        kwargs["system"] = system

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.messages.create(**kwargs)
            return {
                "content_blocks": response.content,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "model": response.model,
            }
        # RateLimitError must come BEFORE APIStatusError (inherits from it).
        # Python except matches the first block that catches - reordering breaks 429 handling.
        except anthropic.RateLimitError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                # Respect retry-after header if present, else fall back to exponential backoff.
                retry_after = 0
                try:
                    retry_after = int(e.response.headers.get("retry-after", 0))
                except (AttributeError, ValueError, TypeError):
                    retry_after = 0
                delay = min(retry_after, MAX_DELAY) if retry_after > 0 else _backoff_delay(attempt)
                print(f"[providers] 429 rate limit, retry {attempt+1}/{MAX_RETRIES} in {delay}s")
                await asyncio.sleep(delay)
                continue
            raise LLMError(f"Rate limit exhausted after {MAX_RETRIES} retries: {e}") from e
        except anthropic.APIStatusError as e:
            last_error = e
            if e.status_code == 529 and attempt < MAX_RETRIES - 1:
                delay = _backoff_delay(attempt)
                print(f"[providers] 529 overloaded, retry {attempt+1}/{MAX_RETRIES} in {delay}s")
                await asyncio.sleep(delay)
                continue
            # Non-529 API error or retries exhausted
            raise LLMError(f"Anthropic API error (status={e.status_code}): {e}") from e
        except anthropic.APIConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = _backoff_delay(attempt)
                print(f"[providers] connection error, retry {attempt+1}/{MAX_RETRIES} in {delay}s")
                await asyncio.sleep(delay)
                continue
            raise LLMError(f"Anthropic connection error after {MAX_RETRIES} retries: {e}") from e
        except Exception as e:
            # Unknown error - no retry, fail fast
            raise LLMError(f"Unexpected LLM error: {e}") from e

    # Should not reach here, but safety net
    raise LLMError(f"All {MAX_RETRIES} retries exhausted. Last error: {last_error}")
