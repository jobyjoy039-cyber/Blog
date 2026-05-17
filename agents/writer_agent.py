from agents.base_agent import BaseAgent
import anthropic
import json


class WriterAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="First Draft Writer")

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
        primary_keyword = context.get("primary_keyword", topic)
        secondary_keywords = context.get("secondary_keywords", [])
        article_outline = context.get("article_outline", {})
        research_data = context.get("research_data", {})
        expert_insights = context.get("expert_insights", {})
        seo_strategy = context.get("seo_strategy", {})
        tone = context.get("tone", "conversational yet authoritative")
        brand_voice = context.get("brand_voice", "")
        audience_profile = context.get("audience_profile", "")

        # Serialize complex context fields for inclusion in the prompt
        outline_str = json.dumps(article_outline, indent=2) if isinstance(article_outline, dict) else str(article_outline)
        research_str = json.dumps(research_data, indent=2) if isinstance(research_data, dict) else str(research_data)
        expert_str = json.dumps(expert_insights, indent=2) if isinstance(expert_insights, dict) else str(expert_insights)
        seo_str = json.dumps(seo_strategy, indent=2) if isinstance(seo_strategy, dict) else str(seo_strategy)

        # Derive word count target from outline or fall back to a sensible default
        word_count_target = article_outline.get("estimated_total_words", 2000) if isinstance(article_outline, dict) else 2000

        system_prompt = (
            "You are the Human-Centered Long-Form Writer. Write a complete, engaging, "
            "authoritative article draft. Style: conversational yet authoritative, human, "
            "emotionally intelligent, clear and engaging. Rules: Avoid AI clichés (delve, "
            "realm, tapestry, leverage, game-changer, etc.). Avoid repetitive sentence "
            "structures. Use natural transitions. Use sentence variation. Include concrete "
            "examples and analogies. Write for humans first, then SEO. Use the H1, H2, H3 "
            "structure from the outline. Incorporate research data, expert insights, and "
            "keywords naturally. Target the specified word count."
        )

        user_message = f"""Write a complete, fully formatted article using ALL of the context below.

Topic: {topic}
Primary Keyword: {primary_keyword}
Secondary Keywords: {', '.join(secondary_keywords)}
Tone: {tone}
Brand Voice: {brand_voice}
Audience Profile: {audience_profile}
Word Count Target: {word_count_target}

Article Outline:
{outline_str}

Research Data:
{research_str}

Expert Insights:
{expert_str}

SEO Strategy:
{seo_str}

Instructions:
- Write the full article in markdown (# for H1, ## for H2, ### for H3).
- Include every section from the outline.
- Incorporate statistics, studies, and frameworks from research_data naturally.
- Weave in expert_insights (tips, pitfalls, nuances, advanced points) at the relevant sections.
- Distribute keywords according to seo_strategy without stuffing.
- Include a FAQ section at the end answering the questions from the outline.
- Meet or exceed the word_count_target.
- Avoid AI clichés: delve, realm, tapestry, leverage, game-changer, revolutionize, paradigm, synergy, holistic, robust, unleash, transformative, elevate.

Return ONLY a valid JSON object with these exact keys:
{{
  "article_draft": "string — the complete markdown article",
  "word_count": 2000,
  "sections_written": ["list of heading titles included in the article"]
}}

Ensure word_count is an integer reflecting the approximate word count of article_draft."""

        raw = self.call_claude_deep_research(system_prompt, user_message, max_tokens=16000)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            # If JSON parsing fails the raw response is likely the article itself;
            # wrap it gracefully so the pipeline can continue.
            data = {
                "article_draft": raw,
                "word_count": len(raw.split()),
                "sections_written": [],
                "raw_response": raw,
            }

        # Update shared context fields
        context["draft_content"] = data.get("article_draft", "")

        word_count = data.get("word_count", len(data.get("article_draft", "").split()))
        sections_written = data.get("sections_written", [])

        improvements = [
            f"Full article draft written: ~{word_count} words",
            f"Sections covered: {len(sections_written)}",
            f"Primary keyword incorporated: {primary_keyword}",
            f"Research data and expert insights woven throughout",
        ]

        return self.format_output(improvements, data)
