"""Pipeline controller — loads config, sets up environment, delegates to BlogPipeline."""
import os
import yaml
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from orchestrator.workflow import BlogPipeline


def load_config(config_path: str = "config/settings.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def create_pipeline(config_path: str = "config/settings.yaml",
                    anthropic_api_key: Optional[str] = None) -> BlogPipeline:
    load_dotenv()
    config = load_config(config_path)
    api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to .env or pass anthropic_api_key parameter.")
    return BlogPipeline(config=config, anthropic_api_key=api_key)


def run_pipeline(topic: str, brand_voice: str = "", article_goal: str = "",
                 config_path: str = "config/settings.yaml",
                 start_from: Optional[str] = None,
                 stop_at: Optional[str] = None) -> dict:
    pipeline = create_pipeline(config_path)
    return pipeline.run(topic=topic, brand_voice=brand_voice, article_goal=article_goal,
                        start_from=start_from, stop_at=stop_at)
