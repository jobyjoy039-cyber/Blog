from agents.base_agent import BaseAgent
import anthropic
import json


class CTAAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="CTA Optimizer")

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
        article_goal = context.get("article_goal", "")
        audience_profile = context.get("audience_profile", "")

        system_prompt = (
            "You are a conversion optimization expert specializing in crafting compelling calls-to-action "
            "for blog content. Your expertise includes: matching CTA messaging to the article's goal "
            "(lead generation, product trial, newsletter signup, consultation booking, content download); "
            "placing CTAs at the highest-converting positions in an article (after major value delivery, "
            "before the conclusion, and inline within relevant sections); writing benefit-driven CTA copy "
            "that speaks directly to the reader's pain points and desired outcomes; creating natural "
            "transitions into CTAs so they feel like helpful next steps rather than interruptions; "
            "developing multiple CTA variants for A/B testing; and aligning CTA urgency and tone with "
            "the reader's intent stage (awareness, consideration, or decision)."
        )

        user_message = f"""Add strategic CTAs to the following article based on its goal and target audience.

Article Goal: {article_goal}
Audience Profile: {audience_profile}

Article Draft:
{draft_content}

Instructions:
- Analyze the article goal and audience to determine the most appropriate CTA type and messaging.
- Insert a primary CTA after the most value-dense section (typically after the main how-to or key insight).
- Insert a secondary CTA before or in the conclusion section.
- Consider adding one inline CTA within the body if there is a highly relevant section.
- CTAs should feel like natural next steps, not interruptions — use transitional lead-ins.
- Format CTAs clearly with a separator line and bold CTA text, e.g.:
  ---
  **Ready to [benefit]? [Action verb] [offer] →**
  ---
- Write benefit-focused copy (what the reader gains, not what they do).
- Create 2-3 CTA variant options for the primary CTA for A/B testing purposes.
- Do NOT place CTAs in the introduction or within the first 20% of the article.

Return ONLY a valid JSON object with these exact keys:
{{
  "content_with_ctas": "string — the full article in markdown with CTAs inserted",
  "cta_strategy": {{
    "primary_cta": "string — the primary CTA copy used",
    "secondary_cta": "string — the secondary CTA copy used",
    "placement": ["list of placement descriptions, e.g. 'After Section 3: Key Benefits'"]
  }},
  "cta_variants": ["list of 2-3 alternative CTA copy variants for A/B testing"]
}}"""

        raw = self.call_claude(system_prompt, user_message)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "content_with_ctas": raw,
                "cta_strategy": {
                    "primary_cta": "",
                    "secondary_cta": "",
                    "placement": [],
                },
                "cta_variants": [],
            }

        # Update shared context fields
        context["draft_content"] = data.get("content_with_ctas", draft_content)
        context["cta_strategy"] = data.get("cta_strategy", {})

        cta_strategy = data.get("cta_strategy", {})
        cta_variants = data.get("cta_variants", [])
        placement = cta_strategy.get("placement", [])

        improvements = [
            f"CTAs added at {len(placement)} strategic positions",
            f"Primary CTA: {cta_strategy.get('primary_cta', '')[:60]}..." if cta_strategy.get("primary_cta") else "Primary CTA added",
            f"A/B test variants created: {len(cta_variants)}",
            "CTAs aligned with article goal and audience intent",
        ]

        return self.format_output(improvements, data)
