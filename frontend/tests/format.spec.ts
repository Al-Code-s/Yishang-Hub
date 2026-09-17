import { describe, expect, it } from 'vitest'

import { formatBytes, formatDate, formatDateTime, omitEmpty } from '@/utils/format'

/**
 * 时间与格式化契约。
 *
 * 后端一律返回 UTC（USE_TZ=True），业务界面按 Asia/Shanghai 展示。
 * 这里专门覆盖跨日边界，避免出现「昨天 16:00 显示成今天」这类问题。
 */
describe('时间格式化', () => {
  it('UTC 转 Asia/Shanghai 会正确跨日', () => {
    // 2026-09-17T16:00:00Z == 2026-09-18 00:00 Asia/Shanghai
    expect(formatDateTime('2026-09-17T16:00:00Z')).toBe('2026-09-18 00:00:00')
    expect(formatDate('2026-09-17T16:00:00Z')).toBe('2026-09-18')
  })

  it('同一天内的转换不改变日期', () => {
    expect(formatDateTime('2026-09-17T01:30:00Z')).toBe('2026-09-17 09:30:00')
  })

  it('空值与非法值返回占位符', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime(undefined)).toBe('-')
    expect(formatDateTime('not-a-date')).toBe('-')
    expect(formatDate('')).toBe('-')
  })

  it('文件大小按量级切换单位', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(3 * 1024 * 1024)).toBe('3.00 MB')
    expect(formatBytes(null)).toBe('-')
  })

  it('omitEmpty 去掉空串但不把 0 / false 当成空', () => {
    const payload = { a: '', b: null, c: 0, d: false, e: 'x' }
    expect(omitEmpty(payload)).toEqual({ c: 0, d: false, e: 'x' })
  })
})