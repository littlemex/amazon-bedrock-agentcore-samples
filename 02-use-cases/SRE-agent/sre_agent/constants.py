#!/usr/bin/env python3

import logging
from typing import Optional
from pydantic import BaseModel, Field

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    """Model configuration constants."""

    # Anthropic model IDs
    anthropic_model_id: str = Field(
        default="claude-sonnet-4-20250514",
        description="Default Anthropic Claude model ID",
    )

    # Amazon Bedrock model IDs
    bedrock_model_id: str = Field(
        default="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
        description="Default Amazon Bedrock Claude model ID",
    )

    # Model parameters
    default_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Default temperature for LLM generation",
    )

    default_max_tokens: int = Field(
        default=4096,
        ge=1,
        le=100000,
        description="Default max tokens for agent responses",
    )

    output_formatter_max_tokens: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Max tokens for output formatter LLM calls",
    )


class AWSConfig(BaseModel):
    """AWS configuration constants."""

    default_region: str = Field(default="us-east-1", description="Default AWS region")

    bedrock_endpoint_url: str = Field(
        default="https://bedrock-agentcore-control.us-east-1.amazonaws.com",
        description="Amazon Bedrock AgentCore control endpoint URL",
    )

    credential_provider_endpoint_url: str = Field(
        default="https://us-east-1.prod.agent-credential-provider.cognito.aws.dev",
        description="AWS credential provider endpoint URL",
    )


class TimeoutConfig(BaseModel):
    """Timeout configuration constants."""

    graph_execution_timeout_seconds: int = Field(
        default=600,
        ge=1,
        le=3600,
        description="Maximum time to wait for graph execution (10 minutes)",
    )

    mcp_tools_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Maximum time to wait for MCP tools loading",
    )


class PromptConfig(BaseModel):
    """Prompt configuration constants."""

    prompts_directory: str = Field(
        default="config/prompts",
        description="Directory containing prompt template files",
    )

    agent_prompt_files: dict[str, str] = Field(
        default={
            "kubernetes": "kubernetes_agent_prompt.txt",
            "logs": "logs_agent_prompt.txt",
            "metrics": "metrics_agent_prompt.txt",
            "runbooks": "runbooks_agent_prompt.txt",
        },
        description="Mapping of agent types to their prompt files",
    )

    supervisor_prompt_files: dict[str, str] = Field(
        default={
            "plan_aggregation": "supervisor_plan_aggregation.txt",
            "standard_aggregation": "supervisor_standard_aggregation.txt",
            "system": "supervisor_aggregation_system.txt",
        },
        description="Supervisor aggregation prompt files",
    )

    output_formatter_prompt_files: dict[str, str] = Field(
        default={
            "executive_summary_system": "executive_summary_system.txt",
            "executive_summary_user_template": "executive_summary_user_template.txt",
        },
        description="Output formatter prompt files",
    )

    base_prompt_file: str = Field(
        default="agent_base_prompt.txt",
        description="Base prompt template used by all agents",
    )

    enable_prompt_caching: bool = Field(
        default=True, description="Whether to enable LRU caching for prompt loading"
    )

    max_cache_size: int = Field(
        default=32,
        ge=1,
        le=128,
        description="Maximum number of prompts to cache in memory",
    )


class ApplicationConfig(BaseModel):
    """Application configuration constants."""

    agent_model_name: str = Field(
        default="sre-multi-agent", description="Model name returned in API responses"
    )

    default_output_dir: str = Field(
        default="./reports",
        description="Default directory for saving investigation reports",
    )

    conversation_state_file: str = Field(
        default=".multi_agent_conversation_state.json",
        description="Filename for saving conversation state",
    )

    spinner_chars: list[str] = Field(
        default=["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
        description="Characters used for spinner animation",
    )


class SREConstants:
    """Central constants configuration for the SRE Agent system.

    This class provides a centralized way to access all configuration constants
    used throughout the SRE Agent application. It uses Pydantic models for
    validation and type safety.

    Usage:
        from .constants import SREConstants

        # Access model configuration
        model_id = SREConstants.model.anthropic_model_id
        temperature = SREConstants.model.default_temperature

        # Access AWS configuration
        region = SREConstants.aws.default_region

        # Access timeout configuration
        timeout = SREConstants.timeouts.graph_execution_timeout_seconds

        # Access prompt configuration
        prompts_dir = SREConstants.prompts.prompts_directory
        agent_files = SREConstants.prompts.agent_prompt_files

        # Access application configuration
        output_dir = SREConstants.app.default_output_dir
    """

    model: ModelConfig = ModelConfig()
    aws: AWSConfig = AWSConfig()
    timeouts: TimeoutConfig = TimeoutConfig()
    prompts: PromptConfig = PromptConfig()
    app: ApplicationConfig = ApplicationConfig()

    @classmethod
    def get_model_config(cls, provider: str, **kwargs) -> dict:
        """Get model configuration for a specific provider.

        Args:
            provider: LLM provider ("anthropic" or "bedrock")
            **kwargs: Additional configuration overrides

        Returns:
            Dictionary with model configuration
        """
        if provider == "anthropic":
            return {
                "model_id": kwargs.get("model_id", cls.model.anthropic_model_id),
                "max_tokens": kwargs.get("max_tokens", cls.model.default_max_tokens),
                "temperature": kwargs.get("temperature", cls.model.default_temperature),
            }
        elif provider == "bedrock":
            return {
                "model_id": kwargs.get("model_id", cls.model.bedrock_model_id),
                "region_name": kwargs.get("region_name", cls.aws.default_region),
                "max_tokens": kwargs.get("max_tokens", cls.model.default_max_tokens),
                "temperature": kwargs.get("temperature", cls.model.default_temperature),
            }
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @classmethod
    def get_output_formatter_config(cls, provider: str, **kwargs) -> dict:
        """Get model configuration for output formatter.

        Args:
            provider: LLM provider ("anthropic" or "bedrock")
            **kwargs: Additional configuration overrides

        Returns:
            Dictionary with output formatter model configuration
        """
        config = cls.get_model_config(provider, **kwargs)
        # Override max_tokens for output formatter
        config["max_tokens"] = kwargs.get(
            "max_tokens", cls.model.output_formatter_max_tokens
        )
        return config

    @classmethod
    def get_prompt_config(cls) -> PromptConfig:
        """Get prompt configuration.

        Returns:
            PromptConfig instance with all prompt settings
        """
        return cls.prompts


# Convenience instance for easy access
constants = SREConstants()

# Legacy support - individual constants for backward compatibility if needed
ANTHROPIC_MODEL_ID = constants.model.anthropic_model_id
BEDROCK_MODEL_ID = constants.model.bedrock_model_id
DEFAULT_TEMPERATURE = constants.model.default_temperature
DEFAULT_MAX_TOKENS = constants.model.default_max_tokens
DEFAULT_AWS_REGION = constants.aws.default_region
GRAPH_EXECUTION_TIMEOUT_SECONDS = constants.timeouts.graph_execution_timeout_seconds
AGENT_MODEL_NAME = constants.app.agent_model_name
DEFAULT_OUTPUT_DIR = constants.app.default_output_dir
