"""Azure OpenAI client wrapper with function calling support."""
import logging
from typing import AsyncIterator

from openai import AsyncAzureOpenAI

from pagecraft.config import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: Settings):
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=60.0,
        )
        self._deployment = settings.azure_openai_deployment

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        """Send a chat completion request and return the full response.

        Args:
            messages: OpenAI-format message list
            tools: OpenAI-format tool definitions

        Returns:
            The response message dict with content and/or tool_calls
        """
        kwargs = {
            "model": self._deployment,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        logger.info(f"LLM request: {len(messages)} messages, {len(tools or [])} tools")
        response = await self._client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        logger.info(
            f"LLM response: content={'yes' if message.content else 'no'}, "
            f"tool_calls={len(message.tool_calls) if message.tool_calls else 0}"
        )
        return message
