"""V2-only intent adapter; the validated v1 planner is never edited."""
import re

from src.planning.planner import QuestionPlanner
from src.planning.models import AnalyticalPlan


class BoundedIntentPlanner(QuestionPlanner):
    def plan(self, question, *, question_id=None):
        rewritten = question
        calculated_sales_intent=False
        # A request to calculate a two-period sales difference is not a lookup
        # of the catalog's separately reported "nominal sales change" metric.
        # Preserve explicit nominal/percentage requests and all v1 behavior.
        if (re.search(r'\bcalculate\b',rewritten,re.I)
            and re.search(r'\bsales change from\b',rewritten,re.I)
            and not re.search(r'\b(?:nominal|organic|percent(?:age)?|reported change)\b|%',rewritten,re.I)):
            rewritten=re.sub(r'\bsales change from\b','change in sales from',rewritten,flags=re.I)
            calculated_sales_intent=True
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
            "raw_question": question, "planner_version": "bounded-intents-0.4" if calculated_sales_intent else "bounded-intents-0.3"})
