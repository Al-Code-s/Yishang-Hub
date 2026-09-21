import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import type { CurrentUser, SessionPayload } from '@/types/models'

/**
 * 登录态权限判定测试。
 *
 * 背景（真实缺陷）：后端对超级管理员返回的是通配符 `["*"]`
 * （`User.permission_codes()`，见 `backend/apps/identity/models.py`），
 * 而不是 173 条权限编码。前端如果只做 `permissions.includes(code)`，
 * 超级管理员就会被判成「没有任何操作权限」，页面上的新增 / 编辑 / 删除按钮
 * 会全部消失——用户看到的现象就是「超级管理员什么也干不了」。
 */

const admin: CurrentUser = {
  id: 1,
  username: 'admin',
  display_name: '系统管理员',
  phone: null,
  email: '',
  company_id: null,
  company_name: '',
  department_id: null,
  department_name: '',
  is_active: true,
  is_staff: true,
  must_change_password: false,
  failed_login_count: 0,
  locked_until: null,
  is_locked: false,
  last_login: null,
  last_login_ip: null,
  roles: [],
  version: 1,
  remark: '',
  date_joined: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function session(permissions: string[]): SessionPayload {
  return { user: admin, permissions, menus: [], unread_notifications: 0 }
}

describe('auth store 权限判定', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('超级管理员（通配符 *）对任意权限点都返回 true', () => {
    const auth = useAuthStore()
    auth.applySession(session(['*']))

    expect(auth.hasFullAccess).toBe(true)
    expect(auth.hasPermission('wms.warehouse.create')).toBe(true)
    expect(auth.hasPermission('identity.role.create')).toBe(true)
    expect(auth.hasAnyPermission(['sales.order.approve', 'wms.document.post'])).toBe(true)
  })

  it('普通角色只放行自己拥有的权限点', () => {
    const auth = useAuthStore()
    auth.applySession(session(['wms.warehouse.view', 'wms.warehouse.create']))

    expect(auth.hasFullAccess).toBe(false)
    expect(auth.hasPermission('wms.warehouse.create')).toBe(true)
    expect(auth.hasPermission('wms.warehouse.delete')).toBe(false)
    expect(auth.hasAnyPermission(['wms.warehouse.delete', 'wms.warehouse.view'])).toBe(true)
    expect(auth.hasAnyPermission(['wms.warehouse.delete', 'sales.order.view'])).toBe(false)
  })

  it('无任何权限时不放行，也不会把空编码当成受限', () => {
    const auth = useAuthStore()
    auth.applySession(session([]))

    expect(auth.hasFullAccess).toBe(false)
    expect(auth.hasPermission('wms.warehouse.view')).toBe(false)
    expect(auth.hasPermission(undefined)).toBe(true)
    expect(auth.hasAnyPermission([])).toBe(true)
  })

  it('退出登录后权限清空', () => {
    const auth = useAuthStore()
    auth.applySession(session(['*']))
    auth.clear()

    expect(auth.hasFullAccess).toBe(false)
    expect(auth.hasPermission('wms.warehouse.view')).toBe(false)
  })
})