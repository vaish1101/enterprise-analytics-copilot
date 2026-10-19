# Methodology

This page describes the validated default workflow and shared data/release
contracts. The opt-in [four-role candidate](release_candidate_architecture.md)
adds model-backed choices within authorized tool menus; it does not replace
deterministic routing, arithmetic or final release checks.

## From question to bounded plan

Question intake validates length and request shape. The deterministic planner
resolves a catalog-grounded company, metric, business scope, period and operation.
It preserves quarter versus half-year grain, fiscal-period identity and
company-specific semantics. Missing context leads to clarification; unsupported
coverage leads to refusal. A prompt alone cannot onboard a new company or grant
SQL/Python execution.

Supported routes distinguish numerical analysis, documentary knowledge,
combined analysis/context, and reported decomposition. Route selection is
deterministic in both paths. In the default workflow it fixes tool execution;
the experimental roles may choose only among the tools and strategies admitted
within that route.

## Numerical execution

Reviewed facts carry source/evidence identities, metric, scope, period, units and
provenance. Runtime validation precedes execution. Decimal arithmetic calculates
permitted absolute/percentage/percentage-point changes and controlled
reconciliations. Zero or unsuitable denominators and metric policies can make a
percentage change unavailable rather than inviting an invented substitute.

Management decompositions retain the issuer's categories. Mercedes' combined
“Volume / structure / net pricing” label remains one component. Rounding
tolerance is rule-scoped, not a blanket allowance for incorrect prose or
unrelated numerical discrepancies. [Contracts](data_contracts.md)

## Documentary retrieval

Only the authorized full-local environment builds source-derived units. Units
retain source, location, period, scope, metric tags and deterministic identifiers.
Metadata filtering constrains retrieval before MiniLM dense ranking. Top-five
selection provides a bounded documentary context; empty required evidence
blocks documentary release. [Sources and rights](data_sources.md)

The public demo does not substitute made-up corporate paragraphs for the absent
corpus. It deliberately refuses documentary routes.

## Assembly, synthesis and checks

Evidence assembly keeps numerical results and documentary context distinct.
Structured synthesis proposes typed claims and limitations; it cannot become
numerical authority by attaching a citation. Independent verification checks
structured identity, numbers, units, calculation runs, fact lineage, selected
citations, provenance and management-causality restrictions. Conservative prose
checks reject unsupported numerical expression formats and contradictions.

One revision is allowed for eligible failed drafts. Final release can keep a
supported subset with visible limitations or refuse. Numeric text is rendered
from verified fields; an unchecked free-form summary is never the released
numerical answer. Frontend runtime validation is a second defensive boundary.

## What the method does not establish

Correct arithmetic does not prove semantic equivalence, a retrieved passage does
not prove causality, and verifier PASS does not certify universal truth. The
method is bounded by source coverage, extraction quality, catalog definitions
and tested contracts. [Verification](provenance_and_verification.md) ·
[Limitations](limitations.md)
