from agents.base_agent import BaseAgent
import anthropic
import json


class BriefAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Content Brief Agent")

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
        topic = context.get("topic", "")
        primary_keyword = context.get("primary_keyword", topic)
        search_intent = context.get("search_intent", {})
        competitor_gaps = context.get("competitor_gaps", {})

        # Build concise summaries for the prompt
        intent_str = json.dumps(search_intent, indent=2) if isinstance(search_intent, dict) else str(search_intent)
        gaps_str = json.dumps(competitor_gaps, indent=2) if isinstance(competitor_gaps, dict) else str(competitor_gaps)

        system_prompt = (
            "You are the Editorial Strategy Agent. Create a master content brief that serves "
            "as the blueprint for the entire article. Define target audience, tone, brand voice, "
            "reading level, E-E-A-T strategy, unique positioning, content goals, desired user "
            "action, emotional positioning, and content depth level."
        )

        user_message = f"""Create a comprehensive content brief using the context below, then return a JSON object.

Topic: {topic}
Primary Keyword: {primary_keyword}

Search Intent:
{intent_str}

Competitor Gaps:
{gaps_str}

Return ONLY a valid JSON object with these exact keys:
{{
  "target_audience": "detailed description of the target audience",
  "tone": "string describing the article tone",
  "brand_voice": "description of the brand voice to use",
  "reading_level": "Flesch-Kincaid grade level as a string (e.g. Grade 8)",
  "eeat_strategy": {{
    "experience": "string",
    "expertise": "string",
    "authority": "string",
    "trustworthiness": "string"
  }},
  "unique_positioning": "string",
  "content_goals": ["list of content goals"],
  "primary_cta": "string",
  "emotional_positioning": "string",
  "content_depth": "shallow | medium | deep | comprehensive",
  "word_count_target": 2000,
  "article_type": "how-to | listicle | guide | review | comparison | other"
}}

Ensure word_count_target is an integer."""

        raw = self.call_claude(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "target_audience": "",
                "tone": "informative",
                "brand_voice": "",
                "reading_level": "Grade 8",
                "eeat_strategy": {},
                "unique_positioning": "",
                "content_goals": [],
                "primary_cta": "",
                "emotional_positioning": "",
                "content_depth": "deep",
                "word_count_target": 2000,
                "article_type": "guide",
                "raw_response": raw,
            }

        # Update shared context fields
        context["tone"] = data.get("tone", "informative")
        context["brand_voice"] = data.get("brand_voice", "")
        context["audience_profile"] = data.get("target_audience", context.get("audience_profile", ""))

        improvements = [
            f"Article type defined: {data.get('article_type', 'N/A')}",
            f"Tone set to: {data.get('tone', 'N/A')}",
            f"Content depth: {data.get('content_depth', 'N/A')}",
            f"Word count target: {data.get('word_count_target', 'N/A')} words",
        ]

        return self.format_output(improvements, data)
