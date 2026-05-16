"""Tests for new agents added in v1.7.0 and v1.8.0.

Validates agent frontmatter, required sections, tool declarations,
security constraints, and behavioral contracts.
"""

from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).parent.parent / "agents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_agent(agent_name: str) -> str:
    path = AGENTS_DIR / f"{agent_name}.md"
    assert path.exists(), f"Agent file not found: {agent_name}.md"
    return path.read_text(encoding="utf-8")


def extract_frontmatter(content: str) -> dict:
    if not content.startswith("---"):
        return {}
    end = content.index("---", 3)
    block = content[3:end].strip()
    result = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def get_tools(content: str) -> list:
    """Extract tools list from frontmatter."""
    if "tools:" not in content:
        return []
    start = content.index("tools:") + len("tools:")
    end = content.index("\n---", start) if "\n---" in content[start:] else len(content)
    block = content[start:end]
    tools = []
    for line in block.splitlines():
        stripped = line.strip().lstrip("- ").strip()
        if stripped and not stripped.startswith("#"):
            tools.append(stripped)
    return tools


ALL_AGENTS = [
    "blog-researcher",
    "blog-writer",
    "blog-seo",
    "blog-reviewer",
    "blog-translator",
    "blog-qa",
    "blog-competitor",
    "blog-monetizer",
    "blog-outreach",
    "blog-repurposer",
    "blog-editor",
    "blog-publisher",
    "blog-strategist",
    "blog-analyst",
    "blog-localizer",
]

NEW_AGENTS = [
    "blog-qa",
    "blog-competitor",
    "blog-monetizer",
    "blog-outreach",
    "blog-repurposer",
    "blog-editor",
    "blog-publisher",
    "blog-strategist",
    "blog-analyst",
    "blog-localizer",
]

# Agents that must NOT have Bash (security hardening from v1.7.0)
NO_BASH_AGENTS = ["blog-reviewer", "blog-translator"]

# Agents that have WebSearch/WebFetch (must have prompt-injection defense)
WEB_FETCH_AGENTS = ["blog-researcher", "blog-competitor", "blog-outreach",
                    "blog-monetizer", "blog-strategist"]


# ---------------------------------------------------------------------------
# All agents: frontmatter validation
# ---------------------------------------------------------------------------

class TestAllAgentFrontmatter:

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_file_exists(self, agent_name):
        path = AGENTS_DIR / f"{agent_name}.md"
        assert path.exists(), f"Agent file missing: {agent_name}.md"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_has_name_field(self, agent_name):
        fm = extract_frontmatter(read_agent(agent_name))
        assert "name" in fm, f"{agent_name}: missing 'name' frontmatter field"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_has_description_field(self, agent_name):
        fm = extract_frontmatter(read_agent(agent_name))
        assert "description" in fm, f"{agent_name}: missing 'description' frontmatter field"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_has_tools_field(self, agent_name):
        content = read_agent(agent_name)
        assert "tools:" in content, f"{agent_name}: missing 'tools:' declaration"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_description_mentions_invoked(self, agent_name):
        content = read_agent(agent_name)
        # Extract the full description block (handles YAML block scalars)
        desc_start = content.find("description:")
        import re
        next_key = re.search(r'\n[a-z]', content[desc_start + 12:])
        desc_end = desc_start + 12 + next_key.start() if next_key else content.find("\ntools:")
        desc_block = content[desc_start:desc_end]
        trigger_words = ["invoked", "use when", "use for", "triggered", "handles",
                         "manages", "validates", "audits", "when", "specialist"]
        assert any(w in desc_block.lower() for w in trigger_words), (
            f"{agent_name}: description should mention when it is invoked"
        )


# ---------------------------------------------------------------------------
# Security: Bash restrictions
# ---------------------------------------------------------------------------

class TestAgentSecurityConstraints:

    @pytest.mark.parametrize("agent_name", NO_BASH_AGENTS)
    def test_no_bash_in_tools(self, agent_name):
        tools = get_tools(read_agent(agent_name))
        assert "Bash" not in tools, (
            f"{agent_name}: must not have Bash tool (security hardening v1.7.0)"
        )

    @pytest.mark.parametrize("agent_name", WEB_FETCH_AGENTS)
    def test_has_prompt_injection_defense(self, agent_name):
        content = read_agent(agent_name)
        defense_markers = [
            "untrusted",
            "EXTERNAL CONTENT",
            "prompt injection",
            "treat as data",
            "never as instructions",
        ]
        has_defense = any(m.lower() in content.lower() for m in defense_markers)
        assert has_defense, (
            f"{agent_name}: has WebFetch/WebSearch but lacks prompt injection defense"
        )

    def test_researcher_wraps_external_content(self):
        content = read_agent("blog-researcher")
        assert "EXTERNAL CONTENT" in content, (
            "blog-researcher: must fence WebFetch output as 'EXTERNAL CONTENT'"
        )

    def test_researcher_strips_injection_patterns(self):
        content = read_agent("blog-researcher")
        assert "Sanitize" in content or "sanitize" in content or "Strip" in content, (
            "blog-researcher: must strip prompt injection patterns from fetched content"
        )


# ---------------------------------------------------------------------------
# New agents: content validation
# ---------------------------------------------------------------------------

class TestNewAgentContent:

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_has_role_section(self, agent_name):
        content = read_agent(agent_name)
        role_markers = ["## Your Role", "## Role", "## Overview", "## Core Principle",
                        "## Critical Rules", "## Your Job"]
        assert any(m in content for m in role_markers), (
            f"{agent_name}: missing role/overview section"
        )

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_has_process_section(self, agent_name):
        content = read_agent(agent_name)
        process_markers = [
            "## Process", "## Workflow", "## Publishing Workflow",
            "## Editorial Workflow", "## Strategy Workflow", "## Pipeline",
        ]
        assert any(m in content for m in process_markers), (
            f"{agent_name}: missing process/workflow section"
        )

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_has_quality_self_check(self, agent_name):
        content = read_agent(agent_name)
        assert "Quality Self-Check" in content or "self-check" in content.lower(), (
            f"{agent_name}: missing Quality Self-Check section"
        )

    @pytest.mark.parametrize("agent_name", NEW_AGENTS)
    def test_under_300_lines(self, agent_name):
        content = read_agent(agent_name)
        line_count = len(content.splitlines())
        assert line_count <= 300, (
            f"{agent_name}: agent file has {line_count} lines (recommended max ~300)"
        )


# ---------------------------------------------------------------------------
# Agent-specific behavioral contracts
# ---------------------------------------------------------------------------

class TestBlogQaAgent:
    def test_has_five_categories(self):
        content = read_agent("blog-qa")
        categories = ["Fact-Check", "AI Content Detection", "SEO Validation",
                      "Schema Markup", "Image Audit"]
        for cat in categories:
            assert cat in content, f"blog-qa: missing category '{cat}'"

    def test_defines_blocked_status(self):
        content = read_agent("blog-qa")
        assert "BLOCKED" in content, "blog-qa: must define BLOCKED publish status"

    def test_critical_severity_defined(self):
        content = read_agent("blog-qa")
        assert "Critical" in content, "blog-qa: must define Critical severity level"


class TestBlogCompetitorAgent:
    def test_has_gap_types(self):
        content = read_agent("blog-competitor")
        gap_types = ["Coverage Gap", "Quality Gap", "Intent Gap", "Adjacency Gap"]
        for g in gap_types:
            assert g in content, f"blog-competitor: missing gap type '{g}'"

    def test_saves_to_competitors_dir(self):
        content = read_agent("blog-competitor")
        assert "competitors/" in content, (
            "blog-competitor: outputs must be saved to competitors/ directory"
        )

    def test_gap_priority_scoring(self):
        content = read_agent("blog-competitor")
        assert "priority score" in content.lower() or "Priority score" in content, (
            "blog-competitor: must include gap priority scoring"
        )


class TestBlogMonetizer:
    def test_has_ftc_disclosure(self):
        content = read_agent("blog-monetizer")
        assert "FTC" in content or "disclosure" in content.lower(), (
            "blog-monetizer: must include FTC disclosure guidance"
        )

    def test_reader_first_principle(self):
        content = read_agent("blog-monetizer")
        assert "reader" in content.lower() and "trust" in content.lower(), (
            "blog-monetizer: must include reader-first / trust principle"
        )

    def test_max_two_ctas(self):
        content = read_agent("blog-monetizer")
        assert "2 CTAs" in content or "Maximum 2" in content or "max 2" in content.lower(), (
            "blog-monetizer: must enforce max 2 CTAs per post"
        )


class TestBlogOutreachAgent:
    def test_email_word_limit(self):
        content = read_agent("blog-outreach")
        assert "120 words" in content or "under 120" in content.lower(), (
            "blog-outreach: outreach emails must be under 120 words"
        )

    def test_no_spam_openers(self):
        content = read_agent("blog-outreach")
        banned = ["I hope this email finds you well", "I wanted to reach out"]
        for phrase in banned:
            assert phrase in content, (
                f"blog-outreach: must explicitly ban spam opener '{phrase}'"
            )

    def test_saves_tracker(self):
        content = read_agent("blog-outreach")
        assert "tracker.md" in content or "outreach/tracker" in content, (
            "blog-outreach: must maintain an outreach tracker file"
        )


class TestBlogRepurposerAgent:
    def test_has_six_platforms(self):
        content = read_agent("blog-repurposer")
        platforms = ["Twitter", "LinkedIn", "YouTube", "Reddit", "email", "short-form"]
        for p in platforms:
            assert p.lower() in content.lower(), f"blog-repurposer: missing platform '{p}'"

    def test_saves_to_repurposed_dir(self):
        content = read_agent("blog-repurposer")
        assert "repurposed/" in content, (
            "blog-repurposer: outputs must save to repurposed/ directory"
        )

    def test_twitter_numbering(self):
        content = read_agent("blog-repurposer")
        assert "1/N" in content or "N/total" in content or "numbered" in content.lower(), (
            "blog-repurposer: Twitter/X threads must use numbered format"
        )


class TestBlogEditorAgent:
    def test_has_phases(self):
        content = read_agent("blog-editor")
        phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4"]
        for phase in phases:
            assert phase in content, f"blog-editor: missing '{phase}'"

    def test_no_fabricated_data_rule(self):
        content = read_agent("blog-editor")
        assert "fabricat" in content.lower() or "never" in content.lower(), (
            "blog-editor: must explicitly prohibit fabricating replacement statistics"
        )


class TestBlogPublisherAgent:
    def test_has_cms_platforms(self):
        content = read_agent("blog-publisher")
        platforms = ["WordPress", "Ghost", "Shopify"]
        for p in platforms:
            assert p in content, f"blog-publisher: missing CMS platform '{p}'"

    def test_requires_qa_approval(self):
        content = read_agent("blog-publisher")
        assert "APPROVED" in content or "QA" in content, (
            "blog-publisher: must require QA approval before publishing"
        )

    def test_no_hardcoded_credentials(self):
        content = read_agent("blog-publisher")
        assert "environment" in content.lower() or "env" in content.lower(), (
            "blog-publisher: credentials must come from environment variables"
        )

    def test_publish_log(self):
        content = read_agent("blog-publisher")
        assert "publish/log.md" in content or "log.md" in content, (
            "blog-publisher: must maintain publish/log.md"
        )


class TestBlogStrategistAgent:
    def test_has_three_phases(self):
        content = read_agent("blog-strategist")
        phases = ["Phase 1", "Phase 2", "Phase 3"]
        for phase in phases:
            assert phase in content, f"blog-strategist: missing '{phase}'"

    def test_ninety_day_output(self):
        content = read_agent("blog-strategist")
        assert "90-day" in content or "90 day" in content.lower(), (
            "blog-strategist: must produce a 90-day editorial calendar"
        )


class TestBlogAnalystAgent:
    def test_has_composite_score(self):
        content = read_agent("blog-analyst")
        assert "composite" in content.lower() or "Composite" in content, (
            "blog-analyst: must calculate a composite performance score"
        )

    def test_saves_to_performance_dir(self):
        content = read_agent("blog-analyst")
        assert "performance/" in content, (
            "blog-analyst: reports must be saved to performance/ directory"
        )


class TestBlogLocalizerAgent:
    def test_has_pipeline_stages(self):
        content = read_agent("blog-localizer")
        stages = ["blog-translate", "blog-localize", "blog-locale-audit", "hreflang"]
        for stage in stages:
            assert stage.lower() in content.lower(), (
                f"blog-localizer: missing pipeline stage '{stage}'"
            )

    def test_x_default_hreflang(self):
        content = read_agent("blog-localizer")
        assert "x-default" in content, (
            "blog-localizer: must include x-default hreflang tag"
        )

    def test_en_publishes_first(self):
        content = read_agent("blog-localizer")
        assert "EN first" in content or "English first" in content or "Publish EN" in content, (
            "blog-localizer: must recommend publishing EN version first"
        )
