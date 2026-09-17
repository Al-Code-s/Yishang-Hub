import { describe, expect, it } from 'vitest'

import {
  DECIMAL_PLACES,
  add,
  divide,
  formatAmount,
  formatDecimal,
  multiply,
  round,
  subtract,
  toApiString,
  toDecimal,
} from '@/utils/decimal'

/**
 * 金额与数量计算的契约测试。
 *
 * 背景（任务书 5.3）：禁止用 IEEE754 浮点数累计金额与库存。
 * 这些用例锁定的正是「用 float 会算错」的典型场景。
 */
describe('decimal 计算', () => {
  it('用十进制加法避免浮点误差', () => {
    // 0.1 + 0.2 用 float 得到 0.30000000000000004
    expect(add('0.1', '0.2').toString()).toBe('0.3')
  })

  it('累计大量金额不丢精度', () => {
    const values = Array.from({ length: 1000 }, () => '0.01')
    expect(add(...values).toFixed(2)).toBe('10.00')
  })

  it('乘除保持精度', () => {
    expect(multiply('19.99', '3').toFixed(2)).toBe('59.97')
    expect(divide('10', '3').toFixed(6)).toBe('3.333333')
  })

  it('减法支持负数结果', () => {
    expect(subtract('3', '5').toString()).toBe('-2')
  })

  it('除数为 0 时抛出而不是返回 Infinity', () => {
    expect(() => divide('1', '0')).toThrow('除数不能为 0')
  })

  it('非法输入抛出异常而不是静默当作 0', () => {
    expect(() => toDecimal('abc')).toThrow()
  })

  it('按四舍五入（HALF_UP）量化', () => {
    expect(round('1.005', 2).toFixed(2)).toBe('1.01')
    expect(round('1.004', 2).toFixed(2)).toBe('1.00')
    expect(round('2.675', 2).toFixed(2)).toBe('2.68')
  })

  it('toApiString 按数量精度补足 6 位小数', () => {
    expect(toApiString('12')).toBe('12.000000')
    expect(toApiString('1.5', DECIMAL_PLACES.quantity)).toBe('1.500000')
  })

  it('空值展示为 -，不当作 0', () => {
    expect(formatDecimal(null)).toBe('-')
    expect(formatDecimal('')).toBe('-')
    expect(formatDecimal(undefined)).toBe('-')
  })

  it('金额展示带千分位与固定小数位', () => {
    expect(formatAmount('1234567.891', 2)).toBe('1,234,567.89')
    expect(formatAmount('-1234.5', 2)).toBe('-1,234.50')
    expect(formatAmount('0', 2)).toBe('0.00')
    expect(formatAmount(null, 2)).toBe('-')
  })
})