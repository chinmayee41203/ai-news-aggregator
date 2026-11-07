"""Who the digest is for. The curator ranks stories against these interests."""

USER_PROFILE = {
    "name": "Chinmayee",
    "interests": {
        "tech": [
            "AI",
            "startups",
            "major scams or scandals happening in big industries",
        ],
        "business": [
            "US stock market",
            "Indian stock market",
            "big tech companies",
            "the economy",
        ],
        "politics": [
            "Indian national politics",
            "US politics",
            "world affairs",
        ],
    },
}

STORIES_PER_SECTION = 5  # "4 to 5 stories per section"
MIN_INDIA_PER_SECTION = 2  # stories mainly about India, when there are any that day
