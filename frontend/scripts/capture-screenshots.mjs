import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

const baseURL = process.env.STEP8_BASE_URL ?? 'http://127.0.0.1:8000'
const output = resolve(import.meta.dirname, '../../docs/screenshots')
await mkdir(output, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 })

async function capture(name) {
  await page.screenshot({ path: resolve(output, name), fullPage: true })
}

async function ask(question) {
  const input = page.getByLabel('Business question')
  await input.fill(question)
  await page.getByRole('button', { name: /Analyze/ }).click()
  await page.getByText(/Analysis complete|Governed boundary applied|Clarification required/).waitFor({ timeout: 30_000 })
}

await page.goto(baseURL, { waitUntil: 'networkidle' })
await capture('01-empty-state.png')

await ask('What were Henkel H1 2026 sales?')
await capture('02-analytics-answer.png')

await ask('Why did Henkel organic sales growth change in H1 2026?')
await page.locator('.evidence-panel.panel-open').getByRole('button', { name: 'Close evidence panel' }).click()
await capture('03-hybrid-answer-with-citations.png')

await ask('What contributed to Henkel organic growth in H1 2026?')
const openPanel = page.locator('.evidence-panel.panel-open')
if (await openPanel.count()) await openPanel.getByRole('button', { name: 'Close evidence panel' }).click()
await capture('04-reconciliation-decomposition.png')

await ask('What was BMW revenue in Q2 2026?')
await capture('05-governed-refusal.png')

await ask('Why did Henkel organic sales growth change in H1 2026?')
await page.getByText('How this answer was produced').click()
await capture('06-evidence-provenance-drawer.png')

await browser.close()
console.log(`Captured six screenshots in ${output}`)
