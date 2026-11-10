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
        "education": [
            "F-1 student visa rules and changes",
            "OPT and STEM OPT",
            "H-1B visa",
            "visa and immigration policy affecting international students and workers in the US",
            "news for international master's students in the US (New Jersey)",
        ],
    },
}

STORIES_PER_SECTION = 5  # "4 to 5 stories per section"

# Stories mainly about India, when there are any that day. Education & Visas is
# about US rules, so no India minimum there.
MIN_INDIA_BY_SECTION = {"tech": 2, "business": 2, "politics": 2, "education": 0}
