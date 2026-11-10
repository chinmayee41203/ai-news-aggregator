"""Check which database the app talks to and that it is reachable.

    uv run python -m app.database.check_connection                 # uses ENVIRONMENT from .env
    uv run python -m app.database.check_connection --production    # force the Neon database
"""

import argparse
import os
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the database connection.")
    parser.add_argument("--production", action="store_true", help="check the production (Neon) database")
    args = parser.parse_args()
    if args.production:
        os.environ["ENVIRONMENT"] = "production"

    # Imported after setting ENVIRONMENT, because the engine is built on import.
    from sqlalchemy import text

    from app.database.connection import describe_database, engine

    print(f"Database: {describe_database()}")
    for attempt in range(1, 4):
        try:
            with engine.connect() as conn:
                version = conn.execute(text("select version()")).scalar_one()
            print(f"Connected ✓  ({version.split(',')[0]})")
            return
        except Exception as exc:
            print(f"Attempt {attempt} failed: {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
            time.sleep(5)
    sys.exit(1)


if __name__ == "__main__":
    main()
