from ..config import Settings
from .base import Capability, Registry
from .brain_claude import ClaudeAnalyzer, ClaudeScriptWriter
from .brain_local import LocalAnalyzer, TemplateScriptWriter
from .ingest import ManualIngest, WebIngest
from .render_ffmpeg import FFmpegRenderer
from .voice import ProportionalAligner, SilentVoice, VoiceStudioVoice
from .voice_kitten import KittenVoice


def build_registry(settings: Settings) -> Registry:
    """Register every built-in plugin. Third-party plugins can be added with
    registry.register(...) before the app starts."""
    reg = Registry(settings.preferred)
    for plugin in (
        ManualIngest(settings.data_dir / "uploads"),
        WebIngest(settings.fetch_user_agent, allow_private=settings.allow_private_urls),
        ClaudeAnalyzer(settings.anthropic_model),
        LocalAnalyzer(),
        ClaudeScriptWriter(settings.anthropic_model),
        TemplateScriptWriter(),
        KittenVoice(settings.kitten_model, settings.kitten_voice, settings.voice_speed),
        VoiceStudioVoice(settings.voicestudio_url, settings.voicestudio_engine, settings.voice_speed),
        SilentVoice(),
        ProportionalAligner(),
        FFmpegRenderer(settings.font),
    ):
        reg.register(plugin)
    return reg


__all__ = ["Capability", "Registry", "build_registry"]
