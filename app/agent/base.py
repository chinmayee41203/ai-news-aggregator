"""Every Gemini call goes through here: structured (Pydantic) output,
spacing between requests for the free tier, and retries on rate limits."""

import logging
import os
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

import app.config  # noqa: F401  (loads .env)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {429, 500, 503}


class GeminiAgent:
    # Free tier allows a limited number of requests per minute; keep a gap between calls.
    min_interval = float(os.getenv("GEMINI_MIN_INTERVAL_SECONDS", "6"))
    _last_call = 0.0  # shared by all agents in this process

    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        # v1beta: the plain v1 API rejects system instructions.
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _wait_for_slot(self) -> None:
        wait = GeminiAgent._last_call + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        GeminiAgent._last_call = time.monotonic()

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        temperature: float = 0.2,
        thinking_budget: int | None = 0,
        max_attempts: int = 4,
    ) -> T:
        """Ask Gemini for JSON matching `schema` and return it as a Pydantic object.

        thinking_budget=0 turns off "thinking" (faster, fewer tokens) — fine for
        sorting/summarizing. Pass None to use the model's default.
        """
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=(
                types.ThinkingConfig(thinking_budget=thinking_budget)
                if thinking_budget is not None
                else None
            ),
        )

        for attempt in range(1, max_attempts + 1):
            self._wait_for_slot()
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
            except errors.APIError as exc:
                if exc.code in RETRYABLE_CODES and attempt < max_attempts:
                    delay = 15 * attempt
                    log.warning("Gemini %s (attempt %d/%d), retrying in %ds", exc.code, attempt, max_attempts, delay)
                    time.sleep(delay)
                    continue
                raise

            if isinstance(response.parsed, schema):
                return response.parsed
            return schema.model_validate_json(response.text)

        raise RuntimeError("unreachable")
