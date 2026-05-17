from agents.base_agent import BaseAgent
import anthropic
import json


class OutlineAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Outline Architect Agent")

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
        secondary_keywords = context.get("secondary_keywords", [])
        search_intent = context.get("search_intent", {})
        competitor_gaps = context.get("competitor_gaps", {})
        tone = context.get("tone", "informative")
        brand_voice = context.get("brand_voice", "")
        audience_profile = context.get("audience_profile", "")

        intent_str = json.dumps(search_intent, indent=2) if isinstance(search_intent, dict) else str(search_intent)
        gaps_str = json.dumps(competitor_gaps, indent=2) if isinstance(competitor_gaps, dict) else str(competitor_gaps)

        system_prompt = (
            "You are the SEO Outline Architect. Create a highly optimized article outline "
            "with logical progression, search intent alignment, featured snippet opportunities, "
            "FAQ opportunities, semantic coverage, strong heading hierarchy, mobile readability, "
            "and skimmable structure. Include hook ideas, story opportunities, table opportunities, "
            "visual opportunities, and summary opportunities. The outline must be comprehensive "
            "and detailed."
        )

        user_message = f"""Create a full article outline using all the context below, then return a JSON object.

Topic: {topic}
Primary Keyword: {primary_keyword}
Secondary Keywords: {', '.join(secondary_keywords)}
Tone: {tone}
Brand Voice: {brand_voice}
Audience Profile: {audience_profile}

Search Intent:
{intent_str}

Competitor Gaps:
{gaps_str}

Return ONLY a valid JSON object with these exact keys:
{{
  "h1_title": "string — compelling H1 title with primary keyword",
  "meta_description": "string — 150 to 160 characters",
  "url_slug": "string — lowercase hyphenated slug",
  "introduction": {{
    "hook_type": "string (e.g. statistic, question, story, bold claim)",
    "hook_text": "string — the actual hook text",
    "key_promise": "string — what the reader will gain"
  }},
  "sections": [
    {{
      "h2": "string — H2 heading",
      "h3s": ["list of H3 subheadings"],
      "content_notes": "string — guidance on what to cover in this section",
      "word_count_estimate": 300,
      "featured_snippet_opportunity": false,
      "has_table": false
    }}
  ],
  "conclusion": {{
    "summary_approach": "string",
    "final_cta": "string"
  }},
  "faq_section": ["list of FAQ questions to answer"],
  "estimated_total_words": 2000
}}

Ensure word_count_estimate and estimated_total_words are integers. Include at least 5 sections."""

        raw = self.call_claude_deep_research(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "h1_title": topic,
                "meta_description": "",
                "url_slug": "",
                "introduction": {},
                "sections": [],
                "conclusion": {},
                "faq_section": [],
                "estimated_total_words": 2000,
                "raw_response": raw,
            }

        # Update shared context fields
        context["article_outline"] = data

        improvements = [
            f"H1 title: {data.get('h1_title', 'N/A')}",
            f"Planned {len(data.get('sections', []))} main sections",
            f"Estimated word count: {data.get('estimated_total_words', 'N/A')}",
            f"FAQ questions planned: {len(data.get('faq_section', []))}",
        ]

        return self.format_output(improvements, data)
