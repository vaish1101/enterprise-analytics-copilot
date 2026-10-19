"""Origin-aware v2 verification; v1 and governed numerical checks unchanged."""
import hashlib
from src.orchestration.verifier import DeterministicVerifier
from src.orchestration.models import ClaimCheck, ClaimSupport, VerificationVerdict
from .answer_contract import components, authenticity
from .post_synthesis import evidence_map
from .source_ownership import excerpt


def content_origin(claim, draft):
    if claim.value is not None:
        return 'DERIVED_NUMERIC_RESULT' if claim.calculation_run_ids else 'GOVERNED_NUMERIC_FACT'
    component = components(draft).get(claim.claim_id)
    return 'SOURCE_QUOTED_NUMERIC_CONTENT' if component and component.source_quotation else 'MODEL_GENERATED_NUMERIC_CLAIM'


class DeterministicReleaseVerifier(DeterministicVerifier):
    def verify(self, draft, evidence):
        docs = evidence_map(evidence)
        typed = components(draft)
        invalid = {}
        normalized = []
        for claim in draft.claims:
            component = typed.get(claim.claim_id)
            if component and component.source_quotation:
                ids = claim.evidence_ids
                doc = docs.get(ids[0]) if len(ids) == 1 else None
                valid = (doc is not None and claim.text == excerpt(doc.text)
                    and component.evidence_ids == ids and component.authenticity == authenticity(doc)
                    and claim.claim_type.value == 'REPORTED' and claim.value is None
                    and not claim.fact_ids and not claim.calculation_run_ids and claim.unit is None)
                if not valid:
                    invalid[claim.claim_id] = 'INVALID_CANONICAL_QUOTATION'
                # Only proven source quotes bypass generated numeric-prose checks.
                normalized.append(claim.model_copy(update={'text':'Canonical documentary quotation.'}) if valid else claim)
            else:
                normalized.append(claim)
        safe = draft.model_copy(update={'claims':tuple(normalized),
            'answer':' '.join(c.text for c in normalized)})
        result = super().verify(safe, evidence)
        errors = list(result.errors)
        if draft.answer != ' '.join(c.text for c in draft.claims):
            errors.append('ANSWER_CLAIM_RENDERING_MISMATCH')
        checks = tuple(ClaimCheck(claim_id=c.claim_id, support=ClaimSupport.UNSUPPORTED,
            errors=(*c.errors,invalid[c.claim_id])) if c.claim_id in invalid else c for c in result.claim_checks)
        supported = tuple(c.claim_id for c in checks if c.support is ClaimSupport.SUPPORTED)
        verdict = result.verdict if not invalid and not errors else VerificationVerdict.NEEDS_REVISION
        identity = hashlib.sha256((draft.draft_id+draft.model_dump_json()+str(checks)+str(errors)).encode()).hexdigest()[:16]
        return result.model_copy(update={'verification_id':'verify_'+identity,'claim_checks':checks,
            'errors':tuple(errors),'supported_claim_ids':supported,'verdict':verdict})
