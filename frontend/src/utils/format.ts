import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

/**
 * 时间展示约定（任务书 5.1）：
 * 数据库与 API 一律 UTC，业务界面默认按 Asia/Shanghai 展示。
 * 后端返回的 ISO 字符串带时区信息，这里只做展示层转换。
 */
export const BUSINESS_TIME_ZONE = 'Asia/Shanghai'

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  if (!parsed.isValid()) {
    return '-'
  }
  return parsed.tz(BUSINESS_TIME_ZONE).format('YYYY-MM-DD HH:mm:ss')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  if (!parsed.isValid()) {
    return '-'
  }
  return parsed.tz(BUSINESS_TIME_ZONE).format('YYYY-MM-DD')
}

/** 相对时间，仅用于「最近动态」这类弱精度场景。 */
export function fromNow(value: string | null | undefined): string {
  if (!value) {
    return '-'
  }
  const target = dayjs(value)
  if (!target.isValid()) {
    return '-'
  }
  const diffSeconds = dayjs().diff(target, 'second')
  if (diffSeconds < 60) {
    return '刚刚'
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} 分钟前`
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)} 小时前`
  }
  if (diffSeconds < 86400 * 30) {
    return `${Math.floor(diffSeconds / 86400)} 天前`
  }
  return formatDate(value)
}

export function formatBytes(size: number | null | undefined): string {
  if (size === null || size === undefined) {
    return '-'
  }
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

/** 去掉空字符串与 null，避免把「未填写」当成字段清空提交给后端。 */
export function omitEmpty<T extends Record<string, unknown>>(payload: T): Partial<T> {
  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(payload)) {
    if (value === '' || value === null || value === undefined) {
      continue
    }
    result[key] = value
  }
  return result as Partial<T>
}