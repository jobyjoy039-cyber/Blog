from agents.base_agent import BaseAgent
import anthropic
import json


class CompetitorAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Competitor Analysis Agent")

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

        # Summarise search_intent for the prompt
        intent_summary = ""
        if isinstance(search_intent, dict):
            intent_summary = (
                f"Primary intent: {search_intent.get('primary_intent', 'N/A')}\n"
                f"Awareness stage: {search_intent.get('awareness_stage', 'N/A')}\n"
                f"Pain points: {', '.join(search_intent.get('pain_points', []))}"
            )
        else:
            intent_summary = str(search_intent)

        system_prompt = (
            "You are the Competitor Gap Analysis Agent. Analyze what ranking competitors "
            "likely have and identify weaknesses and content gaps. Look for: missing "
            "explanations, thin sections, poor examples, weak E-E-A-T signals, weak "
            "formatting, lack of expert insight, outdated data, missing FAQs, poor "
            "readability, weak semantic coverage. Focus on differentiation and unique value "
            "opportunities. Never copy competitors."
        )

        user_message = f"""Based on the context below, identify competitor weaknesses and content gaps, then return a JSON object.

Topic: {topic}
Primary Keyword: {primary_keyword}
Search Intent Summary:
{intent_summary}

Return ONLY a valid JSON object with these exact keys:
{{
  "common_weaknesses": ["list of weaknesses found in competitor content"],
  "content_gaps": ["list of topics or angles competitors miss"],
  "differentiation_opportunities": ["list of ways to stand out"],
  "unique_value_propositions": ["list of unique value propositions for this article"],
  "topics_to_cover_deeply": ["list of topics that deserve deep coverage"],
  "topics_competitors_miss": ["list of topics competitors consistently miss"],
  "recommended_content_depth": "string describing the ideal content depth and approach"
}}"""

        raw = self.call_claude_deep_research(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "common_weaknesses": [],
                "content_gaps": [],
                "differentiation_opportunities": [],
                "unique_value_propositions": [],
                "topics_to_cover_deeply": [],
                "topics_competitors_miss": [],
                "recommended_content_depth": "",
                "raw_response": raw,
            }

        # Update shared context fields
        context["competitor_gaps"] = data

        improvements = [
            f"Found {len(data.get('common_weaknesses', []))} competitor weaknesses",
            f"Identified {len(data.get('content_gaps', []))} content gaps",
            f"Generated {len(data.get('differentiation_opportunities', []))} differentiation opportunities",
            f"Flagged {len(data.get('topics_competitors_miss', []))} topics competitors miss",
        ]

        return self.format_output(improvements, data)
