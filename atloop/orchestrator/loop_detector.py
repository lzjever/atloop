"""
Loop Detector for identifying and intervening in execution loops.

This module detects when the LLM is stuck in repetitive patterns and
triggers graduated interventions to break the loop.

Design Philosophy:
- Evidence-based detection using concrete metrics from ProgressTracker
- Graduated intervention: Warning → Hard Warning → Force → Abort
- Active intervention, not passive warnings
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from atloop.config.loop_detection import (
    DEFAULT_LOOP_DETECTION_CONFIG,
    InterventionLevel,
    LoopDetectionConfig,
)
from atloop.memory.progress_tracker import ActionCategory, ProgressMetrics, ProgressTracker

logger = logging.getLogger(__name__)


class LoopType(Enum):
    """Types of detected loops."""
    NONE = "none"                          # No loop detected
    VIEW_WITHOUT_MODIFY = "view_without_modify"  # Viewing files but not fixing
    SAME_ACTION_REPEAT = "same_action_repeat"    # Same action repeated
    NO_PROGRESS = "no_progress"                  # Actions taken but no measurable progress
    EXPLORATION_LOOP = "exploration_loop"        # Stuck in exploration (ls, find, etc.)


@dataclass
class LoopAnalysis:
    """Result of loop analysis."""
    is_looping: bool
    loop_type: LoopType
    intervention_level: InterventionLevel
    repetition_count: int
    evidence: List[str]  # Evidence for the loop detection
    suggested_action: Optional[str] = None
    metrics: Optional[ProgressMetrics] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_looping": self.is_looping,
            "loop_type": self.loop_type.value,
            "intervention_level": self.intervention_level.name,
            "repetition_count": self.repetition_count,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


@dataclass
class Intervention:
    """Intervention to be applied."""
    level: InterventionLevel
    message: str
    prompt_injection: str  # Text to inject into the prompt
    forced_actions: List[Dict[str, Any]] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)  # Action patterns to block
    require_different_action: bool = False  # Force LLM to do something different
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.name,
            "message": self.message,
            "prompt_injection": self.prompt_injection,
            "forced_actions": self.forced_actions,
            "blocked_patterns": self.blocked_patterns,
            "require_different_action": self.require_different_action,
        }


class LoopDetector:
    """
    Detects execution loops and generates interventions.
    
    This class analyzes progress metrics to detect various types of loops
    and generates appropriate interventions based on severity.
    """
    
    def __init__(self, config: Optional[LoopDetectionConfig] = None):
        """Initialize loop detector with configuration."""
        self.config = config or DEFAULT_LOOP_DETECTION_CONFIG
        self._last_analysis: Optional[LoopAnalysis] = None
    
    def analyze(self, tracker: ProgressTracker) -> LoopAnalysis:
        """
        Analyze progress tracker for loop patterns.
        
        Args:
            tracker: ProgressTracker with action history
            
        Returns:
            LoopAnalysis with detection results
        """
        metrics = tracker.get_metrics(window=self.config.pattern_window_size)
        evidence: List[str] = []
        loop_type = LoopType.NONE
        repetition_count = 0
        
        # Check for same action repeat
        if metrics.consecutive_same_pattern >= self.config.soft_warning_threshold:
            loop_type = LoopType.SAME_ACTION_REPEAT
            repetition_count = metrics.consecutive_same_pattern
            recent_actions = tracker.get_recent_actions_summary(3)
            evidence.append(
                f"Same action pattern repeated {metrics.consecutive_same_pattern} times: "
                f"{recent_actions}"
            )
        
        # Check for view without modify
        elif metrics.consecutive_view_count >= self.config.max_view_without_modify:
            loop_type = LoopType.VIEW_WITHOUT_MODIFY
            repetition_count = metrics.consecutive_view_count
            evidence.append(
                f"Viewed files {metrics.consecutive_view_count} times without any modification"
            )
            evidence.append(
                f"View/Modify ratio: {metrics.view_to_modify_ratio:.1f} "
                f"(view={metrics.view_actions}, modify={metrics.modify_actions})"
            )
        
        # Check for no progress (high repetition rate)
        elif metrics.repetition_rate > 0.7 and metrics.total_actions > 5:
            loop_type = LoopType.NO_PROGRESS
            repetition_count = metrics.repeated_actions
            evidence.append(
                f"High repetition rate: {metrics.repetition_rate:.1%} "
                f"({metrics.repeated_actions}/{metrics.total_actions} repeated actions)"
            )
            evidence.append(
                f"Only {metrics.unique_actions} unique actions out of {metrics.total_actions}"
            )
        
        # Determine intervention level
        is_looping = loop_type != LoopType.NONE
        intervention_level = self.config.get_intervention_level(repetition_count)
        
        # Generate suggested action
        suggested_action = self._get_suggested_action(loop_type, tracker)
        
        analysis = LoopAnalysis(
            is_looping=is_looping,
            loop_type=loop_type,
            intervention_level=intervention_level,
            repetition_count=repetition_count,
            evidence=evidence,
            suggested_action=suggested_action,
            metrics=metrics,
        )
        
        self._last_analysis = analysis
        
        if is_looping:
            logger.warning(
                f"[LoopDetector] Loop detected: type={loop_type.value}, "
                f"repetitions={repetition_count}, level={intervention_level.name}"
            )
        
        return analysis
    
    def _get_suggested_action(
        self, 
        loop_type: LoopType, 
        tracker: ProgressTracker
    ) -> Optional[str]:
        """Get suggested action to break the loop."""
        if loop_type == LoopType.VIEW_WITHOUT_MODIFY:
            # Find what file was being viewed
            for action in reversed(tracker.action_history):
                if action.category == ActionCategory.VIEW and action.target_file:
                    ext = action.target_file.split(".")[-1] if "." in action.target_file else ""
                    if ext in ("py", "js", "ts", "sh"):
                        return f"Execute the file to get actual errors: run the {action.target_file}"
            return "Stop viewing and either MODIFY the file or EXECUTE it to verify"
        
        elif loop_type == LoopType.SAME_ACTION_REPEAT:
            return "Do something DIFFERENT. Your previous actions are not working."
        
        elif loop_type == LoopType.NO_PROGRESS:
            return "Make concrete progress: create or modify a file, or execute code"
        
        return None
    
    def generate_intervention(self, analysis: LoopAnalysis) -> Intervention:
        """
        Generate intervention based on loop analysis.
        
        Args:
            analysis: LoopAnalysis from analyze()
            
        Returns:
            Intervention to apply
        """
        level = analysis.intervention_level
        loop_type = analysis.loop_type
        
        # Build evidence string
        evidence_str = "\n".join(f"  - {e}" for e in analysis.evidence)
        
        if level == InterventionLevel.NONE:
            return Intervention(
                level=level,
                message="",
                prompt_injection="",
            )
        
        elif level == InterventionLevel.SOFT_WARNING:
            return self._soft_warning(analysis, evidence_str)
        
        elif level == InterventionLevel.HARD_WARNING:
            return self._hard_warning(analysis, evidence_str)
        
        elif level == InterventionLevel.FORCE_STRATEGY:
            return self._force_strategy(analysis, evidence_str)
        
        elif level == InterventionLevel.ABORT:
            return self._abort_intervention(analysis, evidence_str)
        
        return Intervention(level=level, message="", prompt_injection="")
    
    def _soft_warning(self, analysis: LoopAnalysis, evidence: str) -> Intervention:
        """Generate soft warning intervention."""
        prompt = f"""
## ⚠️ Pattern Warning

The system has detected a potentially unproductive pattern:
{evidence}

**Suggestion**: {analysis.suggested_action or "Try a different approach"}

Please consider changing your approach if you're not making progress.
"""
        return Intervention(
            level=analysis.intervention_level,
            message=f"Soft warning: {analysis.loop_type.value}",
            prompt_injection=prompt,
        )
    
    def _hard_warning(self, analysis: LoopAnalysis, evidence: str) -> Intervention:
        """Generate hard warning intervention."""
        prompt = f"""
## 🚨🚨🚨 CRITICAL: LOOP DETECTED - IMMEDIATE ACTION REQUIRED 🚨🚨🚨

**STOP!** You are stuck in a repetitive loop that is NOT making progress.

**Evidence:**
{evidence}

**Your pattern ({analysis.repetition_count} repetitions):**
- You keep doing the same thing expecting different results
- This is wasting resources and not solving the problem

**MANDATORY ACTION:**
{analysis.suggested_action or "You MUST do something DIFFERENT from your recent actions"}

**Rules:**
1. Do NOT repeat the same viewing/checking commands
2. If you've seen the file content, DO NOT view it again
3. Either MODIFY the file or EXECUTE it to get real results
4. If you claim there's an error, you MUST run the code to prove it

**If you output the same actions again, the system will FORCE a different strategy.**
"""
        return Intervention(
            level=analysis.intervention_level,
            message=f"Hard warning: {analysis.loop_type.value}, {analysis.repetition_count} repetitions",
            prompt_injection=prompt,
            require_different_action=True,
        )
    
    def _force_strategy(self, analysis: LoopAnalysis, evidence: str) -> Intervention:
        """Generate forced strategy intervention."""
        forced_actions = self._get_recovery_actions(analysis)
        
        prompt = f"""
## 🛑🛑🛑 SYSTEM OVERRIDE: FORCED RECOVERY 🛑🛑🛑

**The system is taking control because you are stuck in an unbreakable loop.**

**Loop Evidence ({analysis.repetition_count} repetitions):**
{evidence}

**SYSTEM WILL NOW FORCE THE FOLLOWING ACTIONS:**
{self._format_forced_actions(forced_actions)}

**Your claims about "syntax errors" or other issues are NOT verified.**
**The system will now EXECUTE the code to get ACTUAL results.**

**After this forced execution:**
- If there IS a real error, you will see it in the output
- If there is NO error, the task may be complete
- Base your next actions on REAL evidence, not assumptions
"""
        return Intervention(
            level=analysis.intervention_level,
            message=f"Forced recovery: {analysis.loop_type.value}",
            prompt_injection=prompt,
            forced_actions=forced_actions,
            blocked_patterns=self._get_blocked_patterns(analysis),
        )
    
    def _abort_intervention(self, analysis: LoopAnalysis, evidence: str) -> Intervention:
        """Generate abort intervention."""
        prompt = f"""
## ⛔⛔⛔ SYSTEM ABORT: STRATEGY FAILED ⛔⛔⛔

**After {analysis.repetition_count} attempts, the current approach has completely failed.**

**Evidence:**
{evidence}

**The system is ABORTING this approach.**

**YOU MUST:**
1. Completely ABANDON your current line of thinking
2. Start with a FRESH approach
3. If the file exists and seems complete, consider that the task might be DONE
4. Use stop_reason="done" if the original goal appears achieved

**DO NOT:**
- Continue with ANY of your previous actions
- Repeat the same "view file" or "check syntax" pattern
- Claim errors without EXECUTING the code first
"""
        return Intervention(
            level=analysis.intervention_level,
            message=f"Abort: strategy failed after {analysis.repetition_count} attempts",
            prompt_injection=prompt,
            require_different_action=True,
        )
    
    def _get_recovery_actions(self, analysis: LoopAnalysis) -> List[Dict[str, Any]]:
        """Get recovery actions to force."""
        actions = []
        
        # If viewing files repeatedly, force execution
        if analysis.loop_type == LoopType.VIEW_WITHOUT_MODIFY:
            # Find the most viewed file
            if analysis.metrics:
                # Default recovery: run the main script
                actions.append({
                    "tool": "run",
                    "args": {"cmd": "ls -la /workspace/*.js /workspace/*.py 2>/dev/null | head -5"},
                    "reason": "List available scripts to execute",
                })
        
        # Generic recovery: check what's actually there
        if not actions:
            actions.append({
                "tool": "run",
                "args": {"cmd": "find /workspace -maxdepth 2 -name '*.js' -o -name '*.py' | head -10"},
                "reason": "Find executable files",
            })
        
        return actions
    
    def _get_blocked_patterns(self, analysis: LoopAnalysis) -> List[str]:
        """Get patterns that should be blocked."""
        blocked = []
        
        if analysis.loop_type == LoopType.VIEW_WITHOUT_MODIFY:
            blocked.extend(["cat ", "head ", "tail ", "wc "])
        
        if analysis.loop_type == LoopType.SAME_ACTION_REPEAT:
            # Block the repeated action pattern
            # This would need the actual pattern from tracker
            pass
        
        return blocked
    
    def _format_forced_actions(self, actions: List[Dict[str, Any]]) -> str:
        """Format forced actions for display."""
        if not actions:
            return "  (System will determine recovery actions)"
        
        lines = []
        for i, action in enumerate(actions, 1):
            tool = action.get("tool", "unknown")
            args = action.get("args", {})
            reason = action.get("reason", "")
            lines.append(f"  {i}. {tool}: {args}")
            if reason:
                lines.append(f"     Reason: {reason}")
        
        return "\n".join(lines)
    
    def should_force_execution(self) -> bool:
        """Check if the system should force execute recovery actions."""
        if not self._last_analysis:
            return False
        return self._last_analysis.intervention_level >= InterventionLevel.FORCE_STRATEGY
    
    def get_last_analysis(self) -> Optional[LoopAnalysis]:
        """Get the last analysis result."""
        return self._last_analysis
