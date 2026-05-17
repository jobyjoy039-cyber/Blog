from agents.base_agent import BaseAgent
import anthropic
import json


class TopicAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Topic Understanding Agent")

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
        topic = context.get("topic", "")

        system_prompt = (
            "You are an expert Topic Understanding Agent. Your role is to deeply analyze "
            "the given topic before content generation begins. Identify the core topic, "
            "subtopics, related entities, niche depth, audience sophistication level, "
            "commercial opportunities, and content format opportunities. Provide a "
            "comprehensive topic analysis."
        )

        user_message = f"""Analyze the following topic in depth and return a JSON object.

Topic: {topic}

Return ONLY a valid JSON object with these exact keys:
{{
  "core_topic": "string",
  "subtopics": ["list of subtopics"],
  "entities": ["list of related named entities"],
  "audience_sophistication": "beginner | intermediate | advanced",
  "commercial_opportunities": ["list of commercial opportunities"],
  "recommended_angles": ["list of recommended content angles"],
  "content_formats": ["list of suitable content formats"],
  "complexity_level": 1
}}

Ensure complexity_level is an integer from 1 to 10."""

        raw = self.call_claude_deep_research(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "core_topic": topic,
                "subtopics": [],
                "entities": [],
                "audience_sophistication": "intermediate",
                "commercial_opportunities": [],
                "recommended_angles": [],
                "content_formats": [],
                "complexity_level": 5,
                "raw_response": raw,
            }

        # Update shared context fields
        context["audience_profile"] = data.get("audience_sophistication", "intermediate")
        context["brand_voice_hints"] = data.get("recommended_angles", [])

        improvements = [
            f"Identified core topic: {data.get('core_topic', topic)}",
            f"Found {len(data.get('subtopics', []))} subtopics",
            f"Audience sophistication: {data.get('audience_sophistication', 'N/A')}",
            f"Complexity level: {data.get('complexity_level', 'N/A')}/10",
        ]

        return self.format_output(improvements, data)
