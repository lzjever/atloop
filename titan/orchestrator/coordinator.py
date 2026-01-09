"""Workflow coordinator - manages all components."""

import logging
from pathlib import Path
from typing import Optional

from titan.config.models import TaskSpec, TitanConfig
from titan.llm import LLMClient
from titan.logging import EventLogger
from titan.orchestrator.budget import BudgetManager
from titan.orchestrator.job_state import JobState
from titan.retrieval import (
    ContextPackBuilder,
    ProjectProfileDetector,
    WorkspaceIndexer,
)
from titan.runtime import SandboxAdapter, ToolRuntime
from titan.orchestrator.state.manager import StateManager
from titan.orchestrator.state_machine import Phase, StateMachine
from titan.orchestrator.verifier import Verifier

logger = logging.getLogger(__name__)


class WorkflowCoordinator:
    """Workflow coordinator - single entry point for all components."""

    def __init__(self, task_spec: TaskSpec, config: TitanConfig):
        """Initialize coordinator."""
        logger.debug(f"[Coordinator] Initializing for task: {task_spec.task_id}")
        
        self.task_spec = task_spec
        self.config = config

        # Infrastructure
        logger.debug(f"[Coordinator] Creating sandbox adapter")
        self.sandbox = SandboxAdapter(config.sandbox, task_spec.task_id)
        
        logger.debug(f"[Coordinator] Creating LLM client")
        self.llm_client = LLMClient(config, workspace_root=task_spec.workspace_root)
        
        logger.debug(f"[Coordinator] Creating tool runtime")
        self.tool_runtime = ToolRuntime(
            self.sandbox, skill_loader=self.llm_client.skill_loader
        )

        # Retrieval
        logger.debug(f"[Coordinator] Creating retrieval components")
        self.indexer = WorkspaceIndexer(self.tool_runtime)
        self.profile_detector = ProjectProfileDetector(self.tool_runtime)
        self.context_builder: Optional[ContextPackBuilder] = None
        self.verifier: Optional[Verifier] = None

        # State
        logger.debug(f"[Coordinator] Creating state manager")
        job_state = JobState(flow_id=f"titan-{task_spec.task_id}")
        state_file = Path(config.runs_dir) / task_spec.task_id / "agent_state.json"
        self.state_manager = StateManager(state_file, job_state)
        self.state_manager.load()

        # State machine
        logger.debug(f"[Coordinator] Creating state machine")
        self.state_machine = StateMachine()
        if self.state_manager.agent_state.step == 0:
            logger.debug(f"[Coordinator] Initial step is 0, setting phase to DISCOVER")
            self.state_manager.update(phase="DISCOVER")
            self.state_machine.current_phase = Phase.DISCOVER

        # Budget
        logger.debug(f"[Coordinator] Creating budget manager")
        self.budget_manager = BudgetManager(task_spec.budget)

        # Logging
        logger.debug(f"[Coordinator] Creating event logger")
        self.event_logger = EventLogger(
            task_id=task_spec.task_id,
            runs_dir=config.runs_dir,
        )
        
        logger.info(f"[Coordinator] Initialization complete for task: {task_spec.task_id}")

    def initialize(self) -> bool:
        """Initialize workspace - single method."""
        logger.debug(f"[Coordinator] Starting workspace initialization")
        try:
            logger.debug(f"[Coordinator] Bootstrapping indexer")
            self.indexer.bootstrap()
            
            logger.debug(f"[Coordinator] Detecting project profile")
            profile = self.profile_detector.detect()
            logger.debug(f"[Coordinator] Detected profile: {profile}")
            
            logger.debug(f"[Coordinator] Creating context builder and verifier")
            self.context_builder = ContextPackBuilder(self.indexer, profile)
            self.verifier = Verifier(self.tool_runtime, profile)
            
            logger.debug(f"[Coordinator] Resetting LLM history")
            self.llm_client.reset_history()
            
            logger.info(f"[Coordinator] Workspace initialization complete")
            return True
        except Exception as e:
            logger.error(f"[Coordinator] Initialize failed: {e}")
            logger.debug(f"[Coordinator] Exception details: {type(e).__name__}: {e}", exc_info=True)
            return False

    @property
    def job_state(self) -> JobState:
        """Get job state."""
        return self.state_manager._job_state
