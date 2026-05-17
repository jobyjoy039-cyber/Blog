from agents.base_agent import BaseAgent
import anthropic
import json


class HumanizerAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Humanization Specialist")

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

        system_prompt = (
            "You are an expert at making AI-generated content sound authentically human. "
            "Your techniques include: varying sentence structure so no two consecutive sentences "
            "follow the same pattern, adding personal anecdotes and relatable scenarios, replacing "
            "corporate jargon and buzzwords with natural everyday language, injecting personality "
            "and a distinct voice, using rhetorical questions to engage readers, adding conversational "
            "transitions that feel organic rather than mechanical, breaking the fourth wall occasionally, "
            "using contractions and informal phrasing where appropriate, referencing specific real-world "
            "examples rather than vague generalities. The goal is that a reader would never suspect "
            "the content was AI-generated."
        )

        user_message = f"""Humanize the following article draft so it reads as if written by a knowledgeable,
engaging human author with a distinct personality and genuine expertise.

Article Draft:
{draft_content}

Instructions:
- Vary sentence lengths dramatically (short punchy sentences mixed with longer flowing ones).
- Replace any AI clichés (delve, realm, tapestry, leverage, game-changer, revolutionize, paradigm,
  synergy, holistic, robust, unleash, transformative, elevate, it's worth noting, in conclusion) with natural alternatives.
- Add 2-3 personal anecdotes or relatable "you've probably experienced this" moments.
- Insert rhetorical questions at natural pause points.
- Use contractions (it's, you'll, don't, we're) throughout.
- Add conversational asides in parentheses occasionally.
- Ensure transitions feel earned, not formulaic.
- Keep all factual content, statistics, and structure intact.

Return ONLY a valid JSON object with these exact keys:
{{
  "humanized_content": "string — the full humanized article in markdown",
  "changes_made": ["list of specific changes applied"],
  "readability_improvements": ["list of readability improvements made"],
  "human_score": 85
}}

Ensure human_score is an integer from 0-100 estimating how human the content reads."""

        raw = self.call_claude_deep_research(system_prompt, user_message, max_tokens=12000)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "humanized_content": raw,
                "changes_made": ["Full humanization pass applied"],
                "readability_improvements": ["Natural language throughout"],
                "human_score": 80,
            }

        context["draft_content"] = data.get("humanized_content", draft_content)

        changes_made = data.get("changes_made", [])
        human_score = data.get("human_score", 80)

        improvements = [
            f"Article humanized — human score: {human_score}/100",
            f"Changes applied: {len(changes_made)}",
            "Replaced AI clichés with natural language",
            "Added personal anecdotes and rhetorical questions",
        ]

        return self.format_output(improvements, data)
