# Provenance and verification

| Label | Meaning | What it does not mean |
|---|---|---|
| REPORTED | Reviewed source-reported numerical fact | Model-estimated or freely calculated figure |
| CALCULATED | Deterministic output with calculation-run and input-fact lineage | An untraced number produced in prose |
| MANAGEMENT_ATTRIBUTED | Issuer-reported bridge contribution or attributed explanation | Independently identified causal effect |
| INTERPRETATION | Evidence-supported analytical language subject to bounded checks | Unrestricted inference or universal semantic verification |
| LIMITATION | A visible boundary/caveat in the answer contract | A fifth numeric claim provenance enum; limitations are stored separately |

## Backend checks

The verifier checks linked numerical authority, company, metric, scope, period,
unit, known calculation runs, selected document citations, provenance relabeling,
causal overstatement and applicable caveats. Reported units must match source
units; calculation units follow linked output fields. Decimal comparisons are
exact at the prose boundary—source rounding tolerance does not excuse arbitrary
answer discrepancies.

Numerical prose checks reject wrong amounts/signs/currencies/scales, extra
unsupported amounts, omitted structured values and unsupported expression
formats. Financial claims cannot obtain numerical authority merely by citing a
retrieved document. Empty drafts do not PASS. These rules are deliberately
conservative and do not implement arbitrary natural-language entailment.

Final numerical text is rendered from verified data and retains source-faithful
labels, including Mercedes' unsplit bridge category. The released answer is
assembled from released claims, never an unchecked model summary.

## Release outcomes

- **PASS:** supported completed claims satisfy the release contract.
- **NEEDS_REVISION:** one bounded revision may be attempted; afterward a supported
  subset can be returned with explicit errors/limitations, not an unqualified PASS.
- **REFUSE / insufficient support:** no unsupported numerical answer is released.
- **Clarification:** missing company/metric/scope/period detail is surfaced.
- **Evidence conflict:** required sources cannot be consolidated safely.

## Frontend boundary

HTTP 200 is not enough. Runtime validation rejects missing or malformed
verification, unsupported verdicts/units/statuses, inconsistent counts and
provenance summaries, duplicate claims and malformed successful payloads.
Completed claim count must equal supported count. Partial release remains
visibly distinct from a normal verified answer. The interface does not replace
backend numerical verification.

## Remaining limits

PASS is not a guarantee that every semantic interpretation is true. Documentary
claims still depend on bounded retrieval and source metadata. Reconciliation
only checks a defined numerical identity; it cannot prove cross-company
comparability. Management attribution remains non-causal even when a bridge
reconciles. [Evaluation](evaluation.md) · [Limitations](limitations.md)
