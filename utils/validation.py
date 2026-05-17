"""Validation helpers for pipeline context and article content."""
import re
from utils.seo_utils import count_words, extract_headings


REQUIRED_CONTEXT_KEYS = ("topic", "primary_keyword")


def validate_context(context: dict) -> tuple[bool, list[str]]:
    """Check that the pipeline context contains all required keys with non-empty values.

    Args:
        context: The shared pipeline context dict.

    Returns:
        (is_valid, list_of_errors) where list_of_errors is empty when valid.
    """
    errors: list[str] = []
    for key in REQUIRED_CONTEXT_KEYS:
        if key not in context:
            errors.append(f"Missing required key: '{key}'")
        elif not context[key]:
            errors.append(f"Required key '{key}' is empty")
    return (len(errors) == 0, errors)


def validate_article(content: str, min_words: int = 1500) -> tuple[bool, list[str]]:
    """Validate a finished article against quality thresholds.

    Checks:
    - Word count >= min_words
    - At least 3 headings present
    - Content is non-empty

    Args:
        content: The raw markdown article text.
        min_words: Minimum acceptable word count (default 1500).

    Returns:
        (is_valid, list_of_errors) where list_of_errors is empty when valid.
    """
    errors: list[str] = []

    if not content or not content.strip():
        errors.append("Article content is empty")
        return (False, errors)

    word_count = count_words(content)
    if word_count < min_words:
        errors.append(f"Article too short: {word_count} words (minimum {min_words})")

    headings = extract_headings(content)
    if len(headings) < 3:
        errors.append(f"Too few headings: {len(headings)} found (minimum 3 required)")

    return (len(errors) == 0, errors)


def sanitize_filename(name: str) -> str:
    """Replace spaces and special characters with underscores to create a safe filename.

    Args:
        name: Raw string (e.g. an article topic).

    Returns:
        A filesystem-safe string using only alphanumerics, hyphens, and underscores.
    """
    sanitized = re.sub(r'[^\w\-]', '_', name)
    # Collapse multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')
