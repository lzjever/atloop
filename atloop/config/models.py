"""Configuration data models."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class TokenizerConfig:
    """Tokenizer configuration for lexilux."""

    name: str = field(
        default="Qwen/Qwen2.5-7B-Instruct", metadata={"description": "Tokenizer model name"}
    )
    cache_dir: Optional[str] = field(
        default=None, metadata={"description": "Tokenizer cache directory (optional)"}
    )


@dataclass(frozen=True)
class AIPerformanceConfig:
    """AI performance parameters (auto-calculated from token limits)."""

    # User-specified limits
    max_tokens_input: int = field(
        default=32 * 1024,  # 32k
        metadata={"description": "Maximum input tokens (default: 32k)"},
    )
    max_tokens_output: int = field(
        default=4 * 1024,  # 4k
        metadata={"description": "Maximum output tokens (default: 4k)"},
    )

    # Auto-calculated (computed in __post_init__)
    # Using default=0 as placeholder - will be overwritten in __post_init__
    max_tokens_total: int = field(init=False, default=0)  # max_tokens_input + max_tokens_output
    memory_retention_tokens: int = field(init=False, default=0)  # Calculated from input
    history_compression_threshold: int = field(init=False, default=0)  # When to compress
    context_window_reserve: int = field(init=False, default=0)  # Reserve for system/user prompts
    max_history_tokens: int = field(init=False, default=0)  # Maximum history tokens to keep
    summary_tokens: int = field(init=False, default=0)  # Tokens for memory summary

    def __post_init__(self):
        """Auto-calculate derived parameters."""
        # Total context window
        object.__setattr__(self, "max_tokens_total", self.max_tokens_input + self.max_tokens_output)

        # Memory retention: keep ~20% of input for memory/summary
        object.__setattr__(self, "memory_retention_tokens", int(self.max_tokens_input * 0.20))

        # History compression: compress when history exceeds 70% of input
        object.__setattr__(self, "history_compression_threshold", int(self.max_tokens_input * 0.70))

        # Reserve: 10% for system prompt and overhead
        object.__setattr__(self, "context_window_reserve", int(self.max_tokens_input * 0.10))

        # Max history: keep up to 60% of input for history
        object.__setattr__(self, "max_history_tokens", int(self.max_tokens_input * 0.60))

        # Summary: use 15% of input for memory summary
        object.__setattr__(self, "summary_tokens", int(self.max_tokens_input * 0.15))


@dataclass(frozen=True)
class AIServiceConfig:
    """AI service endpoint configuration."""

    # Required fields (no defaults) - must come first
    model: str = field(metadata={"description": "Model name"})
    api_base: str = field(metadata={"description": "API base URL"})
    api_key: str = field(metadata={"description": "API key"})

    # Optional fields (with defaults) - must come after required fields
    source_model: Optional[str] = field(
        default=None, metadata={"description": "Source model name (for compatibility)"}
    )
    mode: Optional[str] = field(
        default=None, metadata={"description": "Service mode (for reranker: 'openai' or 'chat')"}
    )

    def __post_init__(self):
        """Set source_model to model if not provided."""
        if self.source_model is None:
            object.__setattr__(self, "source_model", self.model)


@dataclass(frozen=True)
class AIConfig:
    """Complete AI configuration."""

    # Required fields (no defaults) - must come first
    completion: AIServiceConfig = field(metadata={"description": "Completion service"})

    # Optional fields (with defaults) - must come after required fields
    embedding: Optional[AIServiceConfig] = field(
        default=None, metadata={"description": "Embedding service (optional)"}
    )
    reranker: Optional[AIServiceConfig] = field(
        default=None, metadata={"description": "Reranker service (optional)"}
    )
    performance: AIPerformanceConfig = field(
        default_factory=AIPerformanceConfig, metadata={"description": "AI performance parameters"}
    )
    tokenizer: TokenizerConfig = field(
        default_factory=TokenizerConfig, metadata={"description": "Tokenizer configuration"}
    )


@dataclass(frozen=True)
class Budget:
    """Budget constraints for task execution."""

    max_llm_calls: int = field(default=80, metadata={"description": "Maximum LLM calls"})
    max_tool_calls: int = field(default=300, metadata={"description": "Maximum tool calls"})
    max_wall_time_sec: int = field(
        default=1800, metadata={"description": "Maximum wall time in seconds"}
    )

    def to_dict(self) -> dict:
        """Convert Budget to dictionary."""
        return {
            "max_llm_calls": self.max_llm_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_wall_time_sec": self.max_wall_time_sec,
        }


@dataclass(frozen=True)
class SandboxConfig:
    """Sandbox execution configuration."""

    base_url: Optional[str] = field(default=None, metadata={"description": "Sandbox base URL"})
    local_test: bool = field(default=False, metadata={"description": "Use local test mode"})
    timeout: int = field(default=30, metadata={"description": "Request timeout in seconds"})
    session_ttl_seconds: int = field(
        default=900, metadata={"description": "Session TTL in seconds"}
    )
    image: Optional[str] = field(default=None, metadata={"description": "Container image"})
    cpu_limit: Optional[str] = field(default=None, metadata={"description": "CPU limit"})
    memory_limit: Optional[str] = field(default=None, metadata={"description": "Memory limit"})
    ephemeral_storage_limit: Optional[str] = field(
        default=None, metadata={"description": "Ephemeral storage limit"}
    )

    def __post_init__(self):
        """Validate configuration."""
        if not self.local_test and not self.base_url:
            raise ValueError("base_url is required when local_test is False")


@dataclass(frozen=True)
class TaskSpec:
    """Task specification."""

    task_id: str = field(metadata={"description": "Task ID"})
    goal: str = field(metadata={"description": "Task goal"})
    workspace_root: str = field(metadata={"description": "Workspace root directory"})
    constraints: List[str] = field(
        default_factory=list, metadata={"description": "Task constraints"}
    )
    budget: Budget = field(default_factory=Budget, metadata={"description": "Task budget"})
    task_type: str = field(
        default="bugfix", metadata={"description": "Task type: bugfix, feature, or refactor"}
    )

    def __post_init__(self):
        """Validate task specification."""
        if not self.goal:
            raise ValueError("goal is required")
        if not self.workspace_root:
            raise ValueError("workspace_root is required")
        if self.task_type not in ["bugfix", "feature", "refactor"]:
            raise ValueError("task_type must be one of: bugfix, feature, refactor")


@dataclass(frozen=True)
class MemoryConfig:
    """Memory configuration for managing agent memory."""

    # Memory Summary size limits
    summary_max_length: int = field(
        default=96000,  # 96KB (approximately 24k tokens, 18.75% of 128k)
        metadata={"description": "Maximum memory summary length in characters"},
    )
    summary_min_effective_length: int = field(
        default=24000,  # 24KB
        metadata={"description": "Minimum effective memory summary length"},
    )

    # Compression thresholds
    compression_threshold: int = field(
        default=80000,  # 80KB - trigger compression when exceeded
        metadata={"description": "Memory size threshold to trigger compression"},
    )
    compression_target: int = field(
        default=60000,  # 60KB - target size after compression
        metadata={"description": "Target memory size after compression"},
    )

    # Retention policies (rule-based)
    attempts_keep_recent: int = field(
        default=15, metadata={"description": "Number of recent attempts to keep"}
    )
    decisions_keep_recent: int = field(
        default=10, metadata={"description": "Number of recent decisions to keep"}
    )
    important_decisions_keep: int = field(
        default=30, metadata={"description": "Number of important decisions to keep"}
    )
    milestones_keep: int = field(
        default=30, metadata={"description": "Number of milestones to keep"}
    )
    learnings_keep: int = field(default=20, metadata={"description": "Number of learnings to keep"})

    # LLM compression configuration
    llm_compression_enabled: bool = field(
        default=True, metadata={"description": "Enable LLM-based memory compression"}
    )
    llm_compression_threshold: int = field(
        default=100000,  # 100KB - use LLM compression when exceeded
        metadata={"description": "Memory size threshold to trigger LLM compression"},
    )
    llm_compression_target: int = field(
        default=70000,  # 70KB - target size after LLM compression
        metadata={"description": "Target memory size after LLM compression"},
    )

    # Deduplication configuration
    deduplication_enabled: bool = field(
        default=True, metadata={"description": "Enable memory deduplication"}
    )
    deduplication_similarity_threshold: float = field(
        default=0.85,  # Similarity threshold (0-1)
        metadata={"description": "Similarity threshold for deduplication (0-1)"},
    )


@dataclass(frozen=True)
class AtloopConfig:
    """Main atloop configuration."""

    # AI configuration
    ai: AIConfig = field(metadata={"description": "AI configuration"})

    # Sandbox configuration
    sandbox: SandboxConfig = field(
        default_factory=SandboxConfig, metadata={"description": "Sandbox configuration"}
    )

    # Default budget
    default_budget: Budget = field(
        default_factory=Budget, metadata={"description": "Default budget"}
    )

    # Memory configuration
    memory: MemoryConfig = field(
        default_factory=MemoryConfig, metadata={"description": "Memory configuration"}
    )

    # Workspace settings
    runs_dir: str = field(default="runs", metadata={"description": "Runs directory"})

    # Skills and MCP configuration
    skills_dirs: List[str] = field(
        default_factory=list, metadata={"description": "Additional skills directories"}
    )
    mcp_config_path: Optional[str] = field(
        default=None, metadata={"description": "Path to MCP configuration file"}
    )

    # Stuck detection
    stuck_signature_repeats: int = field(
        default=3, metadata={"description": "Stuck signature repeats threshold"}
    )

    def __post_init__(self):
        """Validate configuration."""
        if not self.ai.completion.api_base or not self.ai.completion.api_key:
            raise ValueError("AI completion service (api_base and api_key) is required")
