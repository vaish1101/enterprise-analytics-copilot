"""Request-local source selection contract. Models never serialize source objects."""
from enum import Enum
import re
from pydantic import Field, create_model, model_validator
from .models import Contract
from .post_synthesis import (CompactSynthesis, ContextStatement, compact_payload,
                            evidence_map, governed_draft)


class SynthesisContractError(ValueError):
    pass


class SelectedClaim(Contract):
    kind: str
    evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=2)
    text: str | None

    @model_validator(mode='after')
    def source_owned(self):
        if self.kind not in {'source', 'interpretation', 'limitation'}:
            raise ValueError('Unsupported documentary claim kind')
        if self.kind == 'source' and self.text is not None:
            raise ValueError('Source passage text is application owned')
        if self.kind != 'source' and (not self.text or len(self.text) > 480):
            raise ValueError('Semantic claim needs bounded text')
        return self


class SourceSynthesis(Contract):
    direct_answer: SelectedClaim | None
    context: tuple[SelectedClaim, ...] = Field(max_length=2)


def contract(bundle):
    """Enums enforce the actual menu on the wire, in addition to local checks."""
    docs = evidence_map(bundle)
    ids = Enum('SelectedEvidence', {f'E{i}': k for i, k in enumerate(docs)}, type=str) if docs else type(None)
    kinds = Enum('DocumentaryKind', {x.upper(): x for x in ('source','interpretation','limitation')}, type=str)
    claim = create_model('SourceClaim', __base__=SelectedClaim,
        kind=(kinds, ...), evidence_ids=(tuple[ids, ...], Field(min_length=1,max_length=2)))
    fields = {'direct_answer': (claim | None, ...),
              'context': (tuple[claim, ...], Field(max_length=2))}
    numeric = governed_draft(bundle).claims
    if numeric:
        refs = Enum('NumericFactRef', {f'N{i}': c.claim_id for i,c in enumerate(numeric)}, type=str)
        fields['numeric_fact_ids'] = (tuple[refs, ...], Field(max_length=len(numeric)))
    return create_model('HybridSynthesis' if numeric else 'DocumentarySynthesis',
                        __base__=SourceSynthesis, **fields)


def payload(bundle, observations=()):
    result = compact_payload(bundle, observations)
    result['authority'] = 'Numbers and citations are application owned; select supplied references only.'
    result['numeric_fact_ids'] = [c.claim_id for c in governed_draft(bundle).claims]
    return result


def excerpt(text):
    """Deterministically omit only the labelled fixture preamble, not content."""
    return re.sub(r'^Synthetic development (?:commentary|definition), not an issuer (?:quotation|definition)\.\s*', '', text)


def resolve(bundle, output):
    docs = evidence_map(bundle)
    numeric = {c.claim_id for c in governed_draft(bundle).claims}
    if not set(getattr(output, 'numeric_fact_ids', ())).issubset(numeric):
        raise SynthesisContractError('Unknown numeric fact reference')
    def statement(c):
        if c is None:
            return None
        if not set(c.evidence_ids).issubset(docs):
            raise SynthesisContractError('Unknown evidence reference')
        if c.kind == 'source':
            if len(c.evidence_ids) != 1 or c.text is not None:
                raise SynthesisContractError('Source selection must name one canonical passage')
            text = excerpt(docs[c.evidence_ids[0]].text)
            kind = 'quote'
        else:
            text, kind = c.text, c.kind
            # Numerical authority is not available through free-form narrative.
            if re.search(r'\d', text):
                raise SynthesisContractError('Narrative cannot regenerate numeric values')
        return ContextStatement(kind=kind,text=text,evidence_ids=c.evidence_ids)
    return CompactSynthesis(direct_answer=statement(output.direct_answer),
                            context=tuple(statement(c) for c in output.context))
