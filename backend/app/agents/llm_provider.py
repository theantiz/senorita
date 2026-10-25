from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Type, TypeVar

from google.genai import types
from pydantic import BaseModel

from app.agents.gemini_client import get_client
from app.core.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_instruction: str = "", tools: list[Any] | None = None) -> str:
        """Generate unstructured text from the model."""
        pass

    @abstractmethod
    async def generate_structured(self, prompt: str, schema: Type[T], system_instruction: str = "") -> T:
        """Generate a structured Pydantic object from the model."""
        pass

    @abstractmethod
    async def stream(self, prompt: str, system_instruction: str = "") -> AsyncIterator[str]:
        """Stream unstructured text chunks from the model."""
        pass


class GeminiProvider(LLMProvider):
    async def _execute_with_retries(self, func, max_retries: int = 3):
        import asyncio
        import logging

        logger = logging.getLogger("senorita.llm_provider")
        delay = 2.0
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                err_str = str(e)
                if (
                    any(x in err_str for x in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"])
                    and attempt < max_retries - 1
                ):
                    logger.warning(
                        f"Transient model error in LLM provider ({err_str[:60]}), retrying ({attempt + 1}/{max_retries}) in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise

    async def generate(self, prompt: str, system_instruction: str = "", tools: list[Any] | None = None) -> str:
        client = get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            tools=tools or None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True) if tools else None,
        )
        response = await self._execute_with_retries(
            lambda: client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
        )
        return response.text or ""

    async def generate_structured(self, prompt: str, schema: Type[T], system_instruction: str = "") -> T:
        client = get_client()

        json_schema = schema.model_json_schema()

        def _sanitize_schema(d):
            if isinstance(d, dict):
                d.pop("additionalProperties", None)
                for v in d.values():
                    _sanitize_schema(v)
            elif isinstance(d, list):
                for item in d:
                    _sanitize_schema(item)

        _sanitize_schema(json_schema)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=json_schema,
            system_instruction=system_instruction or None,
            temperature=0.1,
        )
        response = await self._execute_with_retries(
            lambda: client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
        )
        text = response.text or "{}"
        return schema.model_validate_json(text)

    async def stream(self, prompt: str, system_instruction: str = "") -> AsyncIterator[str]:
        client = get_client()
        config = types.GenerateContentConfig(system_instruction=system_instruction or None)
        response_stream = await client.aio.models.generate_content_stream(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=config,
        )

        async def _generator():
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text

        return _generator()
