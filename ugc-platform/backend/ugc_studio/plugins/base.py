"""Plugin contracts and the registry.

Every open-source project or model is wrapped as one plugin that implements a
single capability. The orchestrator asks the registry for a capability's
"chain": the preferred plugin first, then every other available plugin as a
fallback. Swapping a model is a registry call, not a code change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from ..domain import (
    Analysis, JobRequest, ProductInfo, RenderInput, RenderOutput, Script, Word,
)


class Capability(str, Enum):
    ingest = "ingest"
    analyze = "analyze"
    script = "script"
    voice = "voice"
    align = "align"
    render = "render"


class Plugin(ABC):
    name: str
    capability: Capability
    version: str = "1"
    priority: int = 50  # lower runs first when no preference is set
    license: str = ""
    commercial_ok: bool = True
    description: str = ""

    def available(self) -> tuple[bool, str]:
        """Return (ok, reason). Checked on every chain lookup, so keep it cheap."""
        return True, ""

    def info(self) -> dict:
        ok, reason = self.available()
        return {
            "name": self.name,
            "capability": self.capability.value,
            "version": self.version,
            "available": ok,
            "reason": reason,
            "license": self.license,
            "commercial_ok": self.commercial_ok,
            "description": self.description,
        }


class IngestPlugin(Plugin):
    capability = Capability.ingest

    @abstractmethod
    def can_handle(self, request: JobRequest) -> bool: ...

    @abstractmethod
    def ingest(self, request: JobRequest, workdir: Path) -> ProductInfo: ...


class AnalyzePlugin(Plugin):
    capability = Capability.analyze

    @abstractmethod
    def analyze(self, product: ProductInfo) -> Analysis: ...


class ScriptPlugin(Plugin):
    capability = Capability.script

    @abstractmethod
    def write(self, product: ProductInfo, analysis: Analysis, request: JobRequest) -> Script: ...


class VoicePlugin(Plugin):
    capability = Capability.voice

    @abstractmethod
    def synthesize(self, text: str, out_path: Path, request: JobRequest) -> float:
        """Write a WAV to out_path and return its duration in seconds."""


class AlignPlugin(Plugin):
    capability = Capability.align

    @abstractmethod
    def align(self, text: str, audio_path: Path, duration: float) -> list[Word]: ...


class RenderPlugin(Plugin):
    capability = Capability.render

    @abstractmethod
    def render(self, data: RenderInput, out_dir: Path) -> RenderOutput: ...


class NoPluginAvailable(RuntimeError):
    pass


class Registry:
    def __init__(self, preferred: dict[str, str] | None = None):
        self._plugins: dict[Capability, dict[str, Plugin]] = {c: {} for c in Capability}
        self._preferred: dict[Capability, str] = {}
        for cap, name in (preferred or {}).items():
            self._preferred[Capability(cap)] = name

    def register(self, plugin: Plugin) -> None:
        self._plugins[plugin.capability][plugin.name] = plugin

    def get(self, capability: Capability, name: str) -> Plugin:
        try:
            return self._plugins[capability][name]
        except KeyError:
            raise KeyError(f"No {capability.value} plugin named {name!r}") from None

    def set_preferred(self, capability: Capability, name: str) -> None:
        self.get(capability, name)  # validates
        self._preferred[capability] = name

    def preferred(self, capability: Capability) -> str | None:
        return self._preferred.get(capability)

    def all(self) -> list[Plugin]:
        return [p for cap in Capability for p in self._plugins[cap].values()]

    def chain(self, capability: Capability) -> list[Plugin]:
        plugins = sorted(self._plugins[capability].values(), key=lambda p: (p.priority, p.name))
        pref = self._preferred.get(capability)
        if pref:
            plugins.sort(key=lambda p: p.name != pref)
        chain = [p for p in plugins if p.available()[0]]
        if not chain:
            raise NoPluginAvailable(f"No available plugin for {capability.value}")
        return chain
