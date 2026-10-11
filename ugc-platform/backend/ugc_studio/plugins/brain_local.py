"""Offline marketing brain: rule-based analysis and framework script templates.

Always available, so the pipeline works with no API keys. The Claude plugins
produce better copy and take over automatically when configured.
"""
from __future__ import annotations

import re

from ..domain import Analysis, Framework, JobRequest, ProductInfo, Scene, Script
from .base import AnalyzePlugin, ScriptPlugin

WORDS_PER_SECOND = 2.3  # conservative: includes pauses between scenes

RISKY = [
    (r"\bguarantee[ds]?\b", "Guaranteed results need proof."),
    (r"\b(cure[sd]?|heal(s|ed)?|treat(s|ment)?)\b", "Medical claims need substantiation."),
    (r"\b(clinically|scientifically)\s+(proven|tested)\b", "Needs a citable study."),
    (r"(?<!\w)(100%|risk[- ]free)(?!\w)", "Absolute claim."),
    (r"\b(best|#1|number one)\b", "Superlative needs comparative proof."),
    (r"\b(unbreakable|indestructible|forever|permanent)\b", "Absolute durability claim."),
]


def claim_warnings(text: str) -> list[str]:
    out = []
    for pat, why in RISKY:
        for m in re.finditer(pat, text, re.I):
            out.append(f'"{m.group(0)}": {why}')
    return sorted(set(out))


def _short(s: str, words: int) -> str:
    w = re.sub(r"\s+", " ", s).strip().rstrip(".!").split(" ")
    return " ".join(w[:words])


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:] if s and not s[:2].isupper() else s


def short_name(p: ProductInfo) -> str:
    """'GripMount Magnetic Car Phone Mount' -> 'GripMount' (brand) or the first words."""
    if p.brand and p.brand.lower() in p.title.lower() and len(p.brand) <= 24:
        return p.brand
    return _short(re.split(r"[|,(–-]", p.title)[0], 3)


def _price(p: ProductInfo) -> str:
    if not p.price:
        return ""
    sym = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(p.currency.upper(), "")
    return f"{sym}{p.price}" if sym else f"{p.price} {p.currency}".strip()


class LocalAnalyzer(AnalyzePlugin):
    name = "local"
    priority = 90
    license = "MIT (this project)"
    description = "Rule-based analysis from the listing text. Offline."

    def analyze(self, product: ProductInfo) -> Analysis:
        feats = product.features or [product.description[:120]]
        name = short_name(product)
        benefits = [_short(f, 12) for f in feats[:4]]
        # Reviews that compare against what the buyer used before name the real pain.
        switched = [r for r in product.reviews if re.search(r"\b(old|previous|last one|other one|used to|kept)\b", r, re.I)]
        complaints = [r for r in product.reviews if re.search(r"\b(broke|bad|hard|difficult|return|poor|cheap)\b", r, re.I)]
        pains = [_short(_lower_first(re.split(r"[,;.!]", r)[0]), 12) for r in switched[:2]] or ["settling for something that doesn't do the job"]
        proof = []
        if product.rating and product.review_count:
            proof.append(f"{product.rating:g} stars from {product.review_count:,} reviews")
        proof += [_short(f, 14) for f in feats if re.search(r"\d", f)][:3]
        return Analysis(
            audience=f"people shopping for {_short(product.title, 6).lower()}",
            pain_points=pains + [_short(c, 14) for c in complaints[:2]],
            desires=benefits[:3],
            usps=benefits[:3],
            objections=["Is it worth the price?", "Will it actually work for me?"],
            emotional_triggers=["relief", "confidence", "saving time"],
            hooks=[
                f"Okay, I did not expect {name} to be this good.",
                f"Stop scrolling if you need {_lower_first(benefits[0]) if benefits else name}.",
                f"Here's what {name} actually does.",
            ],
            proof_points=proof or [_short(feats[0], 14)],
            claim_warnings=claim_warnings(" ".join([product.title, product.description, *product.features])),
        )


# Each framework is a sequence of (scene kind, line template). Templates use
# {name}, {benefit0..2}, {pain}, {proof}, {price}, {hook}.
FRAMEWORKS: dict[Framework, list[tuple[str, str]]] = {
    Framework.pas: [
        ("hook", "{hook}"),
        ("problem", "Real talk: {pain}. Sound familiar?"),
        ("agitate", "And the usual fixes just don't hold up."),
        ("solution", "That's why {name} stands out: {benefit0}."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
    Framework.aida: [
        ("hook", "{hook}"),
        ("interest", "{name} is all about {benefit0}."),
        ("desire", "Plus {benefit1}, and {benefit2}."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
    Framework.bab: [
        ("before", "Before: {pain}."),
        ("after", "After: {benefit0}."),
        ("bridge", "The bridge? {name}."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
    Framework.problem_solution: [
        ("problem", "Here's a problem nobody talks about: {pain}."),
        ("solution", "{name} fixes it with {benefit0}."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
    Framework.unboxing: [
        ("hook", "Let's open the {name} and see if it's worth it."),
        ("reveal", "First impression: {benefit0}."),
        ("detail", "I also like that {benefit1}."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
    Framework.founder: [
        ("hook", "We built {name} because we were tired of {pain}."),
        ("solution", "So we focused on one thing: {benefit0}."),
        ("detail", "And we added {benefit1}."),
        ("cta", "{cta}"),
    ],
    Framework.educational: [
        ("hook", "Quick tip if you deal with {pain}."),
        ("teach", "The trick is {benefit0}."),
        ("solution", "That's exactly what {name} is built for."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
    Framework.comparison: [
        ("hook", "The old way versus {name}."),
        ("old", "The old way: {pain}."),
        ("new", "With {name}: {benefit0}."),
        ("proof", "{proof}."),
        ("cta", "{cta}"),
    ],
}


class TemplateScriptWriter(ScriptPlugin):
    name = "templates"
    priority = 90
    license = "MIT (this project)"
    description = "Framework templates (PAS, AIDA, BAB, ...). Offline."

    def write(self, product: ProductInfo, analysis: Analysis, request: JobRequest) -> Script:
        name = short_name(product)
        benefits = (analysis.usps + analysis.desires + ["it just works"] * 3)[:3]
        price = _price(product)
        values = {
            "name": name,
            "hook": analysis.hooks[0] if analysis.hooks else f"You need to see {name}.",
            "pain": _lower_first(analysis.pain_points[0].rstrip(".")) if analysis.pain_points else "the daily hassle",
            "proof": _short(analysis.proof_points[0], 16)[:1].upper() + _short(analysis.proof_points[0], 16)[1:] if analysis.proof_points else "See it in action",
            "cta": f"It's {price}. Tap the link to get yours." if price else "Tap the link to get yours.",
        }
        for i, b in enumerate(benefits):
            values[f"benefit{i}"] = _lower_first(b.rstrip("."))
        steps = FRAMEWORKS[request.framework]
        n_img = max(1, len(product.images))
        scenes = []
        for i, (kind, tpl) in enumerate(steps):
            line = tpl.format(**values)
            on_screen = {"hook": _short(values["hook"], 6), "cta": "Link below 👇" if not price else f"{price} · Link below"}.get(kind, "")
            if kind in ("solution", "interest", "after", "new"):
                on_screen = name
            scenes.append(Scene(kind=kind, voice=line, on_screen=on_screen, image_index=i % n_img))
        scenes = _fit_length(scenes, request.target_seconds)
        tags = ["#" + re.sub(r"[^A-Za-z0-9]", "", w) for w in name.split()[:2]]
        return Script(
            framework=request.framework.value,
            title=f"{name}: {request.framework.value} ad",
            scenes=scenes,
            caption=f"{values['hook']} {name}, link in bio.",
            hashtags=[t for t in tags if len(t) > 2] + ["#ad", "#tiktokmademebuyit"],
        )


DROPPABLE = ("agitate", "detail", "desire", "teach", "old", "problem", "interest", "reveal", "before")


def _fit_length(scenes: list[Scene], target_s: int) -> list[Scene]:
    """Drop supporting scenes until the read time fits. Hook, solution, proof
    and CTA always stay."""
    def secs(sc):
        return sum(len(s.voice.split()) for s in sc) / WORDS_PER_SECOND
    scenes = list(scenes)
    for kind in DROPPABLE:
        if secs(scenes) <= target_s or len(scenes) <= 3:
            break
        scenes = [s for s in scenes if s.kind != kind] if sum(s.kind == kind for s in scenes) < len(scenes) else scenes
    return scenes
