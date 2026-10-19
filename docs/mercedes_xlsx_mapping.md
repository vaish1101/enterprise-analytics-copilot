# Mercedes-Benz Q2 2026 XLSX mapping

## Gate status

**PASSED — OFFICIAL WORKBOOK ACQUIRED, VALIDATED, AND MAPPED**

- File: `mercedes-benz-fact-sheet-q2-2026.xlsx`
- Source ID: `mercedes_q2_2026_fact_sheet_xlsx`
- HTTP status: `200`
- Media type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Size: `770145` bytes
- SHA-256: `907950655af45d774f5b2b2acc5b72caa5cb71184851cfdad6bd9312ac0169bf`
- Workbook structure: 27 sheets; all mapped target ranges contain static values,
  not formulas.

The common data columns on the mapped sheets are `C` Q2 2025, `D` Q3 2025,
`E` Q4 2025, `F` Q1 2026, `G` Q2 2026, `H` Q2-on-Q2 change, `I` Q1-Q2
2025, `J` Q1-Q2 2026, and `K` year-to-date change.

## Exact KPI map

The label cell identifies the row. The Q2 2026 and Q1-Q2 2026 cells are the
two governed periods for the initial mapping.

| Scope | Metric | Sheet | Label cell | Q2 2026 cell/value | Q1-Q2 2026 cell/value | Unit |
|---|---|---|---|---:|---:|---|
| Group | Revenue | `4 - Key Figures` | `B9` | `G9` = 32,061 | `J9` = 63,663 | EUR million |
| Group | EBIT | `4 - Key Figures` | `B11` | `G11` = 1,547 | `J11` = 3,451 | EUR million |
| Group | EBIT adjusted | `13 - EBIT Adjusted` | `B25` | `G25` = 2,299 | `J25` = 4,072 | EUR million |
| Mercedes-Benz Cars | Unit sales | `19 - MBC Overview` | `B9` | `G9` = 417,765 | `J9` = 837,195 | vehicles |
| Mercedes-Benz Cars | Revenue | `19 - MBC Overview` | `B13` | `G13` = 22,987 | `J13` = 45,945 | EUR million |
| Mercedes-Benz Cars | EBIT | `19 - MBC Overview` | `B14` | `G14` = 49 | `J14` = 858 | EUR million |
| Mercedes-Benz Cars | EBIT adjusted | `19 - MBC Overview` | `B15` | `G15` = 909 | `J15` = 1,842 | EUR million |
| Mercedes-Benz Vans | Unit sales | `23 - MBV Overview` | `B9` | `G9` = 94,075 | `J9` = 174,331 | vehicles |
| Mercedes-Benz Vans | Revenue | `23 - MBV Overview` | `B13` | `G13` = 4,455 | `J13` = 8,579 | EUR million |
| Mercedes-Benz Vans | EBIT | `23 - MBV Overview` | `B14` | `G14` = 502 | `J14` = 894 | EUR million |
| Mercedes-Benz Vans | EBIT adjusted | `23 - MBV Overview` | `B15` | `G15` = 454 | `J15` = 869 | EUR million |
| Mercedes-Benz Financial Services | Revenue | `27 - MBFS Overview` | `B15` | `G15` = 6,180 | `J15` = 12,285 | EUR million |
| Mercedes-Benz Financial Services | EBIT | `27 - MBFS Overview` | `B16` | `G16` = 475 | `J16` = 874 | EUR million |
| Mercedes-Benz Financial Services | EBIT adjusted | `27 - MBFS Overview` | `B17` | `G17` = 492 | `J17` = 905 | EUR million |

The same revenue/EBIT values also appear in the dedicated segment sheets. The
overview sheets above are the preferred mapping because they co-locate unit sales,
revenue, EBIT, and adjusted EBIT for each governed scope.

## Adjustment-category map and sign convention

Sheet `12 - EBIT Adjustments` stores amounts on a **reported EBIT to adjusted
EBIT** basis. The presentation waterfall shows the opposite direction, from
adjusted EBIT to reported EBIT. Therefore, the same economic adjustment has the
opposite sign in the two sources.

| Scope | XLSX Q2 2026 category range | XLSX sum | XLSX reconciliation | Presentation reconciliation |
|---|---|---:|---|---|
| Cars | `12 - EBIT Adjustments!G10:G13` | +860 | 49 + 860 = 909 | 909 - 860 = 49 |
| Vans | `12 - EBIT Adjustments!G16:G19` | -48 | 502 - 48 = 454 | 454 + 48 = 502 |
| Financial Services | `12 - EBIT Adjustments!G22:G25` | +17 | 475 + 17 = 492 | 492 - 17 = 475 |
| Reconciliation | `12 - EBIT Adjustments!G28:G31` | -77 | Group reconciliation component | Not a segment waterfall |
| Group total | four ranges above | +752 | 1,547 + 752 = 2,299 | 2,299 - 752 = 1,547 |

## PDF and report reconciliation

- `4 - Key Figures!G9`, `G11`, `J9`, and `J11` match the fact-sheet PDF page 4
  and interim report page 3 exactly.
- `13 - EBIT Adjusted!G25` and `J25` match interim report page 3 exactly.
- The Cars cells above match fact-sheet PDF page 19 and interim report pages 4-5.
- The Vans cells above match fact-sheet PDF page 23 and interim report pages 4-5.
- The Financial Services cells above match fact-sheet PDF page 27 and interim
  report pages 4-5.
- The Cars, Vans, and Financial Services adjustment direction and endpoint values
  match presentation PDF pages 8, 11, and 21 respectively.

No numeric contradiction was found in the governed cells.

## Full bridge boundary

The XLSX is structured for KPIs, EBIT statements, adjusted EBIT, and adjustment
categories, but it does **not** contain the full management bridge drivers. Exact
workbook searches returned no cells for `Volume / structure / net pricing`,
`Industrial performance`, `Cost of credit risk`, or `Volume / margin`.

Accordingly, these management-attributed bridge components remain PDF-only:

| Scope | Source | Bridge from Q2 2025 adjusted EBIT to Q2 2026 adjusted EBIT |
|---|---|---|
| Cars | Presentation page 8 | 1,228; -602 volume / structure / net pricing; +17 FX; +482 industrial performance; -194 selling; -28 G&A; +143 R&D; -137 others; 909 endpoint |
| Vans | Presentation page 11 | 441; +98 volume / structure / net pricing; -16 FX; -94 industrial performance; +7 selling; -1 G&A; +38 R&D; -19 others; 454 endpoint |
| Financial Services | Presentation page 21 | 290; -7 FX; +66 cost of credit risk; +188 volume / margin; +31 selling; +2 G&A; -78 others; 492 endpoint |

This is a source boundary, not a defect: bridge-driver facts must retain the
presentation source ID and `MANAGEMENT_ATTRIBUTED` provenance, while workbook
cells support the reported endpoints and adjustment categories.
