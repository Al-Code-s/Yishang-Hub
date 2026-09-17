import { del, get, patch, post, type ApiError } from '@/api/http'
import type { Paginated } from '@/types/models'

/** 通用查询参数。后端对 page_size 有上限（默认 200），超过会被拒绝。 */
export interface QueryParams {
  page?: number
  page_size?: number
  search?: string
  ordering?: string
  [key: string]: unknown
}

export interface CrudApi<T, TWrite> {
  path: string
  list: (params?: QueryParams) => Promise<Paginated<T>>
  retrieve: (id: number) => Promise<T>
  create: (payload: TWrite) => Promise<T>
  update: (id: number, payload: Partial<TWrite>) => Promise<T>
  setActive: (id: number, isActive: boolean, reason?: string) => Promise<T>
  remove: (id: number) => Promise<void>
  action: <R>(id: number, action: string, payload?: unknown) => Promise<R>
}

/**
 * 按后端 REST 约定生成 CRUD 客户端。
 *
 * 后端所有 ViewSet 都提供 `set-active` 动作；是否提供 DELETE 由各模块决定，
 * 界面在启用/停用与删除之间必须按模块区分，不能一律给删除按钮。
 */
export function createCrudApi<T extends { id: number }, TWrite = Partial<T>>(
  path: string,
): CrudApi<T, TWrite> {
  return {
    path,
    list: (params: QueryParams = {}) => get<Paginated<T>>(`${path}/`, { params }),
    retrieve: (id: number) => get<T>(`${path}/${id}/`),
    create: (payload: TWrite) => post<T>(`${path}/`, payload),
    update: (id: number, payload: Partial<TWrite>) => patch<T>(`${path}/${id}/`, payload),
    setActive: (id: number, isActive: boolean, reason = '') =>
      post<T>(`${path}/${id}/set-active/`, { is_active: isActive, reason }),
    remove: (id: number) => del(`${path}/${id}/`),
    action: <R>(id: number, action: string, payload: unknown = {}) =>
      post<R>(`${path}/${id}/${action}/`, payload),
  }
}

export type { ApiError }