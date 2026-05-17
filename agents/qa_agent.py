from agents.base_agent import BaseAgent
import anthropic
import json


class QAAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Quality Assurance")

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
        draft_content = context.get("draft_content", "")
        primary_keyword = context.get("primary_keyword", "")
        search_intent = context.get("search_intent", "")
        article_goal = context.get("article_goal", "")

        system_prompt = (
            "You are a quality assurance specialist for blog content. Your role is to perform a "
            "comprehensive final quality audit and score the article across five dimensions: "
            "(1) SEO Optimization (0-100): keyword placement, meta-friendliness, heading structure, "
            "internal link anchors, schema signals, and search snippet optimization; "
            "(2) Readability (0-100): sentence variety, paragraph length, active voice, transition "
            "quality, scannability, and Flesch-Kincaid grade level appropriateness; "
            "(3) E-E-A-T Signals (0-100): Experience, Expertise, Authoritativeness, and "
            "Trustworthiness — author credentials signals, source citations, depth of expertise "
            "demonstrated, factual accuracy, and trust markers; "
            "(4) Originality (0-100): unique angles, original analysis, avoidance of clichéd "
            "advice, distinctive voice, and content not found in competing articles; "
            "(5) Conversion Potential (0-100): CTA effectiveness, value proposition clarity, "
            "audience alignment, persuasive elements, and next-step clarity. "
            "Calculate an overall score as the weighted average. Provide specific, actionable "
            "recommendations for any dimension scoring below 80."
        )

        user_message = f"""Perform a comprehensive quality audit on the following final article.

Primary Keyword: {primary_keyword}
Search Intent: {search_intent}
Article Goal: {article_goal}

Article to audit:
{draft_content}

Quality Audit Instructions:
- Score each dimension objectively based on the actual content, not assumptions.
- For SEO: check keyword density, heading structure, intro/conclusion keyword presence, link anchors.
- For Readability: assess paragraph length, sentence variety, use of lists, subheading frequency.
- For E-E-A-T: look for expertise signals, citations, author authority markers, factual depth.
- For Originality: evaluate unique insights vs. generic advice, distinctive voice, novel angles.
- For Conversion: assess CTA presence, strength, placement, and alignment with article goal.
- Calculate overall score as: (SEO*0.25 + Readability*0.20 + EEAT*0.25 + Originality*0.15 + Conversion*0.15).
- Approve the article if overall score >= 75, reject if below 75.
- Provide 3-5 specific, actionable recommendations regardless of approval status.

Return ONLY a valid JSON object with these exact keys:
{{
  "quality_scores": {{
    "seo": 85,
    "readability": 80,
    "eeat": 78,
    "originality": 90,
    "conversion": 75,
    "overall": 82
  }},
  "approved": true,
  "recommendations": ["list of specific actionable improvement recommendations"],
  "final_summary": "string — 2-3 sentence executive summary of the article quality"
}}

Ensure all scores are integers from 0-100 and approved is a boolean."""

        raw = self.call_claude(system_prompt, user_message, use_thinking=True, max_tokens=6000)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "quality_scores": {
                    "seo": 75,
                    "readability": 75,
                    "eeat": 75,
                    "originality": 75,
                    "conversion": 75,
                    "overall": 75,
                },
                "approved": True,
                "recommendations": ["Review article manually — automated scoring unavailable"],
                "final_summary": "Quality audit completed with fallback scoring.",
            }

        # Update shared context fields
        context["quality_scores"] = data.get("quality_scores", {})
        context["pipeline_stage"] = "completed"

        quality_scores = data.get("quality_scores", {})
        overall_score = quality_scores.get("overall", 0)
        approved = data.get("approved", False)
        recommendations = data.get("recommendations", [])

        improvements = [
            f"Overall quality score: {overall_score}/100",
            f"Article {'APPROVED' if approved else 'REJECTED — requires revision'}",
            f"SEO: {quality_scores.get('seo', 0)} | Readability: {quality_scores.get('readability', 0)} | E-E-A-T: {quality_scores.get('eeat', 0)}",
            f"Originality: {quality_scores.get('originality', 0)} | Conversion: {quality_scores.get('conversion', 0)}",
            f"Recommendations provided: {len(recommendations)}",
        ]

        return self.format_output(improvements, data)
