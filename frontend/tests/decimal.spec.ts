import { describe, expect, it } from 'vitest'

import {
  DECIMAL_PLACES,
  add,
  divide,
  formatAmount,
  formatDecimal,
  formatNumber,
  formatNumericText,
  multiply,
  numberFormatter,
  round,
  subtract,
  toApiString,
  toDecimal,
  toEditableText,
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

/**
 * 界面显示口径：业务界面上的数值统一「小数点后 2 位」。
 *
 * 注意区分两件事：
 * * **显示**精度 2 位（本组用例）；
 * * **存储 / 接口**精度仍是 6 位（`toApiString` 的用例），显示口径不回写数据。
 */
describe('数值显示口径（2 位小数）', () => {
  it('把 6 位小数的接口值显示成 2 位', () => {
    expect(formatNumber('12.000000')).toBe('12.00')
    expect(formatNumber('1234.567800')).toBe('1,234.57')
    expect(formatNumber('-1234.500000')).toBe('-1,234.50')
    expect(formatNumber('0.000000')).toBe('0.00')
  })

  it('四舍五入遵循 HALF_UP', () => {
    expect(formatNumber('1.005')).toBe('1.01')
    expect(formatNumber('1.004')).toBe('1.00')
  })

  it('非零值不会被显示成 0', () => {
    // BOM 用量 0.004、极小单价 0.0004：显示成 0.00 就是把「有」说成「没有」
    expect(formatNumber('0.004000')).toBe('0.004')
    expect(formatNumber('0.0004')).toBe('0.0004')
    expect(formatNumber('-0.0000001')).toBe('0.00')
  })

  it('会进位的值仍按 2 位显示（保护逻辑不越权保留精度）', () => {
    expect(formatNumber('0.055')).toBe('0.06')
    expect(formatNumber('0.994')).toBe('0.99')
    expect(formatNumber('0.995')).toBe('1.00')
  })

  it('整数计数列（places = 0）不出现小数点', () => {
    expect(formatNumber('12', 0)).toBe('12')
    expect(formatNumber('0', 0)).toBe('0')
    expect(formatNumber('1234', 0)).toBe('1,234')
  })

  it('空值显示 -，不当作 0', () => {
    expect(formatNumber(null)).toBe('-')
    expect(formatNumber(undefined)).toBe('-')
    expect(formatNumber('')).toBe('-')
  })

  it('显示口径不影响提交给后端的精度', () => {
    expect(toApiString(formatNumber('12.5'))).toBe('12.500000')
  })
})

describe('编辑表单回填（toEditableText）', () => {
  it('去掉接口值里无意义的末尾 0，且不加千分位', () => {
    expect(toEditableText('12.000000')).toBe('12')
    expect(toEditableText('-1234.500000')).toBe('-1234.5')
    expect(toEditableText('1234.567800')).toBe('1234.5678')
  })

  it('不回写四舍五入结果，避免显示口径改写用户数据', () => {
    // 若这里返回 0.06，用户「打开编辑再保存」就会把 0.055 改成 0.06
    expect(toEditableText('0.055')).toBe('0.055')
    expect(toEditableText('0.004000')).toBe('0.004')
  })

  it('空值返回空字符串，便于输入框留空', () => {
    expect(toEditableText(null)).toBe('')
    expect(toEditableText(undefined)).toBe('')
    expect(toEditableText('')).toBe('')
  })
})

describe('formatNumericText 只处理数值文本', () => {
  it('十进制字符串按显示口径格式化', () => {
    expect(formatNumericText('12.000000')).toBe('12.00')
    expect(formatNumericText('-0.500000')).toBe('-0.50')
    expect(formatNumericText(12.5)).toBe('12.50')
  })

  it('整数文本与编码不被误格式化（会被加上千分位）', () => {
    expect(formatNumericText('13800138000')).toBeNull()
    expect(formatNumericText('913301001234567890')).toBeNull()
    expect(formatNumericText('M-001')).toBeNull()
    expect(formatNumericText(12)).toBeNull()
    expect(formatNumericText('2026-09-20')).toBeNull()
    expect(formatNumericText(null)).toBeNull()
  })

  it('numberFormatter 对非数值原样返回，空值显示 -', () => {
    expect(numberFormatter(null, null, '12.000000')).toBe('12.00')
    expect(numberFormatter(null, null, 'E1001')).toBe('E1001')
    expect(numberFormatter(null, null, null)).toBe('-')
  })
})
