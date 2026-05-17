from agents.base_agent import BaseAgent
import anthropic
import json


class FinalEditorAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Final Editor")

    def _parse_json_response(self, text: str) -> dict:
        """Strip markdown code blocks and parse JSON."""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            # Remove opening fence (```json or ```)
            lines = lines[1:]
            # Remove closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return json.loads(stripped)

    def run(self, context: dict) -> dict:
        draft_content = context.get("draft_content", "")
        primary_keyword = context.get("primary_keyword", "")
        brand_voice = context.get("brand_voice", "")
        tone = context.get("tone", "conversational yet authoritative")

        system_prompt = (
            "You are a senior editor performing the final polish pass on a blog article before publication. "
            "Your editorial checklist: (1) Grammar and mechanics — fix all grammar errors, punctuation "
            "issues, spelling mistakes, and awkward phrasing; (2) Consistency — ensure consistent "
            "capitalization, hyphenation, number formatting, and terminology throughout; (3) Flow — "
            "verify the article reads smoothly from start to finish with no jarring transitions or "
            "abrupt topic shifts; (4) Brand voice alignment — ensure the tone and style match the "
            "specified brand voice throughout, correcting any sections that drift; (5) Keyword density "
            "— verify the primary keyword appears at 0.5-2% density (neither stuffed nor underused), "
            "adjusting natural placements as needed; (6) Headline promise — ensure every section "
            "delivers on what the headline and introduction promise, flagging any gaps; "
            "(7) Final formatting — ensure consistent heading hierarchy, proper markdown formatting, "
            "no orphaned bullets, and clean paragraph spacing."
        )

        user_message = f"""Perform a comprehensive final editorial pass on the following article.

Primary Keyword: {primary_keyword}
Brand Voice: {brand_voice}
Tone: {tone}

Article Draft:
{draft_content}

Editorial Instructions:
- Fix ALL grammar, spelling, and punctuation errors.
- Ensure consistent use of terminology (pick one variant and use it throughout).
- Smooth out any transitions that feel abrupt or mechanical.
- Verify the brand voice ({brand_voice}) is consistent — rewrite any sections that drift.
- Check keyword density for "{primary_keyword}": it should appear every 100-200 words naturally.
  Add it where missing or remove instances where it is over-concentrated.
- Confirm the introduction delivers a clear value proposition matching the headline.
- Verify the conclusion summarizes key takeaways and provides clear next steps.
- Ensure all markdown formatting is clean and consistent (no broken headings, orphaned bullets).
- Remove any filler phrases ("It is important to note that...", "As mentioned above...", "In today's world...").
- Count the final word count accurately.

Return ONLY a valid JSON object with these exact keys:
{{
  "final_article": "string — the complete, fully polished article in markdown",
  "word_count": 2500,
  "keyword_density": 0.015,
  "editorial_notes": ["list of specific edits made during this final pass"],
  "polish_score": 95
}}

Ensure word_count is an integer, keyword_density is a decimal (e.g. 0.015 = 1.5%), and polish_score is an integer from 0-100."""

        raw = self.call_claude_deep_research(system_prompt, user_message, max_tokens=16000)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "final_article": raw,
                "word_count": len(raw.split()),
                "keyword_density": 0.0,
                "editorial_notes": ["Final editorial pass completed"],
                "polish_score": 85,
            }

        # Update shared context fields
        context["draft_content"] = data.get("final_article", draft_content)

        word_count = data.get("word_count", 0)
        keyword_density = data.get("keyword_density", 0.0)
        polish_score = data.get("polish_score", 0)
        editorial_notes = data.get("editorial_notes", [])

        improvements = [
            f"Final polish score: {polish_score}/100",
            f"Final word count: {word_count:,}",
            f"Keyword density: {keyword_density * 100:.1f}%",
            f"Editorial fixes applied: {len(editorial_notes)}",
        ]

        return self.format_output(improvements, data)
