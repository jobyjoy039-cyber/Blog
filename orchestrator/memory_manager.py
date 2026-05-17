import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class SharedContext:
    """
    Shared state passed between all agents in the blog writing pipeline.

    Each agent reads relevant fields from this context and writes its results
    back. The MemoryManager handles serialisation to disk and updates from
    agent output payloads.
    """

    # --- Topic & keyword research ---
    topic: str = ""
    primary_keyword: str = ""
    secondary_keywords: list = field(default_factory=list)

    # --- Search & audience analysis ---
    search_intent: str = ""
    audience_profile: str = ""
    brand_voice: str = ""
    tone: str = "conversational"
    article_goal: str = ""

    # --- Competitive & SEO research ---
    competitor_gaps: list = field(default_factory=list)
    seo_strategy: dict = field(default_factory=dict)

    # --- Content research ---
    research_data: list = field(default_factory=list)
    expert_insights: list = field(default_factory=list)

    # --- Article structure ---
    article_outline: dict = field(default_factory=dict)

    # --- Draft & final content ---
    draft_content: str = ""

    # --- On-page optimisation ---
    internal_links: list = field(default_factory=list)
    schema_markup: dict = field(default_factory=dict)
    cta_strategy: dict = field(default_factory=dict)

    # --- Quality & metadata ---
    quality_scores: dict = field(default_factory=dict)
    image_prompts: list = field(default_factory=list)
    seo_metadata: dict = field(default_factory=dict)

    # --- Pipeline bookkeeping ---
    pipeline_stage: str = "initialized"
    agent_outputs: dict = field(default_factory=dict)


class MemoryManager:
    """
    Manages persistence and retrieval of the SharedContext across pipeline stages.

    Saves context snapshots as JSON files to an output directory so that
    partial results can be inspected, resumed, or replayed without re-running
    expensive upstream agents.
    """

    def __init__(self, output_dir: str = "outputs"):
        """
        Initialise the MemoryManager and create the output directory if needed.

        Args:
            output_dir: Path to the directory where context JSON files are saved.
        """
        self.output_dir = output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self, context: SharedContext) -> dict:
        """
        Convert a SharedContext dataclass instance to a plain dict.

        Args:
            context: The SharedContext to serialise.

        Returns:
            A JSON-serialisable dict representation.
        """
        return asdict(context)

    def from_dict(self, data: dict) -> SharedContext:
        """
        Reconstruct a SharedContext from a plain dict (e.g. loaded from JSON).

        Unknown keys in *data* are silently ignored so that saved files from
        older schema versions can still be loaded without raising errors.

        Args:
            data: Dict containing SharedContext field values.

        Returns:
            A fully populated SharedContext instance.
        """
        # Only pass keys that are valid SharedContext fields
        valid_fields = {f.name for f in SharedContext.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return SharedContext(**filtered)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, context: SharedContext, filename: str = None) -> str:
        """
        Serialise and save a SharedContext snapshot to disk as JSON.

        Args:
            context: The SharedContext to save.
            filename: Optional filename (without path). When omitted a
                      timestamped name is generated automatically.

        Returns:
            The absolute path to the saved JSON file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stage = context.pipeline_stage.replace(" ", "_")
            filename = f"context_{stage}_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)
        data = self.to_dict(context)
        data["_saved_at"] = datetime.now().isoformat()

        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

        return filepath

    def load(self, filename: str) -> SharedContext:
        """
        Load a SharedContext snapshot from a JSON file.

        Args:
            filename: Either a bare filename (resolved relative to output_dir)
                      or an absolute path.

        Returns:
            The deserialised SharedContext instance.

        Raises:
            FileNotFoundError: If the file does not exist at the resolved path.
        """
        if not os.path.isabs(filename):
            filepath = os.path.join(self.output_dir, filename)
        else:
            filepath = filename

        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Remove internal bookkeeping key before deserialising
        data.pop("_saved_at", None)
        return self.from_dict(data)

    # ------------------------------------------------------------------
    # Agent integration
    # ------------------------------------------------------------------

    def update_from_agent_output(
        self,
        context: SharedContext,
        agent_name: str,
        agent_output: dict,
    ) -> SharedContext:
        """
        Apply an agent's result dict to the shared context in-place.

        The top-level agent output envelope (produced by BaseAgent.format_output)
        is stored verbatim under context.agent_outputs[agent_name]. The nested
        "output" payload is then inspected and any keys that match SharedContext
        fields are written directly onto the context object, allowing agents to
        update shared state without knowing the full context schema.

        Args:
            context: The SharedContext to update.
            agent_name: Identifier for the agent (used as the key in agent_outputs).
            agent_output: The dict returned by the agent's run() method.

        Returns:
            The mutated SharedContext (same object, returned for chaining).
        """
        # Store the full agent output envelope for auditability
        context.agent_outputs[agent_name] = agent_output

        # Extract the inner payload and apply any matching SharedContext fields
        payload: dict = agent_output.get("output", {})
        valid_fields = {f.name for f in SharedContext.__dataclass_fields__.values()}  # type: ignore[attr-defined]

        for key, value in payload.items():
            if key in valid_fields:
                setattr(context, key, value)

        # Always advance the pipeline stage when present in the payload
        if "pipeline_stage" in payload:
            context.pipeline_stage = payload["pipeline_stage"]

        return context
