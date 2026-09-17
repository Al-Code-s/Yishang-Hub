import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import type { CurrentUser, MenuNode, SessionPayload } from '@/types/models'

/**
 * 登录态、权限编码与菜单。
 *
 * 安全约定（任务书 6.4）：前端权限只用于「显示与引导」，
 * 任何隐藏按钮都不能替代后端校验，越权请求由后端拒绝。
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const permissions = ref<string[]>([])
  const menus = ref<MenuNode[]>([])
  const unreadNotifications = ref(0)
  const loaded = ref(false)
  const loading = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')
  const roleNames = computed(() => {
    const roles = user.value?.roles
    if (!Array.isArray(roles)) {
      return [] as string[]
    }
    return roles.map((role) => role.name)
  })
  const mustChangePassword = computed(() => user.value?.must_change_password === true)

  /** 是否拥有某个操作权限。超级管理员由后端直接放行，前端按 is_staff + 全权限处理。 */
  function hasPermission(code: string | undefined | null): boolean {
    if (!code) {
      return true
    }
    return permissions.value.includes(code)
  }

  function hasAnyPermission(codes: string[]): boolean {
    if (codes.length === 0) {
      return true
    }
    return codes.some((code) => permissions.value.includes(code))
  }

  function applySession(payload: SessionPayload): void {
    user.value = payload.user
    permissions.value = [...payload.permissions]
    menus.value = payload.menus
    unreadNotifications.value = payload.unread_notifications
    loaded.value = true
  }

  function clear(): void {
    user.value = null
    permissions.value = []
    menus.value = []
    unreadNotifications.value = 0
    loaded.value = false
  }

  async function fetchSession(): Promise<boolean> {
    loading.value = true
    try {
      applySession(await identityApi.session())
      return true
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        clear()
        return false
      }
      throw error
    } finally {
      loading.value = false
    }
  }

  async function login(username: string, password: string): Promise<void> {
    applySession(await identityApi.login(username, password))
  }

  async function logout(): Promise<void> {
    try {
      await identityApi.logout()
    } finally {
      clear()
    }
  }

  async function refreshUnreadCount(): Promise<void> {
    const result = await identityApi.unreadCount()
    unreadNotifications.value = result.count
  }

  return {
    user,
    permissions,
    menus,
    unreadNotifications,
    loaded,
    loading,
    isAuthenticated,
    displayName,
    roleNames,
    mustChangePassword,
    hasPermission,
    hasAnyPermission,
    applySession,
    clear,
    fetchSession,
    login,
    logout,
    refreshUnreadCount,
  }
})