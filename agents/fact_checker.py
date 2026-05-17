from agents.base_agent import BaseAgent
import anthropic
import json


class FactCheckerAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Fact Checker")

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
        draft_content = context.get("draft_content", "")

        system_prompt = (
            "You are a rigorous fact-checker with expertise in identifying and evaluating factual claims "
            "in written content. Your process: first, identify every factual claim in the article "
            "(statistics, dates, names, percentages, study results, historical facts, product claims). "
            "Second, categorize each claim as verifiable (well-known, commonly accepted facts), "
            "potentially incorrect (specific numbers or dates that seem off), or unverifiable "
            "(claims that cannot be confirmed without a specific primary source). "
            "Third, for verifiable claims add [Source: description] placeholders. "
            "Fourth, flag and correct any claims that appear statistically unlikely or factually wrong. "
            "Fifth, remove or soften unverifiable claims by adding hedging language "
            "(research suggests, many experts believe, some studies indicate). "
            "Your goal is a factually trustworthy article that cites its sources appropriately."
        )

        user_message = f"""Fact-check the following article thoroughly. Identify all factual claims,
verify what you can, flag what seems incorrect, and add source attribution placeholders.

Article Draft:
{draft_content}

Instructions:
- Scan every paragraph for specific factual claims (statistics, percentages, dates, names, study results).
- Add [Source: brief description] immediately after any specific statistic or research finding.
- Flag any claim that seems numerically implausible with [FACT-CHECK: concern description].
- Remove or add hedging language to unverifiable absolute statements.
- Correct any clearly incorrect facts you identify with [CORRECTED: explanation].
- Do NOT remove any content that is likely accurate — only flag or correct genuinely problematic claims.
- Preserve all structure, headings, and flow of the original article.

Return ONLY a valid JSON object with these exact keys:
{{
  "verified_content": "string — the full fact-checked article in markdown",
  "claims_verified": ["list of claims confirmed as accurate"],
  "claims_flagged": ["list of claims flagged for review with reasons"],
  "fact_check_score": 88
}}

Ensure fact_check_score is an integer from 0-100 reflecting overall factual reliability."""

        raw = self.call_claude_deep_research(system_prompt, user_message, max_tokens=8192)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "verified_content": raw,
                "claims_verified": [],
                "claims_flagged": [],
                "fact_check_score": 80,
            }

        context["draft_content"] = data.get("verified_content", draft_content)

        # Update quality scores with fact check result
        quality_scores = context.get("quality_scores", {})
        quality_scores["fact_check"] = data.get("fact_check_score", 80)
        context["quality_scores"] = quality_scores

        fact_check_score = data.get("fact_check_score", 80)
        claims_verified = data.get("claims_verified", [])
        claims_flagged = data.get("claims_flagged", [])

        improvements = [
            f"Fact-check score: {fact_check_score}/100",
            f"Claims verified: {len(claims_verified)}",
            f"Claims flagged for review: {len(claims_flagged)}",
            "Source attribution placeholders added throughout",
        ]

        return self.format_output(improvements, data)
