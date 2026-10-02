# Henkel H1 2026 extraction decision

## Decision

**APPROVED WITH MANUAL CURATION**

The official half-year financial report is suitable for a deterministic initial
data foundation. It exposes stable document pages, table headings, row labels,
units, and numeric price/volume disclosures. However, it is a PDF rather than an
official structured workbook, and its multi-page layout and rounded values make
unreviewed bulk extraction inappropriate for the first release.

The official file was acquired and signature-validated at 2,580,568 bytes with
SHA-256 `b4df29f39f9530c44af0dc2a21bd7e261457ed878d64e7f359021eb218e3fc97`.
Visual and text-layer inspection confirmed the Group sales-development table on
PDF page 7 (printed page 6) and the business-unit tables on PDF pages 11 and 13
(printed pages 10 and 12).

## Initial extraction approach

1. Pin the acquired official file by SHA-256.
2. Maintain a reviewed map of metric ID to page, table heading, row label, and
   column/period label.
3. Extract text or table candidates deterministically from the pinned file.
4. Require expected headings and labels, expected row counts, valid numeric
   syntax, units, and period labels.
5. Review and curate the candidate facts before loading the normalized tables.
6. Run the price-plus-volume and nominal-change reconciliations with the cataloged
   rounding tolerances.

## Change controls

Extraction fails closed if the hash changes, an expected page or label disappears,
more than one candidate matches a mapped location, a unit changes, or a
reconciliation exceeds tolerance. A changed source must be quarantined and its
mapping reviewed. Source values are retained as published; rounding differences
are recorded, not corrected.

## Known limitations

- No official H1 2026 XLSX was identified in the feasibility audit.
- PDF reading order may not represent the visual table structure.
- Published percentages are rounded and can differ by 0.1 percentage point when
  components are added.
- The decision authorizes governed curation, not automated semantic inference.
