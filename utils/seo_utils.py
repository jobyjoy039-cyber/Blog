"""SEO utility functions — pure helpers, no Claude calls."""
import re


def count_words(text: str) -> int:
    """Count total words in text."""
    return len(text.split())


def calculate_keyword_density(text: str, keyword: str) -> float:
    """Return keyword occurrences / total words (as a fraction, e.g. 0.02 = 2%)."""
    total = count_words(text)
    if total == 0:
        return 0.0
    keyword_lower = keyword.lower()
    text_lower = text.lower()
    occurrences = len(re.findall(r'\b' + re.escape(keyword_lower) + r'\b', text_lower))
    return occurrences / total


def extract_headings(text: str) -> list[dict]:
    """Extract H1/H2/H3 headings from markdown text.

    Returns a list of dicts with keys: level (int), text (str).
    """
    pattern = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
    headings = []
    for match in pattern.finditer(text):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        headings.append({"level": level, "text": heading_text})
    return headings


def extract_meta_info(content: str) -> dict:
    """Extract title and description from content by looking for common patterns.

    Checks YAML frontmatter first, then falls back to the first H1 and first paragraph.
    Returns {"title": ..., "description": ...}.
    """
    title = ""
    description = ""

    # Try YAML frontmatter
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if frontmatter_match:
        fm = frontmatter_match.group(1)
        title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
        desc_match = re.search(r'^description:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
        if desc_match:
            description = desc_match.group(1).strip()

    # Fall back to first H1
    if not title:
        h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()

    # Fall back to first non-empty paragraph (skip headings and frontmatter)
    if not description:
        body = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', body) if p.strip()]
        for para in paragraphs:
            if not para.startswith('#'):
                description = para[:160]
                break

    return {"title": title, "description": description}


def check_keyword_in_headings(text: str, keyword: str) -> bool:
    """Return True if the keyword appears (case-insensitive) in any heading."""
    headings = extract_headings(text)
    keyword_lower = keyword.lower()
    return any(keyword_lower in h["text"].lower() for h in headings)
