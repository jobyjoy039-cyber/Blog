"""Domain models shared by every module. Plugins only exchange these types."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Platform(str, Enum):
    tiktok = "tiktok"
    reels = "reels"
    shorts = "shorts"
    snapchat = "snapchat"
    facebook = "facebook"
    pinterest = "pinterest"
    youtube = "youtube"
    amazon = "amazon"
    flipkart = "flipkart"


# width, height at 1080p-class resolution
PLATFORM_FRAME: dict[Platform, tuple[int, int]] = {
    Platform.tiktok: (1080, 1920),
    Platform.reels: (1080, 1920),
    Platform.shorts: (1080, 1920),
    Platform.snapchat: (1080, 1920),
    Platform.facebook: (1080, 1350),
    Platform.pinterest: (1000, 1500),
    Platform.youtube: (1920, 1080),
    Platform.amazon: (1920, 1080),
    Platform.flipkart: (1080, 1080),
}

RESOLUTION_SCALE = {"720p": 2 / 3, "1080p": 1.0, "4k": 2.0}


class Framework(str, Enum):
    pas = "PAS"
    aida = "AIDA"
    bab = "BAB"
    problem_solution = "PROBLEM_SOLUTION"
    unboxing = "UNBOXING"
    founder = "FOUNDER"
    educational = "EDUCATIONAL"
    comparison = "COMPARISON"


class ManualBrief(BaseModel):
    """Product details typed or uploaded by the user instead of a link."""

    title: str
    description: str = ""
    price: str = ""
    brand: str = ""
    features: list[str] = Field(default_factory=list)
    reviews: list[str] = Field(default_factory=list)
    upload_ids: list[str] = Field(default_factory=list, description="IDs returned by POST /uploads")


class JobRequest(BaseModel):
    url: str | None = None
    brief: ManualBrief | None = None
    platform: Platform = Platform.tiktok
    framework: Framework = Framework.pas
    resolution: str = "1080p"
    target_seconds: int = Field(30, ge=8, le=90)
    language: str = "en"
    voice: str | None = Field(None, description="Engine-specific voice/profile id")
    music_upload_id: str | None = None
    script_override: Script | None = Field(None, description="Skip script generation and render this script")

    @model_validator(mode="after")
    def _needs_source(self) -> "JobRequest":
        if not self.url and not self.brief:
            raise ValueError("Provide a product url or a manual brief")
        if self.resolution not in RESOLUTION_SCALE:
            raise ValueError(f"resolution must be one of {sorted(RESOLUTION_SCALE)}")
        return self

    def frame(self) -> tuple[int, int]:
        w, h = PLATFORM_FRAME[self.platform]
        s = RESOLUTION_SCALE[self.resolution]
        return int(round(w * s / 2) * 2), int(round(h * s / 2) * 2)


class ProductInfo(BaseModel):
    title: str
    brand: str = ""
    description: str = ""
    price: str = ""
    currency: str = ""
    features: list[str] = Field(default_factory=list)
    specs: dict[str, str] = Field(default_factory=dict)
    rating: float | None = None
    review_count: int | None = None
    reviews: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list, description="Local file paths")
    source_url: str | None = None
    source: str = ""


class Analysis(BaseModel):
    audience: str
    pain_points: list[str]
    desires: list[str]
    usps: list[str]
    objections: list[str]
    emotional_triggers: list[str]
    hooks: list[str]
    proof_points: list[str] = Field(description="Only facts present in the product data")
    claim_warnings: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    kind: str = Field(description="hook | problem | agitate | solution | proof | cta | ...")
    voice: str = Field(description="Line spoken by the voiceover")
    on_screen: str = Field("", description="Short headline shown on screen (max ~6 words)")
    image_index: int = 0


class Script(BaseModel):
    framework: str
    title: str
    scenes: list[Scene]
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)

    def full_text(self) -> str:
        return " ".join(s.voice for s in self.scenes)


class Word(BaseModel):
    text: str
    start: float
    end: float


class SceneAudio(BaseModel):
    path: str
    duration: float
    words: list[Word] = Field(default_factory=list)


class RenderInput(BaseModel):
    product: ProductInfo
    script: Script
    scene_audio: list[SceneAudio]
    width: int
    height: int
    music_path: str | None = None


class RenderOutput(BaseModel):
    video: str
    thumbnail: str
    duration: float


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class StepTrace(BaseModel):
    step: str
    plugin: str
    cached: bool = False
    seconds: float = 0.0
    fallbacks: list[str] = Field(default_factory=list, description="Plugins that failed before this one")


class Job(BaseModel):
    id: str
    status: JobStatus
    progress: float = 0.0
    step: str = ""
    request: JobRequest
    product: ProductInfo | None = None
    analysis: Analysis | None = None
    script: Script | None = None
    output: RenderOutput | None = None
    trace: list[StepTrace] = Field(default_factory=list)
    error: str | None = None
    created_at: float
    updated_at: float


JobRequest.model_rebuild()
