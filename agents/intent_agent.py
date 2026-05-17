from agents.base_agent import BaseAgent
import anthropic
import json


class IntentAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Search Intent Agent")

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

        system_prompt = (
            "You are the Search Intent Analysis Agent. Your task is to identify the real "
            "underlying reason behind the search. Analyze explicit intent, hidden intent, "
            "emotional drivers, pain points, reader fears, desired transformation, awareness "
            "stage (awareness/consideration/decision), objections, and urgency level."
        )

        user_message = f"""Analyze the search intent for the following keyword and topic, then return a JSON object.

Primary Keyword: {primary_keyword}
Topic: {topic}

Return ONLY a valid JSON object with these exact keys:
{{
  "primary_intent": "informational | commercial | transactional | navigational",
  "hidden_intent": "string describing the underlying motivation",
  "emotional_drivers": ["list of emotional motivations"],
  "pain_points": ["list of reader pain points"],
  "desired_outcomes": ["list of what the reader wants to achieve"],
  "awareness_stage": "awareness | consideration | decision",
  "conversion_opportunities": ["list of conversion opportunities"],
  "engagement_triggers": ["list of content elements that will engage this reader"],
  "reader_psychology_summary": "string with a concise summary of reader psychology"
}}"""

        raw = self.call_claude(system_prompt, user_message, use_thinking=True)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "primary_intent": "informational",
                "hidden_intent": "",
                "emotional_drivers": [],
                "pain_points": [],
                "desired_outcomes": [],
                "awareness_stage": "awareness",
                "conversion_opportunities": [],
                "engagement_triggers": [],
                "reader_psychology_summary": "",
                "raw_response": raw,
            }

        # Update shared context fields
        context["search_intent"] = data

        improvements = [
            f"Primary intent classified: {data.get('primary_intent', 'N/A')}",
            f"Awareness stage: {data.get('awareness_stage', 'N/A')}",
            f"Identified {len(data.get('pain_points', []))} pain points",
            f"Found {len(data.get('emotional_drivers', []))} emotional drivers",
        ]

        return self.format_output(improvements, data)
