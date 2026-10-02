"""V2-only intent adapter; the validated v1 planner is never edited."""
import re

from src.planning.planner import QuestionPlanner
from src.planning.models import AnalyticalPlan


class BoundedIntentPlanner(QuestionPlanner):
    def plan(self, question, *, question_id=None):
        rewritten = question
        replacements = (
            (r"\bwhat helped(?: most)?\b", "rank the largest positive reported contributions to"),
            (r"\bwhat hurt(?: most)?\b", "rank the largest negative reported contributions to"),
            (r"\b(?:biggest|largest|most) positive (?:contributor|contribution|impact)\b", "rank the largest positive reported contributions"),
            (r"\b(?:biggest|largest|most) negative (?:contributor|contribution|impact)\b", "rank the largest negative reported contributions"),
            (r"\b(?:biggest|largest) (?:absolute(?:-magnitude)? )?(?:impact|contributor|contribution)\b", "rank the contributions by absolute magnitude"),
        )
        for pattern, replacement in replacements:
            rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)
        plan = super().plan(rewritten, question_id=question_id)
        if rewritten == question:
            return plan
        # All original catalog, target, period-grain and unsupported-split checks
        # still apply. Only this optional mode understands the new intent aliases.
        return AnalyticalPlan.model_validate({**plan.model_dump(),
            "raw_question": question, "planner_version": "bounded-intents-0.3"})
