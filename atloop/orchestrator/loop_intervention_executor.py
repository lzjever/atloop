"""
Loop Intervention Executor - Centralized execution of loop interventions.

This module provides a clean, single-responsibility component for executing
loop interventions. It separates the "what to do" (LoopDetector) from the
"how to do it" (LoopInterventionExecutor).

Design Philosophy:
- Single Responsibility: Only handles intervention execution
- Strategy Pattern: Different strategies for different intervention levels
- Clean Interface: Returns a clear InterventionResult that callers can act on
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from atloop.config.loop_detection import InterventionLevel
from atloop.orchestrator.loop_detector import Intervention, LoopAnalysis, LoopType

logger = logging.getLogger(__name__)


class InterventionAction(Enum):
    """Action to take based on intervention."""
    CONTINUE_NORMAL = "continue_normal"     # No intervention needed, continue normally
    INJECT_WARNING = "inject_warning"       # Inject warning into prompt, call LLM
    FORCE_RECOVERY = "force_recovery"       # Skip LLM, use forced recovery actions
    ABORT_TASK = "abort_task"               # Abort the task entirely


@dataclass
class InterventionResult:
    """Result of intervention execution decision."""
    action: InterventionAction
    prompt_injection: str                   # Text to inject into prompt (if INJECT_WARNING)
    forced_actions: List[Dict[str, Any]]    # Actions to force (if FORCE_RECOVERY)
    error_message: str                      # Error message (if ABORT_TASK)
    analysis: Optional[LoopAnalysis]        # Original analysis for reference
    
    @property
    def should_skip_llm(self) -> bool:
        """Whether to skip the LLM call entirely."""
        return self.action in [InterventionAction.FORCE_RECOVERY, InterventionAction.ABORT_TASK]
    
    @property
    def should_abort(self) -> bool:
        """Whether to abort the task."""
        return self.action == InterventionAction.ABORT_TASK


class LoopInterventionExecutor:
    """
    Executes loop intervention decisions.
    
    This class is responsible for:
    1. Taking a LoopAnalysis and Intervention from LoopDetector
    2. Deciding the appropriate action based on intervention level
    3. Generating recovery actions when needed
    4. Returning a clear result that PlanPhase can act on
    
    Usage:
        executor = LoopInterventionExecutor(config)
        result = executor.execute(analysis, intervention)
        
        if result.should_abort:
            return failure_result(result.error_message)
        elif result.should_skip_llm:
            actions = result.forced_actions
        else:
            # Call LLM with result.prompt_injection
    """
    
    # Threshold for forcing task abort (repetitions at ABORT level)
    ABORT_REPETITION_THRESHOLD = 12
    
    # Threshold for forcing recovery (repetitions at FORCE level)  
    FORCE_REPETITION_THRESHOLD = 6
    
    def __init__(self, workspace_path: Optional[str] = None):
        """
        Initialize executor.
        
        Args:
            workspace_path: Path to workspace for generating recovery actions
        """
        self.workspace_path = workspace_path or "/workspace"
    
    def execute(
        self,
        analysis: LoopAnalysis,
        intervention: Intervention,
    ) -> InterventionResult:
        """
        Execute intervention decision based on analysis and intervention.
        
        Args:
            analysis: Loop analysis from LoopDetector
            intervention: Intervention from LoopDetector
            
        Returns:
            InterventionResult with action to take
        """
        # No loop detected - continue normally
        if not analysis.is_looping:
            return InterventionResult(
                action=InterventionAction.CONTINUE_NORMAL,
                prompt_injection="",
                forced_actions=[],
                error_message="",
                analysis=analysis,
            )
        
        level = intervention.level
        repetitions = analysis.repetition_count
        
        logger.info(
            f"[LoopInterventionExecutor] Processing intervention: "
            f"level={level.name}, repetitions={repetitions}, type={analysis.loop_type.value}"
        )
        
        # ABORT level with high repetitions - force task failure
        if level >= InterventionLevel.ABORT and repetitions >= self.ABORT_REPETITION_THRESHOLD:
            return self._create_abort_result(analysis, intervention)
        
        # FORCE_STRATEGY level with high repetitions - force recovery actions
        if level >= InterventionLevel.FORCE_STRATEGY and repetitions >= self.FORCE_REPETITION_THRESHOLD:
            return self._create_force_recovery_result(analysis, intervention)
        
        # Lower levels or low repetitions - inject warning and let LLM try
        return self._create_warning_result(analysis, intervention)
    
    def _create_abort_result(
        self,
        analysis: LoopAnalysis,
        intervention: Intervention,
    ) -> InterventionResult:
        """Create result for task abort."""
        error_msg = (
            f"Task aborted: Unbreakable loop detected after {analysis.repetition_count} repetitions. "
            f"Loop type: {analysis.loop_type.value}. "
            f"The system repeatedly performed {analysis.loop_type.value} without making progress. "
            f"Evidence: {'; '.join(analysis.evidence[:2])}"
        )
        
        logger.error(f"[LoopInterventionExecutor] ABORTING task: {error_msg}")
        
        return InterventionResult(
            action=InterventionAction.ABORT_TASK,
            prompt_injection="",
            forced_actions=[],
            error_message=error_msg,
            analysis=analysis,
        )
    
    def _create_force_recovery_result(
        self,
        analysis: LoopAnalysis,
        intervention: Intervention,
    ) -> InterventionResult:
        """Create result for forced recovery."""
        # Generate intelligent recovery actions based on loop type
        forced_actions = self._generate_recovery_actions(analysis)
        
        logger.warning(
            f"[LoopInterventionExecutor] FORCING recovery: "
            f"{len(forced_actions)} actions for {analysis.loop_type.value} loop"
        )
        
        return InterventionResult(
            action=InterventionAction.FORCE_RECOVERY,
            prompt_injection=intervention.prompt_injection,
            forced_actions=forced_actions,
            error_message="",
            analysis=analysis,
        )
    
    def _create_warning_result(
        self,
        analysis: LoopAnalysis,
        intervention: Intervention,
    ) -> InterventionResult:
        """Create result for warning injection."""
        logger.info(
            f"[LoopInterventionExecutor] Injecting {intervention.level.name} warning"
        )
        
        return InterventionResult(
            action=InterventionAction.INJECT_WARNING,
            prompt_injection=intervention.prompt_injection,
            forced_actions=[],
            error_message="",
            analysis=analysis,
        )
    
    def _generate_recovery_actions(self, analysis: LoopAnalysis) -> List[Dict[str, Any]]:
        """
        Generate intelligent recovery actions based on loop type.
        
        This is the key method that makes FORCE_STRATEGY actually useful.
        Instead of generic actions, we generate actions specific to the loop type.
        """
        loop_type = analysis.loop_type
        actions = []
        
        if loop_type == LoopType.VIEW_WITHOUT_MODIFY:
            # The LLM is viewing files but not modifying them
            # Force it to acknowledge the situation and make a decision
            actions.append({
                "tool": "run",
                "args": {
                    "cmd": f"echo '=== FORCED RECOVERY ===' && "
                           f"echo 'Loop type: VIEW_WITHOUT_MODIFY' && "
                           f"echo 'You viewed files {analysis.repetition_count} times without modifying.' && "
                           f"echo 'The system is now forcing you to make a decision.' && "
                           f"ls -la {self.workspace_path}/*.docx {self.workspace_path}/*.doc 2>/dev/null || "
                           f"echo 'No .docx files found - you need to CREATE the document.'"
                },
                "reason": "Force acknowledgment and check document status",
            })
            
        elif loop_type == LoopType.SAME_ACTION_REPEAT:
            # The LLM is repeating the exact same action
            # Show what was repeated and force different approach
            actions.append({
                "tool": "run",
                "args": {
                    "cmd": f"echo '=== FORCED RECOVERY ===' && "
                           f"echo 'Loop type: SAME_ACTION_REPEAT' && "
                           f"echo 'You repeated the same action {analysis.repetition_count} times.' && "
                           f"echo 'This action is not working. Try something DIFFERENT.' && "
                           f"echo 'Current workspace status:' && "
                           f"ls -la {self.workspace_path}/"
                },
                "reason": "Force acknowledgment of repeated action",
            })
            
        elif loop_type == LoopType.NO_PROGRESS:
            # The LLM is taking actions but not making progress
            actions.append({
                "tool": "run", 
                "args": {
                    "cmd": f"echo '=== FORCED RECOVERY ===' && "
                           f"echo 'Loop type: NO_PROGRESS' && "
                           f"echo 'Actions taken but no measurable progress.' && "
                           f"echo 'Files created:' && "
                           f"find {self.workspace_path} -type f -newer /tmp/.start_marker 2>/dev/null || "
                           f"echo 'No new files created'"
                },
                "reason": "Check what progress was made",
            })
            
        else:
            # Generic recovery
            actions.append({
                "tool": "run",
                "args": {
                    "cmd": f"echo '=== FORCED RECOVERY ===' && "
                           f"echo 'Loop detected: {loop_type.value}' && "
                           f"echo 'Repetitions: {analysis.repetition_count}' && "
                           f"ls -la {self.workspace_path}/"
                },
                "reason": "Generic recovery - check workspace status",
            })
        
        return actions


def create_intervention_executor(workspace_path: Optional[str] = None) -> LoopInterventionExecutor:
    """Factory function to create an intervention executor."""
    return LoopInterventionExecutor(workspace_path=workspace_path)
