/*
 * Questions offered in the interface, grouped by what someone wants to do. Every question
 * here is checked against the planner in tests/test_step8_10_phrasing.py: only questions the
 * system actually answers are ever suggested. Order matches `hero.categories` in the strings.
 */
export const CATEGORY_EXAMPLES: string[][] = [
  ['What were Henkel H1 2026 sales?', 'What was Siemens revenue in Q2 2026?'],
  ['Calculate the difference between Henkel H1 2025 sales and H1 2026 sales.', 'How did Mercedes-Benz Group revenue change from Q2 2025 to Q2 2026?'],
  ['What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?', 'What drove Henkel organic sales growth in H1 2026?'],
  ['How does Henkel define organic sales growth?', 'How does Siemens define Industrial Business profit?'],
  ['What did management say about Mercedes-Benz Cars adjusted EBIT in Q2 2026?', 'What did management say about Henkel organic sales growth in H1 2026?'],
  ['Where does the Henkel sales figure for H1 2026 come from?', 'Show the source for Henkel sales in H1 2026'],
]
