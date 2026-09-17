import { describe, expect, it } from 'vitest'

import { ApiError } from '@/api/http'

/**
 * 统一错误结构。
 *
 * 后端错误格式为 { code, message, details, request_id }；
 * 前端必须保留 code 与 request_id 以便排查，不能只留一句「请求失败」。
 */
describe('ApiError', () => {
  it('保留 code / requestId / 字段级错误', () => {
    const error = new ApiError(400, {
      code: 'VALIDATION_FAILED',
      message: '参数校验不通过',
      details: { code: ['该字段是必填项。'], name: '名称重复' },
      request_id: 'req-123',
    })

    expect(error.status).toBe(400)
    expect(error.code).toBe('VALIDATION_FAILED')
    expect(error.message).toBe('参数校验不通过')
    expect(error.requestId).toBe('req-123')
    expect(error.fieldErrors).toEqual({ code: ['该字段是必填项。'], name: ['名称重复'] })
    expect(error.fieldErrorMessage).toContain('code：该字段是必填项。')
  })

  it('缺字段时有兜底值', () => {
    const error = new ApiError(500, {
      code: '',
      message: '',
      details: {},
      request_id: '',
    })
    expect(error.code).toBe('ERROR')
    expect(error.message).toBe('请求失败')
    expect(error.fieldErrors).toEqual({})
    expect(error.fieldErrorMessage).toBe('')
  })
})