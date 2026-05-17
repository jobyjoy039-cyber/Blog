"""Multi-Agent Blog Writing System — CLI entry point."""
import typer
from typing import Optional
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Multi-Agent Blog Writing System powered by Claude")
console = Console()


@app.command()
def generate(
    topic: str = typer.Argument(..., help="Blog topic to write about"),
    brand_voice: str = typer.Option("", "--brand-voice", "-b", help="Brand voice description"),
    article_goal: str = typer.Option("", "--goal", "-g", help="Article goal (e.g. 'drive signups')"),
    config: str = typer.Option("config/settings.yaml", "--config", "-c", help="Config file path"),
    start_from: Optional[str] = typer.Option(None, "--start-from", help="Start from specific stage"),
    stop_at: Optional[str] = typer.Option(None, "--stop-at", help="Stop at specific stage"),
):
    """Generate a complete SEO-optimized blog article using 19 specialized AI agents."""
    from orchestrator.pipeline_controller import run_pipeline

    console.print(Panel.fit(
        f"[bold cyan]Multi-Agent Blog Writing System[/bold cyan]\n"
        f"Topic: [yellow]{topic}[/yellow]",
        border_style="cyan"
    ))

    try:
        results = run_pipeline(
            topic=topic,
            brand_voice=brand_voice,
            article_goal=article_goal,
            config_path=config,
            start_from=start_from,
            stop_at=stop_at,
        )
        scores = results.get("quality_scores", {})
        if scores:
            console.print(f"\n[bold]Quality Scores:[/bold] {scores}")
        console.print("\n[bold green]Pipeline complete![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Pipeline failed:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def list_stages():
    """List all 19 pipeline stages and their stage keys."""
    from orchestrator.workflow import PIPELINE_STAGES
    console.print("\n[bold]Pipeline Stages:[/bold]")
    for i, (key, _, name) in enumerate(PIPELINE_STAGES, 1):
        console.print(f"  {i:2}. [cyan]{key:25}[/cyan] {name}")


if __name__ == "__main__":
    app()
