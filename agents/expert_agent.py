from agents.base_agent import BaseAgent
import anthropic
import json


class ExpertAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Expert Insight Agent")

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
        article_outline = context.get("article_outline", {})
        research_data = context.get("research_data", {})

        outline_str = json.dumps(article_outline, indent=2) if isinstance(article_outline, dict) else str(article_outline)
        research_str = json.dumps(research_data, indent=2) if isinstance(research_data, dict) else str(research_data)

        system_prompt = (
            "You are the Domain Expert Enhancement Agent. Your role is to inject real expertise "
            "into the article to make it feel written by a true domain expert. Add nuance, hidden "
            "pitfalls, strategic insights, advanced considerations, real-world implementation advice, "
            "professional terminology (explained simply), common mistakes to avoid, and best practices. "
            "Make the content authoritative and trustworthy."
        )

        user_message = f"""Add expert-level insights to enrich the article sections using the context below. Return a JSON object.

Topic: {topic}

Article Outline:
{outline_str}

Research Data Summary:
{research_str}

Return ONLY a valid JSON object with these exact keys:
{{
  "expert_insights": [
    {{
      "section": "string — which H2/H3 section this applies to",
      "insight": "string — the expert insight",
      "type": "pitfall | tip | nuance | advanced"
    }}
  ],
  "pro_tips": ["list of actionable pro tips for practitioners"],
  "common_mistakes": [
    {{
      "mistake": "string — the mistake",
      "why_it_happens": "string — root cause",
      "how_to_avoid": "string — prevention advice"
    }}
  ],
  "industry_nuances": ["list of nuances that only insiders know"],
  "advanced_considerations": ["list of advanced considerations for experienced readers"],
  "credibility_boosters": ["list of phrases or approaches that add authority to the writing"],
  "technical_terms_to_use": [
    {{
      "term": "string — the technical term",
      "definition": "string — plain English definition",
      "usage_context": "string — where and how to use it in the article"
    }}
  ]
}}"""

        raw = self.call_claude_deep_research(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "expert_insights": [],
                "pro_tips": [],
                "common_mistakes": [],
                "industry_nuances": [],
                "advanced_considerations": [],
                "credibility_boosters": [],
                "technical_terms_to_use": [],
                "raw_response": raw,
            }

        # Update shared context fields
        context["expert_insights"] = data

        improvements = [
            f"Added {len(data.get('expert_insights', []))} expert insights across sections",
            f"Compiled {len(data.get('pro_tips', []))} pro tips",
            f"Documented {len(data.get('common_mistakes', []))} common mistakes",
            f"Defined {len(data.get('technical_terms_to_use', []))} technical terms",
        ]

        return self.format_output(improvements, data)
