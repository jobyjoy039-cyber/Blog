"""Sequential pipeline runner — chains all 19 agents in order."""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from orchestrator.memory_manager import MemoryManager, SharedContext
from agents import (
    TopicAgent, KeywordAgent, IntentAgent, CompetitorAgent, BriefAgent,
    OutlineAgent, SEOAgent, ResearchAgent, ExpertAgent, WriterAgent,
    HumanizerAgent, ReadabilityAgent, AISearchAgent, FactCheckerAgent,
    InternalLinkAgent, SchemaAgent, CTAAgent, FinalEditorAgent, QAAgent
)

console = Console()

PIPELINE_STAGES = [
    ("topic_understanding",    TopicAgent,         "Topic Understanding"),
    ("keyword_research",       KeywordAgent,        "Keyword Research"),
    ("search_intent",          IntentAgent,         "Search Intent Analysis"),
    ("competitor_analysis",    CompetitorAgent,     "Competitor Analysis"),
    ("content_brief",          BriefAgent,          "Content Brief"),
    ("outline_architect",      OutlineAgent,        "Outline Architecture"),
    ("seo_strategy",           SEOAgent,            "SEO Strategy"),
    ("deep_research",          ResearchAgent,       "Deep Research"),
    ("expert_insights",        ExpertAgent,         "Expert Insights"),
    ("first_draft",            WriterAgent,         "First Draft Writing"),
    ("humanization",           HumanizerAgent,      "Humanization"),
    ("readability",            ReadabilityAgent,    "Readability Optimization"),
    ("ai_search",              AISearchAgent,       "AI Search Optimization"),
    ("fact_check",             FactCheckerAgent,    "Fact Checking"),
    ("internal_links",         InternalLinkAgent,   "Internal Linking"),
    ("schema_markup",          SchemaAgent,         "Schema Generation"),
    ("cta_optimization",       CTAAgent,            "CTA Optimization"),
    ("final_edit",             FinalEditorAgent,    "Final Editing"),
    ("quality_assurance",      QAAgent,             "Quality Assurance"),
]


class BlogPipeline:
    def __init__(self, config: dict, anthropic_api_key: Optional[str] = None):
        self.config = config
        self.client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else anthropic.Anthropic()
        self.memory = MemoryManager()
        self.output_dir = Path(config.get("pipeline", {}).get("output_dir", "outputs"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, topic: str, brand_voice: str = "", article_goal: str = "",
            start_from: Optional[str] = None, stop_at: Optional[str] = None) -> dict:
        """Run the full 19-agent pipeline sequentially."""
        shared = SharedContext(topic=topic, brand_voice=brand_voice, article_goal=article_goal)
        context = self.memory.to_dict(shared)

        start_active = start_from is None
        results = {"topic": topic, "stages": {}, "start_time": datetime.now().isoformat()}

        console.print(f"\n[bold cyan]Starting Blog Pipeline[/bold cyan]: {topic}")
        console.print(f"[dim]Running {len(PIPELINE_STAGES)} agents sequentially[/dim]\n")

        for stage_key, AgentClass, stage_name in PIPELINE_STAGES:
            if start_from and stage_key == start_from:
                start_active = True
            if not start_active:
                console.print(f"[dim]Skipping: {stage_name}[/dim]")
                continue

            console.print(f"[cyan]→ {stage_name}[/cyan]", end=" ")
            stage_start = time.time()

            try:
                agent = AgentClass(client=self.client, config=self.config, name=stage_name)
                output = agent.run(context)
                elapsed = time.time() - stage_start
                console.print(f"[green]✓[/green] [dim]({elapsed:.1f}s)[/dim]")
                results["stages"][stage_key] = {"status": "success", "elapsed": elapsed, "output": output}

                if self.config.get("pipeline", {}).get("save_intermediate", True):
                    self._save_intermediate(stage_key, context, output)

            except Exception as e:
                elapsed = time.time() - stage_start
                console.print(f"[red]✗ Error: {e}[/red]")
                results["stages"][stage_key] = {"status": "error", "error": str(e), "elapsed": elapsed}
                raise

            if stop_at and stage_key == stop_at:
                break

        results["final_article"] = context.get("draft_content", "")
        results["quality_scores"] = context.get("quality_scores", {})
        results["seo_metadata"] = context.get("seo_metadata", {})
        results["schema_markup"] = context.get("schema_markup", {})
        results["end_time"] = datetime.now().isoformat()

        self._save_final(topic, results, context)
        return results

    def _save_intermediate(self, stage_key: str, context: dict, output: dict) -> None:
        stage_dir = self.output_dir / "intermediate"
        stage_dir.mkdir(exist_ok=True)
        path = stage_dir / f"{stage_key}.json"
        with open(path, "w") as f:
            json.dump({"context_snapshot": dict(context), "agent_output": output}, f, indent=2, default=str)

    def _save_final(self, topic: str, results: dict, context: dict) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join(c if c.isalnum() or c in "-_" else "_" for c in topic.lower().replace(" ", "_"))[:50]

        # Save full JSON report
        report_path = self.output_dir / f"{safe_topic}_{ts}_report.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        # Save article markdown
        article = context.get("draft_content", "")
        if article:
            article_path = self.output_dir / f"{safe_topic}_{ts}_article.md"
            with open(article_path, "w") as f:
                f.write(f"# {topic}\n\n")
                f.write(article)
            console.print(f"\n[bold green]Article saved:[/bold green] {article_path}")

        console.print(f"[bold green]Report saved:[/bold green] {report_path}")
