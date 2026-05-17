import anthropic
import yaml
import json
import os
import time
from typing import Any
from abc import ABC, abstractmethod
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class BaseAgent(ABC):
    """
    Base class for all blog writing pipeline agents.

    Provides shared utilities for calling Claude with prompt caching,
    adaptive thinking, and streaming. Subclasses implement the `run`
    method to perform their specific pipeline stage.
    """

    def __init__(self, client: anthropic.Anthropic, config: dict, name: str):
        """
        Initialize the base agent.

        Args:
            client: An instantiated anthropic.Anthropic client.
            config: The loaded application configuration dictionary (from settings.yaml).
            name: Human-readable name for this agent (used in output metadata).
        """
        self.client = client
        self.config = config
        self.name = name
        self.model_heavy = config.get("anthropic", {}).get("model_heavy", "claude-opus-4-7")
        self.model_standard = config.get("anthropic", {}).get("model_standard", "claude-sonnet-4-6")
        self.model_fast = config.get("anthropic", {}).get("model_fast", "claude-haiku-4-5")
        self.max_tokens = config.get("anthropic", {}).get("max_tokens", 8192)
        self.caching_enabled = config.get("anthropic", {}).get("caching", {}).get("enabled", True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
        reraise=True,
    )
    def call_claude(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        use_thinking: bool = False,
        use_cache: bool = True,
    ) -> str:
        """
        Call Claude with optional prompt caching and streaming.

        Builds the system prompt with cache_control when caching is enabled,
        streams the response, and returns the accumulated text content.

        Args:
            system_prompt: The system-level instruction for the agent.
            user_message: The user turn content to send.
            max_tokens: Maximum output tokens for this call.
            use_thinking: If True, enables adaptive thinking on the model.
            use_cache: If True and caching is globally enabled, adds
                       cache_control: ephemeral to the system prompt block.

        Returns:
            The full text response from Claude as a single string.
        """
        # Build system prompt with optional prompt caching
        if use_cache and self.caching_enabled:
            system: Any = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        # Build optional thinking parameter
        extra_params: dict[str, Any] = {}
        if use_thinking:
            extra_params["thinking"] = {"type": "adaptive"}
            extra_params["output_config"] = {
                "effort": self.config.get("anthropic", {})
                .get("thinking", {})
                .get("effort", "high")
            }

        messages = [{"role": "user", "content": user_message}]

        # Use streaming to avoid HTTP timeout on large outputs
        with self.client.messages.stream(
            model=self.model_heavy,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            **extra_params,
        ) as stream:
            final_message = stream.get_final_message()

        # Extract text from all text blocks in the response
        text_parts: list[str] = []
        for block in final_message.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "\n".join(text_parts)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
        reraise=True,
    )
    def call_claude_deep_research(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 8192,
    ) -> str:
        """
        Call Claude with deep research settings: adaptive thinking at high effort.

        Uses the heavy model with adaptive thinking enabled and effort set to
        "high" for maximum reasoning quality on research tasks. Streaming is
        used to prevent HTTP timeouts on long outputs.

        Args:
            system_prompt: The system-level instruction for the research task.
            user_message: The research query or task description.
            max_tokens: Maximum output tokens (defaults to 8192 for deep tasks).

        Returns:
            The full text response from Claude as a single string.
        """
        thinking_effort = (
            self.config.get("anthropic", {})
            .get("thinking", {})
            .get("effort", "high")
        )

        system: Any
        if self.caching_enabled:
            system = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system = system_prompt

        with self.client.messages.stream(
            model=self.model_heavy,
            max_tokens=max_tokens,
            system=system,
            thinking={"type": "adaptive"},
            output_config={"effort": thinking_effort},
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            final_message = stream.get_final_message()

        text_parts: list[str] = []
        for block in final_message.content:
            if block.type == "text":
                text_parts.append(block.text)

        return "\n".join(text_parts)

    @abstractmethod
    def run(self, context: dict) -> dict:
        """
        Execute this agent's pipeline stage.

        Subclasses must implement this method. It receives the shared pipeline
        context dictionary and returns a result dictionary that will be merged
        back into the shared context by the orchestrator.

        Args:
            context: The current shared pipeline context (a dict representation
                     of SharedContext from the memory manager).

        Returns:
            A dict containing the agent's output, typically produced by calling
            self.format_output().
        """
        ...

    def format_output(self, improvements: list, output: dict) -> dict:
        """
        Wrap agent output in a standard metadata envelope.

        Args:
            improvements: A list of strings describing what this agent improved
                          or contributed (shown in pipeline logs).
            output: The agent's primary result payload (arbitrary key/value pairs).

        Returns:
            A dict with keys:
              - "agent_name": the agent's name
              - "improvements_made": the improvements list
              - "output": the result payload
        """
        return {
            "agent_name": self.name,
            "improvements_made": improvements,
            "output": output,
        }
