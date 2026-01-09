"""Importance scorer for memory items."""

from typing import Any, Dict


class ImportanceScorer:
    """Score importance of memory items (0.0-1.0)."""

    @staticmethod
    def score_decision(decision: Dict[str, Any]) -> float:
        """
        Score importance of a decision.

        Args:
            decision: Decision dictionary

        Returns:
            Importance score (0.0-1.0)
        """
        score = 0.5  # Base score

        content = decision.get("content", "").lower()
        context = decision.get("context", {})

        # Keyword-based scoring
        important_keywords = [
            ("架构", 0.3),
            ("设计", 0.3),
            ("技术选型", 0.2),
            ("框架", 0.2),
            ("库", 0.2),
            ("错误", 0.3),
            ("bug", 0.3),
            ("关键", 0.2),
            ("重要", 0.2),
            ("决定", 0.1),
        ]
        for keyword, points in important_keywords:
            if keyword in content:
                score += points

        # Impact-based scoring
        files_affected = context.get("files_affected", 0)
        if files_affected > 5:
            score += 0.2
        elif files_affected > 2:
            score += 0.1

        # Step-based scoring (earlier decisions might be more important)
        step = decision.get("step", 0)
        if step <= 3:
            score += 0.1  # Early decisions are often foundational

        return min(1.0, score)

    @staticmethod
    def score_milestone(milestone: Dict[str, Any]) -> float:
        """
        Score importance of a milestone.

        Args:
            milestone: Milestone dictionary

        Returns:
            Importance score (0.0-1.0)
        """
        # Milestones are generally important
        base_score = 0.7

        content = milestone.get("content", "").lower()

        # Completion keywords
        if any(keyword in content for keyword in ["完成", "成功", "达成", "实现"]):
            base_score += 0.2

        # Scale keywords
        if any(keyword in content for keyword in ["全部", "所有", "核心", "主要"]):
            base_score += 0.1

        return min(1.0, base_score)

    @staticmethod
    def score_learning(learning: str) -> float:
        """
        Score importance of a learning.

        Args:
            learning: Learning text

        Returns:
            Importance score (0.0-1.0)
        """
        score = 0.6  # Base score for learnings

        learning_lower = learning.lower()

        # Error-related learnings are important
        if any(keyword in learning_lower for keyword in ["错误", "失败", "bug", "问题"]):
            score += 0.3

        # Solution-related learnings are important
        if any(keyword in learning_lower for keyword in ["解决", "方法", "技巧", "最佳实践"]):
            score += 0.2

        return min(1.0, score)

    @staticmethod
    def score_attempt(attempt: Dict[str, Any]) -> float:
        """
        Score importance of an attempt.

        Args:
            attempt: Attempt dictionary

        Returns:
            Importance score (0.0-1.0)
        """
        score = 0.4  # Base score

        # Successful attempts with many files are important
        if attempt.get("success", False):
            files_count = len(attempt.get("files", []))
            if files_count > 3:
                score += 0.3
            elif files_count > 0:
                score += 0.2

        # Failed attempts might be important for learning
        if not attempt.get("success", False):
            score += 0.2  # Failures teach us something

        return min(1.0, score)
