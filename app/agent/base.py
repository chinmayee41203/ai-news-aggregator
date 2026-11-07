"""Every Gemini call goes through here: structured (Pydantic) output,
spacing between requests for the free tier, retries on rate limits, and a
backup model (separate free quota) when the main one keeps failing."""

import logging
import os
import re
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

import app.config  # noqa: F401  (loads .env)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {429, 500, 503}
# After retries, these move on to the backup model (404 = model not available).
FALLBACK_CODES = RETRYABLE_CODES | {404}


def low_thinking_config(model: str) -> types.ThinkingConfig:
    """Least "thinking" each model generation accepts (faster, fewer tokens).

    Gemini 2.x takes thinking_budget=0; Gemini 3.x+ rejects that and takes
    thinking_level="minimal" instead.
    """
    match = re.search(r"gemini-(\d+)", model)
    if match and int(match.group(1)) <= 2:
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level="minimal")


class GeminiAgent:
    # Free tier allows a limited number of requests per minute; keep a gap between calls.
    min_interval = float(os.getenv("GEMINI_MIN_INTERVAL_SECONDS", "6"))
    _last_call = 0.0  # shared by all agents in this process

    def __init__(self, model: str | None = None, fallback_model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        # v1beta: the plain v1 API rejects system instructions.
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.fallback_model = fallback_model or os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")

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
        temperature: float | None = 0.2,
        think: bool = False,
        max_attempts: int = 4,
    ) -> T:
        """Ask Gemini for JSON matching `schema` and return it as a Pydantic object.

        think=False keeps "thinking" to the minimum — fine for sorting and
        summarizing. think=True uses the model's default.
        """
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)

        for i, model in enumerate(models):
            config = types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=None if think else low_thinking_config(model),
            )
            try:
                return self._call_with_retries(model, prompt, schema, config, max_attempts)
            except errors.APIError as exc:
                if i + 1 < len(models) and exc.code in FALLBACK_CODES:
                    log.warning("Gemini %s failed (%s); switching to backup model %s", model, exc.code, models[i + 1])
                    continue
                raise
        raise RuntimeError("unreachable")

    def _call_with_retries(self, model: str, prompt: str, schema: type[T], config, max_attempts: int) -> T:
        for attempt in range(1, max_attempts + 1):
            self._wait_for_slot()
            try:
                response = self.client.models.generate_content(model=model, contents=prompt, config=config)
            except errors.APIError as exc:
                if exc.code in RETRYABLE_CODES and attempt < max_attempts:
                    delay = 15 * attempt
                    log.warning("Gemini %s %s (attempt %d/%d), retrying in %ds", model, exc.code, attempt, max_attempts, delay)
                    time.sleep(delay)
                    continue
                raise

            if isinstance(response.parsed, schema):
                return response.parsed
            return schema.model_validate_json(response.text)
        raise RuntimeError("unreachable")
