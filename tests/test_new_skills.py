"""Tests for Phase 2 and Phase 3 skills added in v1.8.0+.

Validates SKILL.md frontmatter structure, required sections,
and key behavioral contracts for each new skill.
"""

import os
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent / "skills"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_skill(skill_name: str) -> str:
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.exists(), f"SKILL.md not found for {skill_name}"
    return path.read_text(encoding="utf-8")


def extract_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter fields as a simple key: value dict."""
    if not content.startswith("---"):
        return {}
    end = content.index("---", 3)
    block = content[3:end].strip()
    result = {}
    for line in block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


NEW_SKILLS = [
    "blog-ab",
    "blog-decay",
    "blog-style",
    "blog-sxo",
    "blog-email-sequence",
    "blog-quiz",
    "blog-glossary",
    "blog-accessibility",
    "blog-podcast-brief",
    "blog-keyword-research",
    "blog-drift",
    "blog-dashboard",
]


# ---------------------------------------------------------------------------
# Frontmatter validation (all new skills)
# ---------------------------------------------------------------------------

class TestNewSkillFrontmatter:
    """All new SKILL.md files must have valid frontmatter."""

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_file_exists(self, skill_name):
        path = SKILLS_DIR / skill_name / "SKILL.md"
        assert path.exists(), f"{skill_name}/SKILL.md missing"

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_name_field(self, skill_name):
        fm = extract_frontmatter(read_skill(skill_name))
        assert "name" in fm, f"{skill_name}: missing 'name' in frontmatter"
        assert fm["name"] == skill_name, (
            f"{skill_name}: name field '{fm['name']}' does not match directory"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_description(self, skill_name):
        fm = extract_frontmatter(read_skill(skill_name))
        assert "description" in fm, f"{skill_name}: missing 'description'"

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_license(self, skill_name):
        fm = extract_frontmatter(read_skill(skill_name))
        assert "license" in fm, f"{skill_name}: missing 'license'"

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_no_disallowed_fields(self, skill_name):
        content = read_skill(skill_name)
        assert "allowed-tools:" not in content, (
            f"{skill_name}: 'allowed-tools' is not a valid Claude Code spec field"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_user_invokable_field(self, skill_name):
        """Skills with argument-hint must also have user-invokable: true."""
        fm = extract_frontmatter(read_skill(skill_name))
        if "argument-hint" in fm:
            assert fm.get("user-invokable") == "true", (
                f"{skill_name}: has argument-hint but user-invokable is not true"
            )


# ---------------------------------------------------------------------------
# Content structure validation
# ---------------------------------------------------------------------------

class TestNewSkillContent:
    """New skills must have required content sections."""

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_h1_title(self, skill_name):
        content = read_skill(skill_name)
        body = content[content.index("---", 3) + 3:].strip() if "---" in content[3:] else content
        assert any(line.startswith("# ") for line in body.splitlines()), (
            f"{skill_name}: missing H1 title in body"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_input_handling_section(self, skill_name):
        content = read_skill(skill_name)
        assert "## Input Handling" in content or "## Input" in content or "## Usage" in content, (
            f"{skill_name}: missing Input Handling section"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_output_format_section(self, skill_name):
        content = read_skill(skill_name)
        assert "## Output" in content, (
            f"{skill_name}: missing Output Format section"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_has_quality_self_check(self, skill_name):
        content = read_skill(skill_name)
        assert "Quality Self-Check" in content or "self-check" in content.lower(), (
            f"{skill_name}: missing Quality Self-Check section"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_skill_under_500_lines(self, skill_name):
        content = read_skill(skill_name)
        line_count = len(content.splitlines())
        assert line_count <= 500, (
            f"{skill_name}: SKILL.md has {line_count} lines (max 500 per dev rules)"
        )

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_description_mentions_use_when(self, skill_name):
        """Description should tell Claude when to invoke this skill."""
        content = read_skill(skill_name)
        # Find the description block (handles YAML block scalars with >)
        desc_start = content.find("description:")
        # End at next top-level key (user-invokable, argument-hint, license, etc.)
        import re
        next_key = re.search(r'\n[a-z]', content[desc_start + 12:])
        desc_end = desc_start + 12 + next_key.start() if next_key else len(content)
        desc_block = content[desc_start:desc_end]
        trigger_words = ["use when", "invoked", "use for", "triggered"]
        assert any(w in desc_block.lower() for w in trigger_words), (
            f"{skill_name}: description should include usage trigger phrases ('use when', 'invoked', etc.)"
        )


# ---------------------------------------------------------------------------
# Skill-specific behavioral contracts
# ---------------------------------------------------------------------------

class TestBlogAb:
    def test_mentions_five_angles(self):
        content = read_skill("blog-ab")
        angles = ["Number", "Curiosity", "How-To", "Question", "Contrarian"]
        for angle in angles:
            assert angle in content, f"blog-ab: missing headline angle '{angle}'"

    def test_mentions_ctr_scoring(self):
        content = read_skill("blog-ab")
        assert "CTR" in content, "blog-ab: should reference CTR scoring"

    def test_output_has_table(self):
        content = read_skill("blog-ab")
        assert "| # |" in content or "| Variant |" in content, (
            "blog-ab: output format should include a table"
        )


class TestBlogDecay:
    def test_has_four_signals(self):
        content = read_skill("blog-decay")
        signals = ["Age", "Statistic Freshness", "Reference Currency", "GSC"]
        for s in signals:
            assert s in content, f"blog-decay: missing decay signal '{s}'"

    def test_defines_decay_bands(self):
        content = read_skill("blog-decay")
        bands = ["Healthy", "Urgent", "Recommended", "Critical"]
        for band in bands:
            assert band in content, f"blog-decay: missing decay band '{band}'"

    def test_gsc_flag_documented(self):
        content = read_skill("blog-decay")
        assert "--gsc" in content, "blog-decay: --gsc flag not documented"


class TestBlogStyle:
    def test_has_nng_dimensions(self):
        content = read_skill("blog-style")
        axes = ["Funny", "Serious", "Formal", "Casual", "Respectful", "Irreverent",
                "Enthusiastic", "Matter-of-fact"]
        for axis in axes:
            assert axis in content, f"blog-style: missing NNGroup axis '{axis}'"

    def test_saves_to_personas_dir(self):
        content = read_skill("blog-style")
        assert "personas/" in content, "blog-style: should save profiles to personas/ directory"

    def test_minimum_post_requirement(self):
        content = read_skill("blog-style")
        assert "5" in content and "post" in content.lower(), (
            "blog-style: should document minimum post requirement (5 posts)"
        )


class TestBlogSxo:
    def test_has_serp_features(self):
        content = read_skill("blog-sxo")
        features = ["Featured Snippet", "PAA", "Rich Results", "Image Pack"]
        for f in features:
            assert f in content, f"blog-sxo: missing SERP feature '{f}'"

    def test_has_scoring_table(self):
        content = read_skill("blog-sxo")
        assert "Weight" in content and "Score" in content, (
            "blog-sxo: scoring table must show weights"
        )

    def test_snippet_format_guidance(self):
        content = read_skill("blog-sxo")
        assert "40-60" in content or "40–60" in content, (
            "blog-sxo: should specify 40-60 word snippet format"
        )


class TestBlogEmailSequence:
    def test_has_five_email_types(self):
        content = read_skill("blog-email-sequence")
        emails = ["Hook", "Problem", "Insight", "Method", "CTA"]
        for e in emails:
            assert e in content, f"blog-email-sequence: missing email type '{e}'"

    def test_word_limit_documented(self):
        content = read_skill("blog-email-sequence")
        assert "300" in content, "blog-email-sequence: 300-word limit should be documented"

    def test_subject_line_limit(self):
        content = read_skill("blog-email-sequence")
        assert "50" in content and "character" in content.lower() or "chars" in content.lower(), (
            "blog-email-sequence: 50-char subject line limit should be documented"
        )


class TestBlogQuiz:
    def test_has_quiz_types(self):
        content = read_skill("blog-quiz")
        types = ["Knowledge", "Assessment", "Personality"]
        for t in types:
            assert t in content, f"blog-quiz: missing quiz type '{t}'"

    def test_html_output_documented(self):
        content = read_skill("blog-quiz")
        assert "html" in content.lower() and "embed" in content.lower(), (
            "blog-quiz: HTML embed output must be documented"
        )

    def test_no_all_of_the_above(self):
        content = read_skill("blog-quiz")
        # Skill should mention the ban on "All of the above"
        assert "All of the above" in content, (
            "blog-quiz: should explicitly ban 'All of the above' answer options"
        )
        # Ban should be in a negative context (No, Never, avoid, not)
        idx = content.find("All of the above")
        surrounding = content[max(0, idx - 80):idx + 40].lower()
        banned_context = ["no ", "never", "avoid", "not ", "without"]
        assert any(w in surrounding for w in banned_context), (
            "blog-quiz: 'All of the above' must appear in a prohibition context"
        )


class TestBlogGlossary:
    def test_mentions_defined_term_schema(self):
        content = read_skill("blog-glossary")
        assert "DefinedTermSet" in content or "DefinedTerm" in content, (
            "blog-glossary: should generate DefinedTermSet schema"
        )

    def test_has_frequency_filter(self):
        content = read_skill("blog-glossary")
        assert "--min-frequency" in content, (
            "blog-glossary: --min-frequency flag must be documented"
        )

    def test_back_link_option(self):
        content = read_skill("blog-glossary")
        assert "--link" in content, "blog-glossary: --link flag must be documented"


class TestBlogAccessibility:
    def test_has_wcag_criteria(self):
        content = read_skill("blog-accessibility")
        criteria = ["1.1.1", "1.3.1", "2.4.4", "3.1.1"]
        for c in criteria:
            assert c in content, f"blog-accessibility: missing WCAG criterion {c}"

    def test_has_eight_checks(self):
        content = read_skill("blog-accessibility")
        # Should reference 8 checks in the scoring model
        assert "16" in content, "blog-accessibility: max score of 16 (8 checks × 2) should be documented"

    def test_fix_mode_documented(self):
        content = read_skill("blog-accessibility")
        assert "--fix" in content, "blog-accessibility: --fix auto-repair flag must be documented"


class TestBlogPodcastBrief:
    def test_has_three_formats(self):
        content = read_skill("blog-podcast-brief")
        formats = ["Solo", "Interview", "Panel"]
        for f in formats:
            assert f in content, f"blog-podcast-brief: missing format '{f}'"

    def test_has_duration_mapping(self):
        content = read_skill("blog-podcast-brief")
        assert "15 min" in content or "15-min" in content.lower(), (
            "blog-podcast-brief: duration mapping table must include 15-minute option"
        )

    def test_show_notes_section(self):
        content = read_skill("blog-podcast-brief")
        assert "Show Notes" in content or "show-notes" in content.lower(), (
            "blog-podcast-brief: show notes section must be documented"
        )


class TestBlogKeywordResearch:
    def test_has_keyword_tiers(self):
        content = read_skill("blog-keyword-research")
        tiers = ["Head terms", "Body keywords", "Long-tail", "Question keywords", "LSI"]
        for t in tiers:
            assert t in content, f"blog-keyword-research: missing keyword tier '{t}'"

    def test_has_difficulty_signals(self):
        content = read_skill("blog-keyword-research")
        assert "SERP" in content and "difficulty" in content.lower(), (
            "blog-keyword-research: difficulty estimation must reference SERP analysis"
        )

    def test_has_depth_modes(self):
        content = read_skill("blog-keyword-research")
        modes = ["quick", "standard", "deep"]
        for m in modes:
            assert m in content, f"blog-keyword-research: missing depth mode '{m}'"

    def test_no_api_key_required(self):
        content = read_skill("blog-keyword-research")
        blocked = ["ahrefs api key", "semrush api key", "moz api"]
        for b in blocked:
            assert b.lower() not in content.lower(), (
                f"blog-keyword-research: must not require {b} — Claude-native only"
            )


class TestBlogDrift:
    def test_has_three_modes(self):
        content = read_skill("blog-drift")
        modes = ["--baseline", "--check", "--diff"]
        for m in modes:
            assert m in content, f"blog-drift: missing mode '{m}'"

    def test_stores_in_blog_drift_dir(self):
        content = read_skill("blog-drift")
        assert ".blog-drift/" in content, (
            "blog-drift: baselines must be stored in .blog-drift/ directory"
        )

    def test_has_drift_classification(self):
        content = read_skill("blog-drift")
        bands = ["No Drift", "Minor Drift", "Moderate Drift", "Severe Drift"]
        for band in bands:
            assert band in content, f"blog-drift: missing drift classification '{band}'"


class TestBlogDashboard:
    def test_has_status_bands(self):
        content = read_skill("blog-dashboard")
        bands = ["Excellent", "Healthy", "Needs Attention", "Needs Work", "Critical"]
        for band in bands:
            assert band in content, f"blog-dashboard: missing status band '{band}'"

    def test_html_output_documented(self):
        content = read_skill("blog-dashboard")
        assert "html" in content.lower(), "blog-dashboard: HTML output must be documented"

    def test_no_external_cdn(self):
        content = read_skill("blog-dashboard")
        assert "No external CDN" in content or "no external CDN" in content.lower(), (
            "blog-dashboard: must specify no external CDN dependencies"
        )
