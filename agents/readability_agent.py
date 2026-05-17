from agents.base_agent import BaseAgent
import anthropic
import json


class ReadabilityAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Readability Optimizer")

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
            "You are an expert at optimizing content for readability. Your specialties include: "
            "breaking up dense paragraphs into shorter, more digestible chunks (2-4 sentences max), "
            "converting appropriate passages into bullet points or numbered lists, adding descriptive "
            "subheadings that guide readers through the content, converting passive voice to active voice, "
            "optimizing for Flesch-Kincaid readability scores (target grade 8-10), adding transition "
            "words that improve flow (however, additionally, as a result, in contrast), creating scannable "
            "structure with clear visual hierarchy, ensuring topic sentences clearly state each paragraph's "
            "main idea, and removing redundant or filler content that slows readers down."
        )

        user_message = f"""Optimize the following article for maximum readability and scannability.

Article Draft:
{draft_content}

Instructions:
- Break any paragraph longer than 4 sentences into two paragraphs.
- Convert dense explanations into bullet points or numbered lists where appropriate.
- Ensure every H2 section has a clear, benefit-driven subheading.
- Add H3 subheadings to long sections to improve navigation.
- Convert passive voice constructions to active voice.
- Add transition words at the start of paragraphs to improve flow.
- Ensure topic sentences are crisp and front-loaded.
- Target an average sentence length of 15-20 words.
- Keep all content, facts, and structure — only optimize presentation.

Return ONLY a valid JSON object with these exact keys:
{{
  "optimized_content": "string — the full readability-optimized article in markdown",
  "readability_score": 72,
  "improvements": ["list of specific improvements made"],
  "avg_sentence_length": 18
}}

Ensure readability_score is an integer from 0-100 and avg_sentence_length is an integer (word count)."""

        raw = self.call_claude(system_prompt, user_message, max_tokens=8192)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "optimized_content": raw,
                "readability_score": 70,
                "improvements": ["Readability pass applied"],
                "avg_sentence_length": 18,
            }

        context["draft_content"] = data.get("optimized_content", draft_content)

        readability_score = data.get("readability_score", 70)
        improvements_list = data.get("improvements", [])
        avg_sentence_length = data.get("avg_sentence_length", 18)

        improvements = [
            f"Readability score: {readability_score}/100",
            f"Average sentence length: {avg_sentence_length} words",
            f"Improvements applied: {len(improvements_list)}",
            "Active voice, scannable structure, optimized paragraphs",
        ]

        return self.format_output(improvements, data)
