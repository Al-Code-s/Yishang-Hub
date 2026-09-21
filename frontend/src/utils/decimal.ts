import Decimal from 'decimal.js'

/**
 * 金额 / 数量计算工具。
 *
 * 强制约束（任务书 5.3）：前端不得用 IEEE754 浮点数累计金额与库存。
 * 所有运算走 decimal.js，最终值仍以后端校验为准。
 */

Decimal.set({ precision: 30, rounding: Decimal.ROUND_HALF_UP, toExpNeg: -9, toExpPos: 30 })

export type Numeric = string | number | Decimal | null | undefined

export const DECIMAL_PLACES = {
  quantity: 6,
  price: 6,
  money: 4,
  rate: 10,
} as const

/** 业务界面统一显示精度：2 位小数（与存储 / 接口精度 `DECIMAL_PLACES` 无关）。 */
export const DISPLAY_PLACES = 2

/** 形如 `12.000000` 的十进制文本；用于判断「这段文本是不是数值」。 */
const DECIMAL_TEXT = /^-?\d+\.\d+$/

export function toDecimal(value: Numeric): Decimal {
  if (value === null || value === undefined || value === '') {
    return new Decimal(0)
  }
  try {
    return new Decimal(value)
  } catch {
    // 非法输入不静默变成 0；抛出以便调用方发现数据问题
    throw new Error(`无法解析为十进制数：${String(value)}`)
  }
}

/** 加法。用于金额、数量累计。 */
export function add(...values: Numeric[]): Decimal {
  return values.reduce<Decimal>((acc, item) => acc.plus(toDecimal(item)), new Decimal(0))
}

export function subtract(a: Numeric, b: Numeric): Decimal {
  return toDecimal(a).minus(toDecimal(b))
}

/** 乘法：单价 × 数量。 */
export function multiply(a: Numeric, b: Numeric): Decimal {
  return toDecimal(a).times(toDecimal(b))
}

export function divide(a: Numeric, b: Numeric): Decimal {
  const divisor = toDecimal(b)
  if (divisor.isZero()) {
    throw new Error('除数不能为 0')
  }
  return toDecimal(a).div(divisor)
}

/** 按业务精度量化：金额 4 位、数量 6 位。 */
export function round(value: Numeric, places: number): Decimal {
  return toDecimal(value).toDecimalPlaces(places, Decimal.ROUND_HALF_UP)
}

/** 转成后端接受的字符串（DecimalField 使用字符串传输）。 */
export function toApiString(value: Numeric, places: number = DECIMAL_PLACES.quantity): string {
  return round(value, places).toFixed(places)
}

/** 千分位分组。 */
function group(text: string): string {
  const negative = text.startsWith('-')
  const body = negative ? text.slice(1) : text
  const [integer, fraction] = body.split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const result = fraction ? `${grouped}.${fraction}` : grouped
  return negative ? `-${result}` : result
}

function trimTrailingZeros(text: string): string {
  return text.includes('.') ? text.replace(/0+$/, '').replace(/\.$/, '') : text
}

/** 按位数输出 0：`places = 2` → `0.00`，`places = 0` → `0`（整数计数列）。 */
function zeroText(places: number): string {
  return places > 0 ? `0.${'0'.repeat(places)}` : '0'
}

/**
 * 统一的数值展示口径：**四舍五入到 2 位小数（HALF_UP）+ 千分位**。
 *
 * 边界与理由：
 * * 空值显示 `-`，不当作 0；
 * * **非零值四舍五入后变成 0 时，保留其真实精度**——否则 BOM 用量 `0.004`、
 *   极小单价 `0.0004` 会被显示成 `0.00`，把「有」说成「没有」；
 * * 该保护只发生在「四舍五入结果恰好为 0」时；`0.055` 这类会进位的值仍按 2 位显示为 `0.06`；
 * * 只影响显示，不回写、不参与提交；提交给后端的精度见 `toApiString`。
 */
export function formatNumber(value: Numeric, places: number = DISPLAY_PLACES): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const decimal = toDecimal(value)
  const rounded = decimal.toDecimalPlaces(places, Decimal.ROUND_HALF_UP)
  if (!rounded.isZero()) {
    return group(rounded.toFixed(places))
  }
  if (decimal.isZero()) {
    return zeroText(places)
  }
  const precise = trimTrailingZeros(
    decimal.toFixed(Math.min(decimal.decimalPlaces(), DECIMAL_PLACES.quantity)),
  )
  // 极小值（如 -0.0000001）在 6 位数量精度内仍为 0，无法保留有效信息，回退常规 0
  return toDecimal(precise).isZero() ? zeroText(places) : group(precise)
}

/** 与 `formatNumber` 同一口径（保留旧名，新增代码请直接用 `formatNumber`）。 */
export function formatDecimal(value: Numeric, places: number = DISPLAY_PLACES): string {
  return formatNumber(value, places)
}

/** 与 `formatNumber` 同一口径（保留旧名，调用处不必区分金额与数量）。 */
export function formatAmount(value: Numeric, places: number = DISPLAY_PLACES): string {
  return formatNumber(value, places)
}

/**
 * 表格 / 详情里的「数值文本」自动格式化。
 *
 * 后端 `DecimalField` 默认以字符串返回（如 `"12.000000"`），列表与详情若直接输出就是
 * 一长串小数。这里**只对形如小数的字符串生效**：
 * 纯整数文本（手机号 `13800138000`、纳税人识别号 `91330100…`、数字型编码）与
 * JS 整数（`id`、计数）一律不处理，避免把「文本」误当成「数字」加上千分位。
 *
 * 返回 `null` 表示「不适用」，调用方按原逻辑渲染。
 */
export function formatNumericText(value: unknown): string | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) && !Number.isInteger(value) ? formatNumber(value) : null
  }
  if (typeof value !== 'string') {
    return null
  }
  const trimmed = value.trim()
  return DECIMAL_TEXT.test(trimmed) ? formatNumber(trimmed) : null
}

/**
 * 编辑表单回填用：把接口值（`"12.000000"`）去掉无意义的末尾 0，得到 `"12"`、`"0.055"`。
 *
 * 与 `formatNumber` 的区别：
 * * **不做四舍五入**，不会因为显示口径把用户已录入的 `0.055` 改成 `0.06`；
 * * 不带千分位，保证回填文本能被原样解析后再次提交。
 */
export function toEditableText(value: Numeric): string {
  if (value === null || value === undefined || value === '') {
    return ''
  }
  const decimal = toDecimal(value)
  return decimal.toFixed(Math.min(decimal.decimalPlaces(), DECIMAL_PLACES.quantity))
}

/** 原生 `<el-table-column :formatter="numberFormatter">` 用：数值列统一显示口径。 */
export function numberFormatter(_row: unknown, _column: unknown, cellValue: unknown): string {
  const formatted = formatNumericText(cellValue)
  if (formatted !== null) {
    return formatted
  }
  return cellValue === null || cellValue === undefined || cellValue === '' ? '-' : String(cellValue)
}

export { Decimal }
