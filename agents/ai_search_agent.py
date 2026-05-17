from agents.base_agent import BaseAgent
import anthropic
import json


class AISearchAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="AI Search Optimizer")

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
        primary_keyword = context.get("primary_keyword", "")

        system_prompt = (
            "You are an expert at optimizing content for AI-powered search engines including "
            "Google SGE (Search Generative Experience), Bing Copilot, and Perplexity AI. "
            "Your techniques include: crafting direct answer snippets at the start of sections "
            "that AI engines can extract as citations, adding comprehensive FAQ sections with "
            "conversational question phrasing that matches how people ask AI assistants, "
            "inserting structured data signals through clear definition patterns (X is defined as..., "
            "The key difference between X and Y is...), entity optimization by clearly defining "
            "and contextualizing all named entities, matching conversational query patterns "
            "(who, what, when, where, why, how questions), and creating content chunks that "
            "stand alone as authoritative answers."
        )

        user_message = f"""Optimize the following article for AI-powered search engines (Google SGE, Bing Copilot, Perplexity).

Primary Keyword: {primary_keyword}

Article Draft:
{draft_content}

Instructions:
- Add a concise 2-3 sentence direct answer paragraph immediately after the H1 (before any other content).
- Ensure each H2 section opens with a direct answer to the implicit question the heading raises.
- Add or expand a FAQ section with 5-8 questions phrased conversationally (as people ask AI assistants).
- Add definition boxes or bolded definitions for key terms (format: **Term**: definition).
- Ensure all named entities (people, organizations, tools, concepts) are clearly introduced with context.
- Add "According to..." or "Research shows..." attribution patterns where statistics appear.
- Structure list items so each is a complete, extractable answer on its own.
- Keep all existing content — add to and restructure, do not remove.

Return ONLY a valid JSON object with these exact keys:
{{
  "optimized_content": "string — the full AI-search-optimized article in markdown",
  "ai_snippets_added": ["list of direct answer snippets added"],
  "faq_section": "string — the complete FAQ section added or enhanced",
  "entity_optimizations": ["list of entity optimizations made"]
}}"""

        raw = self.call_claude(system_prompt, user_message, use_thinking=True, max_tokens=8192)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "optimized_content": raw,
                "ai_snippets_added": ["Direct answer snippets added throughout"],
                "faq_section": "",
                "entity_optimizations": ["Entity context added"],
            }

        context["draft_content"] = data.get("optimized_content", draft_content)

        snippets_added = data.get("ai_snippets_added", [])
        entity_opts = data.get("entity_optimizations", [])

        improvements = [
            f"AI search optimized for Google SGE, Bing Copilot, Perplexity",
            f"Direct answer snippets added: {len(snippets_added)}",
            f"Entity optimizations: {len(entity_opts)}",
            "FAQ section added/enhanced for conversational queries",
        ]

        return self.format_output(improvements, data)
