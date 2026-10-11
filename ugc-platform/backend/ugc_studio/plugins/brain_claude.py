"""Claude-powered product analysis and script writing.

Available when the Anthropic SDK can find credentials (ANTHROPIC_API_KEY or an
`ant auth login` profile). Structured outputs return validated Pydantic objects.
Server-side refusal fallbacks are enabled so a declined request is re-run on a
fallback model inside the same call.
"""
from __future__ import annotations

import os

from pydantic import BaseModel

from ..domain import Analysis, JobRequest, ProductInfo, Scene, Script
from .base import AnalyzePlugin, ScriptPlugin

HONESTY_RULES = """\
Rules for every ad you write:
- Only state facts present in the product data. Never invent ratings, numbers, awards or results.
- The voiceover is a creator demonstrating the product in a paid ad. Never pose as a real customer and never write fake testimonials or fake personal results.
- No medical, financial or guaranteed-outcome claims unless the product data states them.
- Write the way people talk on TikTok/Reels: short, specific, concrete. No corporate language."""


def _product_brief(p: ProductInfo) -> str:
    lines = [f"Title: {p.title}", f"Brand: {p.brand}", f"Price: {p.price} {p.currency}".strip()]
    if p.rating:
        lines.append(f"Rating: {p.rating} from {p.review_count or 'unknown'} reviews")
    lines.append(f"Description:\n{p.description[:6000]}")
    if p.features:
        lines.append("Features:\n" + "\n".join(f"- {f}" for f in p.features))
    if p.specs:
        lines.append("Specs:\n" + "\n".join(f"- {k}: {v}" for k, v in p.specs.items()))
    if p.reviews:
        lines.append("Customer reviews (verbatim, may be partial):\n" + "\n".join(f"- {r}" for r in p.reviews[:40]))
    lines.append(f"Number of product images available: {len(p.images)}")
    return "\n".join(lines)


class _ScriptOut(BaseModel):
    title: str
    scenes: list[Scene]
    caption: str
    hashtags: list[str]


class _ClaudeBase:
    license = "Anthropic API (commercial terms)"
    commercial_ok = True

    def __init__(self, model: str):
        self.model = model
        self._client = None

    def available(self) -> tuple[bool, str]:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, "pip install 'ugc-studio[claude]'"
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("ANTHROPIC_PROFILE")
                or os.path.isdir(os.path.expanduser("~/.config/anthropic"))):
            return False, "No Anthropic credentials (set ANTHROPIC_API_KEY or run `ant auth login`)"
        return True, ""

    def _parse(self, system: str, prompt: str, schema: type[BaseModel]):
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic()
        response = self._client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declined this request")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise RuntimeError(f"No structured output (stop_reason={response.stop_reason})")
        return response.parsed_output


class ClaudeAnalyzer(_ClaudeBase, AnalyzePlugin):
    name = "claude"
    priority = 10
    description = "Claude reads the listing and reviews: audience, pain points, USPs, objections, hooks."

    def __init__(self, model: str):
        _ClaudeBase.__init__(self, model)

    def analyze(self, product: ProductInfo) -> Analysis:
        system = (
            "You are a direct-response creative strategist analyzing a product for UGC video ads.\n"
            + HONESTY_RULES
            + "\nproof_points must be facts copied from the data. Put any risky claim found in the listing into claim_warnings."
        )
        return self._parse(system, _product_brief(product), Analysis)


class ClaudeScriptWriter(_ClaudeBase, ScriptPlugin):
    name = "claude"
    priority = 10
    description = "Claude writes the scene-by-scene script in the chosen framework."

    def __init__(self, model: str):
        _ClaudeBase.__init__(self, model)

    def write(self, product: ProductInfo, analysis: Analysis, request: JobRequest) -> Script:
        words = int(request.target_seconds * 2.3)
        system = "You write short-form UGC video ad scripts.\n" + HONESTY_RULES
        prompt = (
            f"{_product_brief(product)}\n\nAnalysis:\n{analysis.model_dump_json(indent=1)}\n\n"
            f"Write a {request.target_seconds}-second {request.platform.value} ad using the "
            f"{request.framework.value} framework, in language '{request.language}'.\n"
            f"- About {words} spoken words in total, split into 4-7 scenes.\n"
            "- First scene is a scroll-stopping hook that works with the sound off; last scene is one clear CTA.\n"
            "- on_screen is a 2-6 word headline (empty string if the scene needs none).\n"
            f"- image_index picks which product image (0 to {max(0, len(product.images) - 1)}) to show.\n"
            "- Include #ad in hashtags."
        )
        out: _ScriptOut = self._parse(system, prompt, _ScriptOut)
        n = max(1, len(product.images))
        for s in out.scenes:
            s.image_index = min(max(0, s.image_index), n - 1)
        return Script(framework=request.framework.value, **out.model_dump())
