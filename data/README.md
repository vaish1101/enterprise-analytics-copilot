# Public-safe data boundary

The repository includes source_manifest.csv and normalized/facts.csv: official
source metadata/checksums and reviewed derived numerical figures with metric,
scope, period, unit, provenance and lineage. These are the numerical demo's
authority, not a full corpus or freely interchangeable company KPIs.

Mercedes-Benz, Henkel and Siemens are reporting demonstration datasets, not
clients or endorsers. See [sources and rights](../docs/data_sources.md).

## Excluded local assets

raw_sources/ holds publisher-owned reports/workbooks acquired locally.
retrieval/local/ holds extracted text, model caches, embeddings, indexes and
private runtime/evaluation artifacts. checkpoints/ holds graph/session state.
All remain excluded from Git and public Docker input. Never move them into a
public folder to repair reproduction.

## Authorized full-local acquisition

Acquisition and corpus scripts remain as implementation evidence, not public
quickstart requirements. They validate official hosts, TLS, media/signatures,
checksums and protected output locations; they do not bypass access controls.
Rebuilding requires suitable rights, source access and private local assets.
Do not run frozen held evaluations as setup.

Use [the numerical Docker demo](../docs/reproduction.md) for public reproduction.
