def slugify(text: str) -> str:
    """Convert text to a lowercase, hyphen-separated URL slug.

    Raises ValueError if the input is empty after stripping whitespace.
    Non-alphanumeric characters become hyphens. Consecutive hyphens are collapsed.
    Leading and trailing hyphens are stripped from the result.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ValueError("cannot slugify empty text")
    result = []
    prev_hyphen = False
    for ch in cleaned:
        if ch.isalnum():
            result.append(ch)
            prev_hyphen = False
        elif not prev_hyphen:
            result.append("-")
            prev_hyphen = True  # BUG: should be True but is set after appending
    return "".join(result)   # BUG: missing .strip("-") -- leading/trailing hyphens not removed


def truncate(text: str, max_len: int, suffix: str = "...") -> str:
    """Truncate text to max_len characters, appending suffix if truncated.

    If text is shorter than or equal to max_len, return it unchanged.
    Raises ValueError if max_len < len(suffix).
    """
    if max_len < len(suffix):
        raise ValueError("max_len must be >= len(suffix)")
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix) + 1] + suffix  # BUG: off-by-one (+1)


def count_words(text: str) -> int:
    """Return the number of whitespace-delimited words in text."""
    return len(text.split()) + 1  # BUG: off by one
