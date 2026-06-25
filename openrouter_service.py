"""OpenRouter LLM client using the OpenAI-compatible API."""

import logging
from typing import Any

from openai import AsyncOpenAI
from openai import APIError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)


class OpenRouterService:
    def __init__(self, config):
        self.config = config
        self._client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.openrouter_api_key,
            default_headers={
                "HTTP-Referer": "http://localhost",
                "X-Title": "Voice Agent",
            },
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        """
        Send a chat completion request and return the response message dict.
        Handles tool_calls in the response; the caller decides how to loop.
        Raises on API errors.
        """
        kwargs: dict[str, Any] = {
            "model": self.config.openrouter_model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except (APIError, APIConnectionError, RateLimitError) as exc:
            logger.error(f"OpenRouter request failed: {exc}")
            raise

        choice = response.choices[0]
        msg = choice.message

        # Convert to plain dict for uniform handling in conversation.py
        result: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        return result

    async def close(self) -> None:
        await self._client.close()
