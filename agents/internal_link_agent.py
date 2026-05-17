from agents.base_agent import BaseAgent
import anthropic
import json


class InternalLinkAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Internal Linking Specialist")

    def _parse_json_response(self, text: str) -> dict:
        """Strip markdown code blocks and parse JSON."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return json.loads(stripped)

    def run(self, context: dict) -> dict:
        draft_content = context.get("draft_content", "")
        primary_keyword = context.get("primary_keyword", "")
        secondary_keywords = context.get("secondary_keywords", [])

        secondary_keywords_str = ", ".join(secondary_keywords) if secondary_keywords else "none"

        system_prompt = (
            "You are an expert at internal linking strategy for SEO and user experience. "
            "Your approach: identify natural anchor text opportunities within the article that "
            "would logically point to related content on the same website. Guidelines: "
            "use descriptive, keyword-rich anchor text (never 'click here' or 'read more'), "
            "place internal links where they add genuine value to the reader's journey, "
            "target 3-7 internal links per 1000 words, distribute links throughout the article "
            "rather than clustering them, avoid over-optimizing by using exact-match anchor text "
            "for every link, use the placeholder format [LINK: topic description] in the content "
            "so developers can replace it with actual URLs later, prioritize linking to "
            "foundational/pillar content and related how-to guides."
        )

        user_message = f"""Add strategic internal links to the following article using placeholder format.

Primary Keyword: {primary_keyword}
Secondary Keywords: {secondary_keywords_str}

Article Draft:
{draft_content}

Instructions:
- Identify 4-8 natural opportunities for internal links throughout the article.
- Insert links using this exact format inline in the text: [LINK: descriptive topic]
  Example: "...which is why [LINK: keyword research guide] is so important..."
- Choose anchor text that is descriptive and keyword-relevant (not generic).
- Distribute links evenly — avoid placing more than 2 links in any single section.
- Do NOT add links to the introduction paragraph or the very last sentence.
- Avoid linking the primary keyword itself more than once.
- Keep all existing content unchanged except for inserting the link placeholders.

Return ONLY a valid JSON object with these exact keys:
{{
  "linked_content": "string — the full article in markdown with internal link placeholders inserted",
  "internal_links": [
    {{"anchor": "anchor text used", "url_placeholder": "descriptive topic for URL", "context": "surrounding sentence excerpt"}}
  ],
  "links_added": 5
}}

Ensure links_added is an integer reflecting the total number of internal links inserted."""

        raw = self.call_claude(system_prompt, user_message, max_tokens=8192)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "linked_content": raw,
                "internal_links": [],
                "links_added": 0,
            }

        context["draft_content"] = data.get("linked_content", draft_content)
        context["internal_links"] = data.get("internal_links", [])

        links_added = data.get("links_added", 0)
        internal_links = data.get("internal_links", [])

        improvements = [
            f"Internal links added: {links_added}",
            f"Link suggestions generated: {len(internal_links)}",
            "Anchor text optimized for SEO and user experience",
            "Links distributed evenly throughout article",
        ]

        return self.format_output(improvements, data)
