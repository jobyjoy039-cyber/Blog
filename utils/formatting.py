"""Formatting and output helpers for the blog writing pipeline."""
import json
import os
from datetime import datetime
from pathlib import Path

from utils.validation import sanitize_filename


def format_article_markdown(content: str, metadata: dict) -> str:
    """Wrap article content with YAML frontmatter.

    Args:
        content: The raw article markdown.
        metadata: Dict with keys: title, description, keywords (list or str), date.

    Returns:
        A string beginning with a YAML frontmatter block followed by the content.
    """
    title = metadata.get("title", "")
    description = metadata.get("description", "")
    keywords = metadata.get("keywords", [])
    date = metadata.get("date", datetime.now().strftime("%Y-%m-%d"))

    if isinstance(keywords, list):
        keywords_str = ", ".join(keywords)
    else:
        keywords_str = str(keywords)

    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f'description: "{description}"\n'
        f'keywords: "{keywords_str}"\n'
        f'date: "{date}"\n'
        "---\n\n"
    )
    return frontmatter + content


def save_output(content: str, filepath: str) -> None:
    """Write content to *filepath*, creating any missing parent directories.

    Args:
        content: Text content to write.
        filepath: Destination file path (absolute or relative).
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def format_json_report(agent_outputs: dict) -> str:
    """Pretty-print agent outputs as a formatted string.

    Args:
        agent_outputs: Dict mapping agent names to their output payloads.

    Returns:
        A human-readable multi-line string representation.
    """
    lines = ["=" * 60, "AGENT OUTPUTS REPORT", "=" * 60]
    for agent_name, output in agent_outputs.items():
        lines.append(f"\n[{agent_name}]")
        if isinstance(output, dict):
            lines.append(json.dumps(output, indent=2, default=str))
        else:
            lines.append(str(output))
        lines.append("-" * 40)
    return "\n".join(lines)


def create_output_filename(topic: str, timestamp: str) -> str:
    """Create a safe output filename from a topic string and timestamp.

    Args:
        topic: The article topic (may contain spaces and special characters).
        timestamp: A timestamp string to append (e.g. "20240101_120000").

    Returns:
        A filename string like "my_topic_20240101_120000.md".
    """
    safe_topic = sanitize_filename(topic.lower().replace(" ", "_"))[:50]
    return f"{safe_topic}_{timestamp}.md"
