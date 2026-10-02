import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const base = process.env.DEMO_BASE_URL ?? 'http://127.0.0.1:4173'
const output = resolve('../assets/screenshots/temporary')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
const widths = [320, 360, 390, 430, 768, 1024, 1280, 1440, 1920]
const errors = []
const calls = []
try {
  for (const width of widths) for (const theme of ['light', 'dark']) for (const lang of ['en', 'de']) for (const motion of ['no-preference', 'reduce']) {
    const page = await browser.newPage({ viewport: { width, height: 1000 }, reducedMotion: motion })
    await page.addInitScript(({ theme, lang }) => { localStorage.setItem('eac-theme', theme); localStorage.setItem('eac-lang', lang) }, { theme, lang })
    page.on('pageerror', error => errors.push(error.message))
    page.on('request', request => { if (/\/api\/|openai|localhost:8000|127\.0\.0\.1:8000/.test(request.url())) calls.push(request.url()) })
    await page.goto(base, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { level: 1 }).waitFor()
    if (width === 1440 && lang === 'en') await page.waitForTimeout(2000)
    const metrics = await page.evaluate(() => ({ viewport: innerWidth, width: document.documentElement.scrollWidth, lang: document.documentElement.lang, theme: document.documentElement.dataset.theme }))
    assert.equal(metrics.lang, lang); assert.equal(metrics.theme, theme)
    assert.ok(metrics.width <= metrics.viewport + 1, `Horizontal overflow ${width}/${theme}/${lang}: ${metrics.width}`)
    await page.screenshot({ path: resolve(output, `overview-${width}-${theme}-${lang}-${motion}.png`) })
    await page.close()
  }
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  await page.addInitScript(() => localStorage.setItem('eac-theme', 'light'))
  page.on('request', request => { if (/\/api\/|openai/.test(request.url())) calls.push(request.url()) })
  await page.goto(base, { waitUntil: 'networkidle' })
  const input = page.getByRole('textbox', { name: 'Business question', exact: true })
  await input.fill('What were Henkel H1 2026 sales?')
  await input.press('Meta+Enter')
  await page.getByRole('region', { name: 'Direct answer' }).filter({ hasText: /10,348|10348/ }).waitFor()
  await page.locator('#product').scrollIntoViewIfNeeded()
  await page.screenshot({ path: resolve(output, 'supported-analysis.png') })
  await page.getByRole('button', { name: /^Sources & checks/ }).click()
  await page.getByRole('dialog', { name: 'Sources & checks' }).waitFor()
  await page.screenshot({ path: resolve(output, 'evidence-inspector.png') })
  await page.keyboard.press('Escape')
  const follow = page.getByRole('textbox', { name: 'Follow-up or new question', exact: true })
  await follow.fill('How much Mercedes-Benz Cars EBIT was due to price alone in Q2 2026?')
  await follow.press('Meta+Enter')
  await page.getByRole('heading', { name: 'Not separately disclosed' }).waitFor()
  await page.screenshot({ path: resolve(output, 'governed-refusal.png') })
  await follow.fill('What were Henkel sales?'); await follow.press('Meta+Enter')
  await page.getByRole('heading', { name: 'Which period do you mean?' }).waitFor()
  assert.equal(calls.length, 0, 'Static demo made external/API requests')
  assert.equal(errors.length, 0, 'Browser runtime errors')
  console.log(JSON.stringify({ responsiveStates: widths.length * 8, themes: 2, languages: 2, motionModes: 2, apiRequests: calls.length, runtimeErrors: errors.length, result: 'PASS' }))
} finally { await browser.close() }
