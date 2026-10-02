"""Independent deterministic claim verifier for Step 6."""

from __future__ import annotations

import hashlib
import re

from src.analytics.models import WarningCode
from src.schemas.models import ProvenanceType
from .numerical_prose import numerical_prose_matches

from .models import (
    Claim,
    ClaimCheck,
    ClaimSupport,
    EvidenceBundle,
    SynthesisDraft,
    VerificationResult,
    VerificationVerdict,
)


_CAUSAL = re.compile(r"\b(caused|led to|resulted in|because of|drove)\b", re.IGNORECASE)


class DeterministicVerifier:
    """Checks structured claims and their released prose against governed evidence."""

    def verify(self, draft: SynthesisDraft, evidence: EvidenceBundle) -> VerificationResult:
        analytics = evidence.analytics
        retrieved = {item.evidence_unit_id: item for item in evidence.retrieval.results} if evidence.retrieval else {}
        facts = {}
        runs = {}
        if analytics:
            candidates = [analytics.primary_result, analytics.comparison_result, *analytics.supporting_results, *analytics.decomposition_components]
            facts = {item.fact_id: item for item in candidates if item is not None}
            runs = {item.run_id: item for item in analytics.calculation_runs}
        checks: list[ClaimCheck] = []
        global_errors: list[str] = [] if draft.claims else ["NO_RELEASABLE_CLAIMS"]
        supported: list[str] = []
        conflict = False
        for claim in draft.claims:
            errors: list[str] = []
            fact_lineage = [facts.get(fid) for fid in claim.fact_ids]
            if any(item is None for item in fact_lineage):
                errors.append("UNKNOWN_FACT_LINEAGE")
            valid_facts = [item for item in fact_lineage if item is not None]
            financial_quantity = bool(
                re.search(r"\d|\b(?:hundred|thousand|one|two|three|four|five|six|seven|eight|nine|ten)\b", claim.text, re.I)
                and re.search(r"EUR|USD|€|\$|million|billion|percent|%|percentage.point|\b(?:sales|revenue|EBIT|margin|growth|profit)\b", claim.text, re.I)
            )
            if claim.value is None and (claim.fact_ids or financial_quantity) and not numerical_prose_matches(claim.text, set(), set()):
                errors.append("NUMERIC_VALUE_MISSING")
            if claim.value is not None:
                if not numerical_prose_matches(claim.text, {claim.value}, {claim.unit}):
                    errors.append("NUMERICAL_PROSE_CONTRADICTION")
                expected_values = {item.value for item in valid_facts}
                expected_values.update(run.result_value for rid in claim.calculation_run_ids if (run := runs.get(rid)) and run.result_value is not None)
                if not expected_values or claim.value not in expected_values:
                    errors.append("WRONG_OR_UNSUPPORTED_NUMBER")
            if valid_facts:
                expected = valid_facts[0]
                if claim.company_id != expected.company.value: errors.append("WRONG_COMPANY")
                if claim.metric_id != expected.metric_id.value: errors.append("WRONG_METRIC")
                if claim.business_scope != expected.business_scope: errors.append("WRONG_SCOPE")
                if not set(claim.periods).issubset({item.period.value for item in valid_facts}): errors.append("WRONG_PERIOD")
                allowed_units = {expected.unit.value}
                if claim.claim_type.value == "CALCULATED":
                    allowed_units = {
                        "percent" if run.output_field.value == "PERCENT_CHANGE" else
                        "percentage_point" if run.output_field.value == "PERCENTAGE_POINT_CHANGE" else expected.unit.value
                        for rid in claim.calculation_run_ids
                        if (run := runs.get(rid)) and run.result_value == claim.value
                    }
                if claim.value is not None and claim.unit not in allowed_units:
                    errors.append("WRONG_UNIT")
                if claim.claim_type.value == "CALCULATED" and expected.provenance_type is not ProvenanceType.CALCULATED and not claim.calculation_run_ids:
                    errors.append("PROVENANCE_RELABELING")
                if expected.provenance_type is ProvenanceType.MANAGEMENT_ATTRIBUTED and claim.claim_type.value != "MANAGEMENT_ATTRIBUTED":
                    errors.append("PROVENANCE_RELABELING")
                if expected.provenance_type is not ProvenanceType.MANAGEMENT_ATTRIBUTED and claim.claim_type.value == "MANAGEMENT_ATTRIBUTED":
                    errors.append("PROVENANCE_RELABELING")
                if expected.provenance_type is ProvenanceType.MANAGEMENT_ATTRIBUTED and _CAUSAL.search(claim.text):
                    errors.append("CAUSAL_OVERSTATEMENT")
            if claim.claim_type.value == "CALCULATED":
                if not claim.calculation_run_ids: errors.append("CALCULATION_LINEAGE_MISSING")
                if any(rid not in runs for rid in claim.calculation_run_ids): errors.append("UNKNOWN_CALCULATION_RUN")
            for evidence_id in claim.evidence_ids:
                if evidence_id.startswith("eu_"):
                    item = retrieved.get(evidence_id)
                    if item is None:
                        errors.append("CITATION_NOT_IN_RETRIEVED_TOP_K")
                        continue
                    if claim.company_id and claim.company_id != item.company_id: errors.append("CITATION_WRONG_COMPANY")
                    if claim.metric_id and item.metric_ids and claim.metric_id not in item.metric_ids: errors.append("CITATION_WRONG_METRIC")
                    if claim.business_scope and item.business_scopes and claim.business_scope not in item.business_scopes: errors.append("CITATION_WRONG_SCOPE")
                    if claim.periods and item.reporting_periods and not set(claim.periods).issubset(item.reporting_periods): errors.append("CITATION_WRONG_PERIOD")
            if evidence.retrieval and not claim.fact_ids and not claim.evidence_ids:
                errors.append("DOCUMENT_CITATION_MISSING")
            if claim.claim_type.value == "INTERPRETATION" and not claim.evidence_ids:
                errors.append("UNSUPPORTED_INTERPRETATION")
            support = ClaimSupport.SUPPORTED if not errors else ClaimSupport.UNSUPPORTED
            if "WRONG_OR_UNSUPPORTED_NUMBER" in errors and any(eid in retrieved for eid in claim.evidence_ids):
                support = ClaimSupport.CONFLICTING
                conflict = True
            checks.append(ClaimCheck(claim_id=claim.claim_id, support=support, errors=tuple(dict.fromkeys(errors))))
            if not errors:
                supported.append(claim.claim_id)
        numeric_claims = [claim for claim in draft.claims if claim.value is not None]
        if numeric_claims and not numerical_prose_matches(
            draft.answer, {claim.value for claim in numeric_claims}, {claim.unit for claim in numeric_claims}
        ):
            global_errors.append("ANSWER_NUMERICAL_PROSE_CONTRADICTION")
        if analytics and WarningCode.ROUNDING_TOLERANCE_APPLIED in analytics.warnings:
            if "ROUNDING_TOLERANCE_APPLIED" not in draft.limitations and "rounding" not in draft.answer.lower():
                global_errors.append("HENKEL_ROUNDING_CAVEAT_OMITTED")
        if evidence.conflict_notes:
            global_errors.append("EVIDENCE_CONFLICT")
            conflict = True
        all_errors = [error for check in checks for error in check.errors] + global_errors
        if not all_errors:
            verdict = VerificationVerdict.PASS
        elif conflict and not supported:
            verdict = VerificationVerdict.REFUSE
        else:
            verdict = VerificationVerdict.NEEDS_REVISION
        identity = hashlib.sha256((draft.draft_id + "|" + "|".join(all_errors)).encode()).hexdigest()[:16]
        return VerificationResult(
            verification_id=f"verify_{identity}", verdict=verdict,
            claim_checks=tuple(checks), errors=tuple(global_errors),
            supported_claim_ids=tuple(supported),
        )
