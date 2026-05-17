from agents.base_agent import BaseAgent
import anthropic
import json


class SEOAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="SEO Strategy Agent")

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
        primary_keyword = context.get("primary_keyword", context.get("topic", ""))
        secondary_keywords = context.get("secondary_keywords", [])
        article_outline = context.get("article_outline", {})

        outline_str = json.dumps(article_outline, indent=2) if isinstance(article_outline, dict) else str(article_outline)

        system_prompt = (
            "You are the On-Page SEO Strategist. Optimize the article structure for search "
            "visibility while maintaining readability. Generate SEO title, meta description, "
            "URL slug, semantic keyword distribution plan, heading optimization, entity "
            "optimization, featured snippet optimization, and internal link opportunities. "
            "Avoid keyword stuffing. Optimize naturally. Prioritize readability."
        )

        user_message = f"""Develop an SEO strategy using the context below, then return a JSON object.

Primary Keyword: {primary_keyword}
Secondary Keywords: {', '.join(secondary_keywords)}

Article Outline:
{outline_str}

Return ONLY a valid JSON object with these exact keys:
{{
  "seo_title": "string — 50 to 60 characters including primary keyword",
  "meta_description": "string — 150 to 160 characters",
  "url_slug": "string — lowercase hyphenated slug",
  "focus_keyword": "string",
  "keyword_distribution": {{
    "keyword_example": "suggested number of occurrences as integer"
  }},
  "heading_keywords": {{
    "h2_position_example": "keyword to use"
  }},
  "featured_snippet_target": "string — which section is best for featured snippet",
  "entity_optimization": ["list of entities to mention naturally"],
  "schema_types_recommended": ["list of Schema.org types (e.g. Article, FAQPage, HowTo)"],
  "internal_link_opportunities": [
    {{
      "anchor_text": "string",
      "suggested_page": "string — description of the page to link to"
    }}
  ]
}}"""

        raw = self.call_claude(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "seo_title": primary_keyword,
                "meta_description": "",
                "url_slug": "",
                "focus_keyword": primary_keyword,
                "keyword_distribution": {},
                "heading_keywords": {},
                "featured_snippet_target": "",
                "entity_optimization": [],
                "schema_types_recommended": [],
                "internal_link_opportunities": [],
                "raw_response": raw,
            }

        # Update shared context fields
        context["seo_strategy"] = data
        context["seo_metadata"] = {
            "seo_title": data.get("seo_title", ""),
            "meta_description": data.get("meta_description", ""),
            "url_slug": data.get("url_slug", ""),
        }

        improvements = [
            f"SEO title optimized: {data.get('seo_title', 'N/A')}",
            f"URL slug: {data.get('url_slug', 'N/A')}",
            f"Schema types recommended: {', '.join(data.get('schema_types_recommended', []))}",
            f"Internal link opportunities: {len(data.get('internal_link_opportunities', []))}",
        ]

        return self.format_output(improvements, data)
