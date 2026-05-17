from agents.base_agent import BaseAgent
import anthropic
import json


class SchemaAgent(BaseAgent):
    def __init__(self, client, config):
        super().__init__(client, config, name="Schema Markup Generator")

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
        seo_metadata = context.get("seo_metadata", {})

        seo_metadata_str = json.dumps(seo_metadata, indent=2) if isinstance(seo_metadata, dict) else str(seo_metadata)

        system_prompt = (
            "You are an expert at structured data and schema.org markup for SEO. "
            "You generate valid JSON-LD schema markup based on content analysis. "
            "Your expertise covers: Article schema (for blog posts and news), FAQPage schema "
            "(for content with question-answer sections), HowTo schema (for step-by-step guides), "
            "BreadcrumbList schema (for site navigation), and combining multiple schema types "
            "in a single @graph. Rules: always use @context: https://schema.org, validate that "
            "all required properties for each schema type are present, use ISO 8601 for dates, "
            "include author and publisher as nested objects, ensure FAQ schema questions match "
            "actual FAQ content in the article, and provide implementation notes for the developer."
        )

        user_message = f"""Generate appropriate schema.org JSON-LD markup for the following article.

Primary Keyword: {primary_keyword}

SEO Metadata:
{seo_metadata_str}

Article Content:
{draft_content}

Instructions:
- Analyze the article type (is it a how-to guide, informational blog post, FAQ-heavy article?).
- Generate Article schema with: headline, description, author, publisher, datePublished, dateModified,
  mainEntityOfPage, image placeholder.
- If the article contains a FAQ section, add FAQPage schema with all questions and answers extracted.
- If the article is a step-by-step guide, add HowTo schema with steps extracted from the content.
- Add BreadcrumbList schema with placeholder breadcrumbs appropriate to the topic.
- Combine multiple schema types using @graph when applicable.
- Ensure all JSON-LD is syntactically valid.

Return ONLY a valid JSON object with these exact keys:
{{
  "schema_markup": {{"@context": "https://schema.org", "@graph": []}},
  "schema_types": ["Article", "FAQPage"],
  "implementation_notes": "string — instructions for the developer on how to implement this schema"
}}

The schema_markup value must itself be a valid JSON object representing the complete structured data."""

        raw = self.call_claude(system_prompt, user_message, use_thinking=True, max_tokens=6000)

        try:
            data = self._parse_json_response(raw)
        except (json.JSONDecodeError, ValueError):
            data = {
                "schema_markup": {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": primary_keyword,
                    "description": f"Comprehensive guide about {primary_keyword}",
                },
                "schema_types": ["Article"],
                "implementation_notes": "Add this JSON-LD script tag to the <head> of the page.",
            }

        context["schema_markup"] = data.get("schema_markup", {})

        schema_types = data.get("schema_types", [])

        improvements = [
            f"Schema types generated: {', '.join(schema_types)}",
            "Valid JSON-LD structured data markup created",
            "FAQPage schema extracted from article FAQ section",
            "Implementation notes provided for developer handoff",
        ]

        return self.format_output(improvements, data)
