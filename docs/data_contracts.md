# Data contract invariants

These invariants apply to every normalized metric fact and are enforced by the
SQL schema and mirrored by the Python models.

1. A metric, business scope, and source document each belong to exactly one
   company. Composite foreign keys require a fact and its evidence to use that
   same company.
2. Period grain uses only `QUARTER`, `HALF_YEAR`, `YEAR`, `POINT_IN_TIME`,
   `QUARTER_YOY`, or `HALF_YEAR_YOY`. Each metric has explicit allowed grains;
   pipe-separated pseudo-types are invalid.
3. Each metric has explicit allowed scope types. A fact must reference both a
   scope owned by its company and a scope type allowed for its metric.
4. Fact unit and value type must exactly match the metric definition.
5. Provenance and claim semantics are separate controlled fields. A
   `MANAGEMENT_ATTRIBUTED` fact must use `MANAGEMENT_ATTRIBUTION`, cannot be
   marked causal, and cannot receive `HIGH` confidence.
6. No current metric permits a causal claim. Adding causal evidence later
   requires an explicit new contract and migration.
7. A `CALCULATED` fact must match a successful deterministic calculation run,
   including output metric, company, result value, versioned rule, execution
   metadata, input digest, and at least one governed input fact.
8. Reported and management-attributed facts require an allow-listed primary
   source and must not reference a calculation run.
9. Each `fact_evidence` row references one evidence expectation, one source
   document, and one concrete page/sheet and optional cell/range. Multi-document
   support is represented by multiple rows rather than free-text concatenation.
10. Acquisition output must resolve inside `data/raw_sources/`. Project paths,
    external paths, traversal, and symlink escapes fail before transfer.

`config/controlled_vocabularies.csv` is the reviewable vocabulary register.
Tests require it to agree with the Python enums and SQL reference tables.
