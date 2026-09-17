import { get, patch, post, put } from '@/api/http'
import { createCrudApi, type QueryParams } from '@/api/crud'
import type {
  CurrentUser,
  LoginAttempt,
  MenuNode,
  Notification,
  Paginated,
  PermissionGroup,
  PermissionRow,
  Role,
  SessionPayload,
  UserRow,
} from '@/types/models'

export const userApi = createCrudApi<UserRow>('/identity/users')
export const roleApi = createCrudApi<Role>('/identity/roles')

export interface UserCreatePayload {
  username: string
  password: string
  display_name?: string
  phone?: string | null
  email?: string
  company_id?: number | null
  department_id?: number | null
  is_staff?: boolean
  must_change_password?: boolean
  role_ids?: number[]
  remark?: string
}

export interface UserUpdatePayload {
  display_name?: string
  phone?: string | null
  email?: string
  company_id?: number | null
  department_id?: number | null
  is_staff?: boolean
  remark?: string
  expected_version?: number
}

/** 数据范围授权：按维度分别提交 ID 列表，后端按维度校验对象是否存在及公司归属。 */
export interface RoleScopePayload {
  data_scope_type: string
  company_ids?: number[]
  factory_ids?: number[]
  department_ids?: number[]
  warehouse_ids?: number[]
}

export interface RoleWritePayload {
  code: string
  name: string
  company_id?: number | null
  data_scope_type?: string
  sort_order?: number
  remark?: string
}

/** 身份与权限接口。写操作一律由后端做权限与数据范围校验。 */
export const identityApi = {
  csrf: () => get<{ detail: string }>('/identity/auth/csrf/'),
  login: (username: string, password: string) =>
    post<SessionPayload>('/identity/auth/login/', { username, password }),
  logout: () => post<{ detail: string }>('/identity/auth/logout/'),
  session: () => get<SessionPayload>('/identity/auth/session/'),
  changePassword: (oldPassword: string, newPassword: string) =>
    post<{ detail: string }>('/identity/auth/change-password/', {
      old_password: oldPassword,
      new_password: newPassword,
    }),
  profile: () => get<CurrentUser>('/identity/profile/'),
  updateProfile: (payload: { display_name?: string; phone?: string | null; email?: string }) =>
    put<CurrentUser>('/identity/profile/', payload),

  createUser: (payload: UserCreatePayload) => post<UserRow>('/identity/users/', payload),
  updateUser: (id: number, payload: UserUpdatePayload) =>
    patch<UserRow>(`/identity/users/${id}/`, payload),
  setUserActive: (id: number, isActive: boolean, reason = '') =>
    post<UserRow>(`/identity/users/${id}/set-active/`, { is_active: isActive, reason }),
  resetUserPassword: (id: number, newPassword: string, reason = "") =>
    post<{ detail: string }>(`/identity/users/${id}/reset-password/`, {
      new_password: newPassword,
      reason,
    }),
  unlockUser: (id: number) => post<UserRow>(`/identity/users/${id}/unlock/`),
  assignRoles: (id: number, roleIds: number[]) =>
    post<UserRow>(`/identity/users/${id}/roles/`, { role_ids: roleIds }),

  createRole: (payload: RoleWritePayload) => post<Role>('/identity/roles/', payload),
  updateRole: (id: number, payload: Partial<RoleWritePayload>) =>
    patch<Role>(`/identity/roles/${id}/`, payload),
  setRolePermissions: (id: number, codes: string[]) =>
    post<Role>(`/identity/roles/${id}/permissions/`, { permission_codes: codes }),
  setRoleMenus: (id: number, codes: string[]) =>
    post<Role>(`/identity/roles/${id}/menus/`, { menu_codes: codes }),
  setRoleScope: (id: number, payload: RoleScopePayload) =>
    post<Role>(`/identity/roles/${id}/scope/`, payload),

  permissions: (params: QueryParams = {}) =>
    get<Paginated<PermissionRow>>('/identity/permissions/', { params }),
  permissionGroups: () => get<PermissionGroup[]>('/identity/permissions/grouped/'),
  myMenus: () => get<MenuNode[]>('/identity/menus/mine/'),
  menuTree: () => get<MenuNode[]>('/identity/menus/tree/'),
  menuList: (params: QueryParams = {}) => get<Paginated<MenuNode>>('/identity/menus/', { params }),
  loginAttempts: (params: QueryParams = {}) =>
    get<Paginated<LoginAttempt>>('/identity/login-attempts/', { params }),

  notifications: (params: QueryParams = {}) =>
    get<Paginated<Notification>>('/identity/notifications/', { params }),
  unreadCount: () => get<{ count: number }>('/identity/notifications/unread-count/'),
  markNotificationRead: (id: number) =>
    post<{ detail: string }>(`/identity/notifications/${id}/read/`),
  markAllNotificationsRead: () => post<{ detail: string }>('/identity/notifications/read-all/'),

  scopeGrantsOf: (roleId: number) =>
    get<Role>(`/identity/roles/${roleId}/`).then((role) => role.scope_grants),
}