"""Configuration data models."""

from dataclasses import dataclass, field
from typing import List, Literal, Optional


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
    default_session_id: Optional[str] = field(
        default=None,
        metadata={
            "description": "Default sandbox session ID (falls back to task_id if not provided)"
        },
    )

    def __post_init__(self):
        """Validate configuration."""
        if not self.local_test and not self.base_url:
            raise ValueError("base_url is required when local_test is False")


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime behavior configuration."""

    default_budget: Budget = field(
        default_factory=Budget, metadata={"description": "Default budget for task execution"}
    )
    stuck_signature_repeats: int = field(
        default=3,
        metadata={
            "description": "Number of repeated error signatures before considering agent stuck"
        },
    )
    breakpoint: bool = field(
        default=False, metadata={"description": "Pause after each LLM response for debugging"}
    )
    default_agent_session_id: Optional[str] = field(
        default=None,
        metadata={"description": "Default agent session ID for resuming/continuing runs"},
    )


@dataclass(frozen=True)
class DebugConfig:
    """Debugging and diagnostics configuration."""

    show_memory_diagnostics: bool = field(
        default=False, metadata={"description": "Print memory statistics panel after each step"}
    )
    save_llm_io: bool = field(
        default=False,
        metadata={"description": "Save LLM input/output to files in debug/ directory"},
    )
    save_memory_dump: bool = field(
        default=False, metadata={"description": "Save memory state to JSON files after each step"}
    )


@dataclass(frozen=True)
class OutputConfig:
    """Output style configuration for console output."""

    style: Literal["minimal", "verbose"] = field(
        default="minimal",
        metadata={
            "description": "Console output style: minimal (key info only) or verbose (detailed step-by-step)"
        },
    )


@dataclass(frozen=True)
class TaskSpec:
    """Task specification."""

    task_id: str = field(metadata={"description": "Task ID"})
    goal: str = field(metadata={"description": "Task goal"})
    workspace_root: str = field(metadata={"description": "Workspace root directory"})
    budget: Budget = field(default_factory=Budget, metadata={"description": "Task budget"})

    def __post_init__(self):
        """Validate task specification."""
        if not self.goal:
            raise ValueError("goal is required")
        if not self.workspace_root:
            raise ValueError("workspace_root is required")


@dataclass(frozen=True)
class MemoryConfig:
    """Memory configuration for managing agent memory.

    This configuration controls memory compression, retention policies, and
    summary size limits. Memory summary limits are included here because
    they are closely related to memory compression and management.
    """

    # Memory Summary size limits
    summary_max_length: int = field(
        default=96000,  # 96KB (approximately 24k tokens, 18.75% of 128k)
        metadata={"description": "Maximum memory summary length in characters"},
    )
    summary_min_effective_length: int = field(
        default=24000,  # 24KB
        metadata={"description": "Minimum effective memory summary length"},
    )

    # Memory summary default and output limits
    summary_default_limit: int = field(
        default=64000,  # 64KB
        metadata={
            "description": "Default maximum memory summary length",
            "unit": "characters",
            "rationale": "Utilizes ~12.5% of 128k token input context for long-term memory",
        },
    )

    summary_stdout_stderr_shell: int = field(
        default=12000,  # 12KB
        metadata={
            "description": "Shell command output limit in memory summary",
            "unit": "characters",
            "rationale": "Memory summary needs more context than regular output to track history",
        },
    )

    summary_stdout_stderr_other: int = field(
        default=4000,  # 4KB
        metadata={
            "description": "Other tool output limit in memory summary",
            "unit": "characters",
            "rationale": "Non-shell tools typically have shorter output",
        },
    )

    summary_stderr_tail: int = field(
        default=5000,  # 5KB
        metadata={
            "description": "stderr tail limit in memory summary",
            "unit": "characters",
            "rationale": "Last error is important, needs sufficient space for tracebacks",
        },
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
class OutputLimitsConfig:
    """Output size limits for tool execution results.

    These limits control how much output from tool executions (stdout/stderr)
    is retained and passed to the LLM. Different limits apply based on the
    semantic type of the output (file content, execution result, etc.).

    Design rationale:
    - File view commands need larger limits to show complete file content
    - Normal commands need moderate limits to balance information vs token usage
    - Other tools (non-shell) typically have short output, need smaller limits
    """

    # Standard output limits (characters)
    normal: int = field(
        default=8000,  # 8KB
        metadata={
            "description": "Output limit for normal commands (non-file-view)",
            "unit": "characters",
            "rationale": "Balances information retention with token usage for typical command output",
        },
    )

    file_view: int = field(
        default=60000,  # 60KB
        metadata={
            "description": "Output limit for file view commands (cat, head, tail, sed -n)",
            "unit": "characters",
            "rationale": "File content needs larger limits to ensure LLM can see complete files for error fixing",
        },
    )

    other: int = field(
        default=2000,  # 2KB
        metadata={
            "description": "Output limit for non-shell tools (write_file, edit_file, etc.)",
            "unit": "characters",
            "rationale": "Non-shell tools typically have short success/failure messages",
        },
    )

    # Error summary limits (characters)
    error_summary_normal: int = field(
        default=25000,  # 25KB
        metadata={
            "description": "Error summary limit for normal commands",
            "unit": "characters",
            "rationale": "Ensures complete error information including long tracebacks",
        },
    )

    error_summary_file_view: int = field(
        default=50000,  # 50KB
        metadata={
            "description": "Error summary limit for file view commands",
            "unit": "characters",
            "rationale": "File view errors may include file content, need larger limit",
        },
    )

    # stderr tail limit (characters)
    stderr_tail: int = field(
        default=10000,  # 10KB
        metadata={
            "description": "stderr tail storage limit for detailed error analysis",
            "unit": "characters",
            "rationale": "Error information is typically at the end of stderr output",
        },
    )


@dataclass(frozen=True)
class ContextPackLimitsConfig:
    """Size limits for context pack construction.

    Context packs are assembled from various sources (recent errors, diffs,
    test results) and passed to the LLM in prompts. These limits control
    how much of each component is included.
    """

    # Maximum total size (bytes)
    max_size: int = field(
        default=200 * 1024,  # 200KB
        metadata={
            "description": "Maximum total size of context pack",
            "unit": "bytes",
            "rationale": "Balances context richness with token usage for 128k token context window",
        },
    )

    # Recent error limits (characters)
    recent_error_normal: int = field(
        default=20000,  # 20KB
        metadata={
            "description": "Recent error limit for normal errors",
            "unit": "characters",
            "rationale": "Provides sufficient error context without overwhelming the prompt",
        },
    )

    recent_error_file_content: int = field(
        default=40000,  # 40KB
        metadata={
            "description": "Recent error limit when error includes file content",
            "unit": "characters",
            "rationale": "Errors with file content need more space to show relevant context",
        },
    )

    # Diff limit (characters)
    diff: int = field(
        default=10000,  # 10KB
        metadata={
            "description": "Diff information limit",
            "unit": "characters",
            "rationale": "Shows sufficient file changes without excessive token usage",
        },
    )

    # Test results limits (characters)
    test_results: int = field(
        default=15000,  # 15KB
        metadata={
            "description": "Test results limit in agent loop",
            "unit": "characters",
            "rationale": "Test output can be long, need sufficient space for complete results",
        },
    )

    test_results_context: int = field(
        default=10000,  # 10KB
        metadata={
            "description": "Test results limit in context pack",
            "unit": "characters",
            "rationale": "Context pack has multiple components, test results need smaller limit",
        },
    )


@dataclass(frozen=True)
class VerifierLimitsConfig:
    """Size limits for verifier error extraction.

    The verifier runs test/build commands and extracts error information
    from their output. These limits control how much error information
    is extracted and formatted.
    """

    # Error summary limit (characters)
    error_summary: int = field(
        default=15000,  # 15KB
        metadata={
            "description": "Error summary limit for verifier output",
            "unit": "characters",
            "rationale": "Must be large enough to include complete ImportError tracebacks",
        },
    )

    # Error line extraction
    error_lines_max: int = field(
        default=30,
        metadata={
            "description": "Maximum number of error-related lines to extract",
            "unit": "lines",
            "rationale": "Captures relevant error context without excessive output",
        },
    )

    # Error signature line limit (characters)
    error_signature_line: int = field(
        default=200,
        metadata={
            "description": "Single line limit for error signature extraction",
            "unit": "characters",
            "rationale": "Error signatures are typically single lines, 200 chars is sufficient",
        },
    )


@dataclass(frozen=True)
class EventLoggerLimitsConfig:
    """Size limits for event logging.

    Event logs record execution history for debugging and analysis.
    These limits control how much output is stored in logs to balance
    information retention with log file size.
    """

    # Output limit (characters)
    output_normal: int = field(
        default=12000,  # 12KB
        metadata={
            "description": "Normal tool output limit in event logs",
            "unit": "characters",
            "rationale": "Logs need key information for debugging, not full output",
        },
    )

    # Prompt preview limit (characters)
    prompt_preview: int = field(
        default=4000,  # 4KB
        metadata={
            "description": "Prompt preview limit in event logs",
            "unit": "characters",
            "rationale": "Only store prompt beginning for debugging, not full prompt",
        },
    )


@dataclass(frozen=True)
class LoggingLimitsConfig:
    """Size limits for log file management.

    Controls log file rotation and size management.
    """

    # Log file max size (MB)
    file_max_size_mb: int = field(
        default=100,  # 100MB
        metadata={
            "description": "Maximum log file size before rotation",
            "unit": "MB",
            "rationale": "Balances log retention with disk space usage",
        },
    )


@dataclass(frozen=True)
class LimitsConfig:
    """Runtime limits configuration.

    This configuration controls all size and length limits used throughout
    the system. These are runtime limits (not user-configurable application
    settings) but can be adjusted via configuration files for tuning.

    All limits are in characters unless otherwise specified (bytes, lines, MB).
    """

    output: OutputLimitsConfig = field(
        default_factory=OutputLimitsConfig, metadata={"description": "Tool execution output limits"}
    )

    context_pack: ContextPackLimitsConfig = field(
        default_factory=ContextPackLimitsConfig,
        metadata={"description": "Context pack size limits"},
    )

    verifier: VerifierLimitsConfig = field(
        default_factory=VerifierLimitsConfig,
        metadata={"description": "Verifier error extraction limits"},
    )

    event_logger: EventLoggerLimitsConfig = field(
        default_factory=EventLoggerLimitsConfig,
        metadata={"description": "Event logger output limits"},
    )

    logging: LoggingLimitsConfig = field(
        default_factory=LoggingLimitsConfig, metadata={"description": "Log file size limits"}
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

    # Memory configuration
    memory: MemoryConfig = field(
        default_factory=MemoryConfig, metadata={"description": "Memory configuration"}
    )

    # Runtime limits configuration
    limits: LimitsConfig = field(
        default_factory=LimitsConfig, metadata={"description": "Runtime limits configuration"}
    )

    # Runtime configuration
    runtime: RuntimeConfig = field(
        default_factory=RuntimeConfig, metadata={"description": "Runtime behavior configuration"}
    )

    # Debug configuration
    debug: DebugConfig = field(
        default_factory=DebugConfig,
        metadata={"description": "Debugging and diagnostics configuration"},
    )

    # Output configuration
    output: OutputConfig = field(
        default_factory=OutputConfig, metadata={"description": "Output style configuration"}
    )

    def __post_init__(self):
        """Validate configuration."""
        if not self.ai.completion.api_base or not self.ai.completion.api_key:
            raise ValueError("AI completion service (api_base and api_key) is required")
