"""V2-only typed answer identity and source authenticity, not model assertions."""
from enum import Enum
from src.orchestration.models import SynthesisDraft
from .models import Contract


class ComponentRole(str, Enum):
    DIRECT_ANSWER = 'direct_answer'
    SUPPORTING_CONTEXT = 'supporting_context'
    LIMITATION = 'limitation'
    ABSTENTION = 'abstention'


class Authenticity(str, Enum):
    PUBLIC_REPORT = 'PUBLIC_REPORT'
    SYNTHETIC_FIXTURE = 'SYNTHETIC_FIXTURE'
    DERIVED_ANALYSIS = 'DERIVED_ANALYSIS'


class AnswerComponent(Contract):
    claim_id: str
    role: ComponentRole
    authenticity: Authenticity
    evidence_ids: tuple[str, ...]
    # Application-owned, never part of the model's source selection contract.
    source_quotation: bool = False


class TypedDraft(SynthesisDraft):
    components: tuple[AnswerComponent, ...] = ()
    fixture_mode: bool = False


def authenticity(item):
    # Source metadata is pinned by retrieval; never supplied by Synthesis.
    if item.source_id.startswith('synthetic_') or getattr(item,'parser_version','').startswith('synthetic') or 'synthetic' in item.source_title.lower():
        return Authenticity.SYNTHETIC_FIXTURE
    return Authenticity.PUBLIC_REPORT


def components(draft):
    return {c.claim_id:c for c in getattr(draft,'components',())}
