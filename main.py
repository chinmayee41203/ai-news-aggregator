"""Entry point: run the full daily pipeline.

    uv run main.py              collect → rank → summarize → email
    uv run main.py --no-send    same, but write data/digest_preview.html instead of emailing
"""

from app.daily_runner import main

if __name__ == "__main__":
    main()
