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

export function formatDecimal(value: Numeric, places: number = DECIMAL_PLACES.quantity): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  return round(value, places).toFixed(places)
}

/** 千分位展示，用于金额列表。 */
export function formatAmount(value: Numeric, places: number = 2): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const fixed = round(value, places).toFixed(places)
  const [integer, fraction] = fixed.split('.')
  const sign = integer.startsWith('-') ? '-' : ''
  const digits = sign ? integer.slice(1) : integer
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return fraction ? `${sign}${grouped}.${fraction}` : `${sign}${grouped}`
}

export { Decimal }