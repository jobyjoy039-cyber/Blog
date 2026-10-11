import io
import shutil
from pathlib import Path

import pytest
from PIL import Image

from ugc_studio.domain import JobRequest, ManualBrief, ProductInfo, RenderInput, RenderOutput
from ugc_studio.plugins.base import RenderPlugin, VoicePlugin
from ugc_studio.plugins.voice import SilentVoice

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

PRODUCT_HTML = """<html><head><title>Fallback title</title>
<meta property="og:image" content="/og.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"WebSite","name":"Shop"},
 {"@type":"Product","name":"GripMount Magnetic Car Phone Mount","brand":{"@type":"Brand","name":"GripMount"},
  "description":"Snaps on in two seconds.<br>Holds phones up to 300 g through potholes.<br>One-hand release.",
  "image":["/a.jpg",{"url":"/b.jpg"}],
  "offers":[{"@type":"Offer","price":"28.00","priceCurrency":"USD"}],
  "aggregateRating":{"ratingValue":"4.6","reviewCount":"1843"},
  "review":[{"reviewBody":"My old suction mount kept falling, this one holds."}],
  "additionalProperty":[{"name":"Weight","value":"80 g"}]}]}</script>
</head><body></body></html>"""


def jpeg_bytes(color=(200, 60, 60), size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def product(tmp_path: Path) -> ProductInfo:
    img = tmp_path / "p.jpg"
    img.write_bytes(jpeg_bytes())
    return ProductInfo(
        title="GripMount Magnetic Car Phone Mount", brand="GripMount", price="28.00", currency="USD",
        description="Snaps on in two seconds.", features=["Snaps on in two seconds", "Holds 300 g through potholes"],
        rating=4.6, review_count=1843, reviews=["My old suction mount kept falling, this one holds."],
        images=[str(img)],
    )


@pytest.fixture
def brief_request() -> JobRequest:
    return JobRequest(brief=ManualBrief(title="GripMount", description="Snaps on in two seconds.", price="28"),
                      target_seconds=20, resolution="720p")


class FakeVoice(VoicePlugin):
    """Silence of a fixed length per word: fast and deterministic."""

    name = "fake-voice"
    priority = 1

    def synthesize(self, text, out_path, request):
        return SilentVoice().synthesize(text, out_path, request)


class FakeRender(RenderPlugin):
    name = "fake-render"
    priority = 1

    def render(self, data: RenderInput, out_dir: Path) -> RenderOutput:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ad.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        (out_dir / "thumbnail.jpg").write_bytes(jpeg_bytes())
        return RenderOutput(video=str(out_dir / "ad.mp4"), thumbnail=str(out_dir / "thumbnail.jpg"),
                            duration=sum(a.duration for a in data.scene_audio))
