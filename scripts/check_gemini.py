"""Phase 0 checkpoint: confirm the Gemini API key and model work.

Run:  uv run python scripts/check_gemini.py
"""

import os
import sys

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not api_key:
    sys.exit("GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.")

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model=model,
        contents="In one sentence, what does a news aggregator do?",
    )
    print(f"OK — {model} replied:\n{response.text}")
except Exception as exc:
    print(f"Request to '{model}' failed: {exc}\n")
    print("Flash models available to your key:")
    for m in client.models.list():
        if "flash" in m.name:
            print(" ", m.name.removeprefix("models/"))
    sys.exit(1)
