/**
 * Display formatting for governed values.
 *
 * Values arrive as exact decimal strings. Formatting is purely typographic:
 * digit grouping, a true minus sign and a unit suffix. The digits themselves
 * are never re-parsed through floating point, rounded or rescaled.
 */

const MINUS = '−'

/** Interface locale for typography only (grouping, decimal mark, unit placement). */
let locale: 'en' | 'de' = 'en'
export function setFormatLocale(next: 'en' | 'de') { locale = next }
export function formatLocale() { return locale }

export type ValueParts = { sign: '' | '+' | typeof MINUS; digits: string; unit: string; prefix: string }

const DECIMAL = /^-?\d+(\.\d+)?$/

export function isGovernedDecimal(value: string | null | undefined): value is string {
  return typeof value === 'string' && DECIMAL.test(value)
}

function group(integer: string): string {
  return integer.replace(/\B(?=(\d{3})+(?!\d))/g, locale === 'de' ? '.' : ',')
}

export function unitParts(unit: string | null | undefined): { prefix: string; suffix: string; spoken: string } {
  if (locale === 'de') switch (unit) {
    case 'EUR_million': return { prefix: '', suffix: '\u00a0Mio.\u00a0€', spoken: 'Millionen Euro' }
    case 'percentage_point': return { prefix: '', suffix: '\u00a0Pp.', spoken: 'Prozentpunkte' }
    case 'percent': return { prefix: '', suffix: '\u00a0%', spoken: 'Prozent' }
    case 'vehicle': return { prefix: '', suffix: ' Fahrzeuge', spoken: 'Fahrzeuge' }
  }
  switch (unit) {
    case 'EUR_million': return { prefix: '€', suffix: 'm', spoken: 'million euros' }
    case 'percentage_point': return { prefix: '', suffix: ' pp', spoken: 'percentage points' }
    case 'percent': return { prefix: '', suffix: '%', spoken: 'percent' }
    case 'vehicle': return { prefix: '', suffix: ' units', spoken: 'vehicles' }
    default: return { prefix: '', suffix: unit ? ` ${unit.replaceAll('_', ' ')}` : '', spoken: unit?.replaceAll('_', ' ') ?? '' }
  }
}

export function unitName(unit: string | null | undefined): string {
  if (locale === 'de') switch (unit) {
    case 'EUR_million': return 'Mio.\u00a0€'
    case 'percentage_point': return 'Prozentpunkte'
    case 'percent': return 'Prozent'
    case 'vehicle': return 'Fahrzeuge'
  }
  switch (unit) {
    case 'EUR_million': return '€ million'
    case 'percentage_point': return 'percentage points'
    case 'percent': return 'percent'
    case 'vehicle': return 'vehicles'
    default: return unit?.replaceAll('_', ' ') ?? ''
  }
}

/** Split a governed value into typographic parts. `signed` forces a leading + for positives. */
/**
 * Calculated ratios can carry many decimals. For display only, round a percent to one
 * decimal using string arithmetic (half away from zero); the exact value stays available.
 */
export function displayDecimal(value: string, unit: string | null | undefined): string {
  if (unit !== 'percent' || !isGovernedDecimal(value)) return value
  const [int, frac = ''] = value.replace('-', '').split('.')
  if (frac.length <= 2) return value // reported precision is shown as published
  let tenths = BigInt(int + frac[0])
  if (Number(frac[1]) >= 5) tenths += 1n
  const text = tenths.toString().padStart(2, '0')
  const rounded = `${text.slice(0, -1)}.${text.slice(-1)}`
  return (value.startsWith('-') && tenths !== 0n ? '-' : '') + rounded
}

export function valueParts(value: string, unit: string | null | undefined, signed = false): ValueParts {
  value = displayDecimal(value, unit)
  if (!isGovernedDecimal(value)) return { sign: '', digits: value, unit: unitParts(unit).suffix, prefix: unitParts(unit).prefix }
  const negative = value.startsWith('-')
  const body = negative ? value.slice(1) : value
  const [integer, fraction] = body.split('.')
  const digits = group(integer) + (fraction !== undefined ? `${locale === 'de' ? ',' : '.'}${fraction}` : '')
  const isZero = /^0+(\.0+)?$/.test(body)
  const sign = negative ? MINUS : signed && !isZero ? '+' : ''
  const parts = unitParts(unit)
  return { sign, digits, unit: parts.suffix, prefix: parts.prefix }
}

export function formatValue(value: string, unit: string | null | undefined, signed = false): string {
  const p = valueParts(value, unit, signed)
  return `${p.sign}${p.prefix}${p.digits}${p.unit}`
}

/** Screen-reader phrasing: "minus 602 million euros". */
export function spokenValue(value: string, unit: string | null | undefined): string {
  const negative = value.startsWith('-')
  const body = negative ? value.slice(1) : value
  return `${negative ? 'minus ' : ''}${locale === 'de' ? body.replace('.', ',') : body} ${unitParts(unit).spoken}`.trim()
}

export function isNegative(value: string): boolean {
  return isGovernedDecimal(value) && value.startsWith('-') && !/^-0+(\.0+)?$/.test(value)
}

/**
 * Relative magnitude for chart geometry only. Governed values in this product are
 * small decimals (at most a few million), so conversion to a JS number for
 * *layout* is exact enough; the displayed label always uses the original string.
 */
export function magnitude(value: string): number {
  return isGovernedDecimal(value) ? Number(value) : 0
}
