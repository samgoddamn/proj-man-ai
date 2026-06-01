"""Provideroberoende LLM-abstraktion med structured output och retry.

Mål:
  * Byt OpenAI <-> Anthropic utan att röra agent-logiken.
  * Tvinga giltig JSON via structured output / tool-use + Pydantic-validering.
  * Vid valideringsfel: retry MED felet inmatat i prompten (inte blind retry),
    så modellen kan rätta sig.
  * Prompt caching: systemprompt + projektbrief återanvänds i varje nod → cacha dem.
"""

from __future__ import annotations

import json
import os
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)


class SchemaRetryExhausted(RuntimeError):
    """Modellen lyckades inte producera giltig JSON inom max antal försök."""

    def __init__(self, schema_name: str, last_error: str | None) -> None:
        super().__init__(
            f"Kunde inte få giltig {schema_name} från modellen: {last_error}"
        )
        self.schema_name = schema_name
        self.last_error = last_error


class LLMClient(Protocol):
    """Minimal yta som varje provider måste implementera."""

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[TModel],
        cache_system: bool = True,
    ) -> TModel:
        """Anropa modellen och returnera en validerad instans av `schema`.

        Implementationen ansvarar för att be modellen om JSON enligt
        `schema.model_json_schema()` och validera svaret.
        """
        ...


async def call_structured(
    client: LLMClient,
    *,
    system: str,
    user: str,
    schema: type[TModel],
    max_retries: int = 2,
) -> TModel:
    """Anropa `client.structured` med self-healing retry på schema-fel."""
    last_err: str | None = None
    for attempt in range(max_retries + 1):
        prompt = (
            user
            if attempt == 0
            else (
                f"{user}\n\n"
                f"Ditt förra svar var ogiltigt: {last_err}\n"
                f"Returnera JSON som EXAKT matchar det begärda schemat."
            )
        )
        try:
            return await client.structured(
                system=system, user=prompt, schema=schema, cache_system=True
            )
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = str(e)
    raise SchemaRetryExhausted(schema.__name__, last_err)


# --------------------------------------------------------------------------- #
# Anthropic-implementation (tool-use för garanterad JSON + prompt caching)
# --------------------------------------------------------------------------- #


class AnthropicClient:
    def __init__(self, model: str = "claude-opus-4-8") -> None:
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = model

    async def structured(
        self, *, system, user, schema, cache_system=True
    ):
        tool = {
            "name": "emit",
            "description": f"Returnera resultatet som {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }
        system_blocks = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            system=system_blocks,
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit"},
            messages=[{"role": "user", "content": user}],
        )
        block = next(b for b in msg.content if b.type == "tool_use")
        return schema.model_validate(block.input)


# --------------------------------------------------------------------------- #
# OpenAI-implementation (structured outputs via response_format=Pydantic)
# --------------------------------------------------------------------------- #


class OpenAIClient:
    """Använder SDK:ns parse-hjälpare: Pydantic-modellen skickas som response_format
    och OpenAI genererar ett strikt JSON-schema + validerar svaret åt oss.

    Prompt caching sker automatiskt hos OpenAI för stabila prefix > ~1024 tokens
    (systemprompt + brief ligger först), så `cache_system` behövs inte men accepteras
    för att uppfylla LLMClient-protokollet.
    """

    def __init__(self, model: str = "gpt-4o-2024-08-06") -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._model = model

    async def structured(self, *, system, user, schema, cache_system=True):
        completion = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema,
        )
        msg = completion.choices[0].message
        if msg.refusal:
            raise ValueError(f"Modellen vägrade svara: {msg.refusal}")
        if msg.parsed is None:
            raise ValueError("Tomt strukturerat svar från OpenAI")
        return msg.parsed


def get_llm() -> LLMClient:
    """Fabrik styrd av env (LLM_PROVIDER=anthropic|openai)."""
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        return AnthropicClient(model=os.getenv("LLM_MODEL", "claude-opus-4-8"))
    if provider == "openai":
        return OpenAIClient(model=os.getenv("LLM_MODEL", "gpt-4o-2024-08-06"))
    raise NotImplementedError(f"Provider '{provider}' saknar implementation.")
