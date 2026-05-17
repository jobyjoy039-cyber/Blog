from agents.base_agent import BaseAgent
import anthropic
import json


class KeywordAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Keyword Research Agent")

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

        system_prompt = (
            "You are an advanced SEO Keyword Research Agent. Generate a complete semantic "
            "keyword ecosystem. Analyze and produce primary keywords, secondary keywords, "
            "long-tail keywords, question keywords, semantic keywords, NLP entities, topical "
            "clusters, search modifiers, low competition opportunities, and commercial intent "
            "keywords. Prioritize semantic relevance over keyword stuffing. Optimize for "
            "topical authority. Include conversational and AI-search friendly terms."
        )

        user_message = f"""Research keywords for the following topic and return a JSON object.

Topic: {topic}

Return ONLY a valid JSON object with these exact keys:
{{
  "primary_keyword": "string",
  "secondary_keywords": ["5 to 10 secondary keywords"],
  "long_tail_keywords": ["5 to 10 long-tail keyword phrases"],
  "semantic_keywords": ["list of semantically related keywords"],
  "entities": ["list of NLP entities relevant to the topic"],
  "paa_questions": ["list of People Also Ask style questions"],
  "related_searches": ["list of related search queries"],
  "keyword_clusters": [
    {{
      "cluster_name": "string",
      "keywords": ["list of keywords in this cluster"]
    }}
  ]
}}"""

        raw = self.call_claude_deep_research(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "primary_keyword": topic,
                "secondary_keywords": [],
                "long_tail_keywords": [],
                "semantic_keywords": [],
                "entities": [],
                "paa_questions": [],
                "related_searches": [],
                "keyword_clusters": [],
                "raw_response": raw,
            }

        # Update shared context fields
        context["primary_keyword"] = data.get("primary_keyword", topic)
        context["secondary_keywords"] = data.get("secondary_keywords", [])

        improvements = [
            f"Primary keyword identified: {data.get('primary_keyword', 'N/A')}",
            f"Generated {len(data.get('secondary_keywords', []))} secondary keywords",
            f"Generated {len(data.get('long_tail_keywords', []))} long-tail keywords",
            f"Built {len(data.get('keyword_clusters', []))} topical keyword clusters",
        ]

        return self.format_output(improvements, data)
