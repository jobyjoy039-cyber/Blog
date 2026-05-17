from agents.base_agent import BaseAgent
import anthropic
import json


class ResearchAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Research Agent")

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

        outline_str = json.dumps(article_outline, indent=2) if isinstance(article_outline, dict) else str(article_outline)

        system_prompt = (
            "You are the Research and Evidence Agent. Collect authoritative supporting "
            "information for the article. Include relevant statistics, studies, trends, expert "
            "opinions, case studies, examples, frameworks, and data-backed claims. Prioritize "
            "recent and authoritative sources. Flag uncertain claims. Avoid fabricated statistics "
            "— use placeholders like [STAT: description] for statistics that need verification. "
            "Focus on providing factual frameworks and knowledge structures."
        )

        user_message = f"""Research supporting content for the topic below, guided by the article outline. Return a JSON object.

Topic: {topic}

Article Outline:
{outline_str}

Return ONLY a valid JSON object with these exact keys:
{{
  "key_statistics": [
    {{
      "stat": "string — the statistic (use [STAT: description] if uncertain)",
      "source": "string — source name or [SOURCE NEEDED]",
      "year": "string — year or 'N/A'"
    }}
  ],
  "relevant_studies": [
    {{
      "finding": "string — the study finding",
      "implication": "string — what this means for the reader"
    }}
  ],
  "industry_trends": ["list of current industry trends"],
  "expert_perspectives": ["list of expert viewpoints or commonly cited expert opinions"],
  "case_studies": [
    {{
      "scenario": "string — the situation",
      "outcome": "string — what happened",
      "lesson": "string — key takeaway"
    }}
  ],
  "frameworks": [
    {{
      "name": "string — framework name",
      "description": "string — what it is",
      "application": "string — how to apply it"
    }}
  ],
  "data_points": ["list of notable data points and facts"],
  "research_notes": "string — comprehensive notes on the research gathered"
}}"""

        raw = self.call_claude_deep_research(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "key_statistics": [],
                "relevant_studies": [],
                "industry_trends": [],
                "expert_perspectives": [],
                "case_studies": [],
                "frameworks": [],
                "data_points": [],
                "research_notes": "",
                "raw_response": raw,
            }

        # Update shared context fields
        context["research_data"] = data

        improvements = [
            f"Gathered {len(data.get('key_statistics', []))} key statistics",
            f"Found {len(data.get('relevant_studies', []))} relevant studies",
            f"Identified {len(data.get('industry_trends', []))} industry trends",
            f"Developed {len(data.get('frameworks', []))} frameworks",
        ]

        return self.format_output(improvements, data)
