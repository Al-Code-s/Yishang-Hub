import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import type { MenuNode } from '@/types/models'

/**
 * 路由表按菜单权限动态注册。
 *
 * 「未实施的模块不展示伪可用页面」（任务书 8.2）：这里只注册后端菜单表里
 * 真实存在的页面组件，未实现的模块不会出现在导航中，也不会产生可访问路由。
 */

const viewModules = import.meta.glob('../views/**/*.vue')

export function resolveView(component: string): (() => Promise<unknown>) | undefined {
  if (!component) {
    return undefined
  }
  const normalized = component.replace(/^\/+/, '')
  const key = `../${normalized}`
  return viewModules[key] as (() => Promise<unknown>) | undefined
}

function collectPages(nodes: MenuNode[], result: MenuNode[] = []): MenuNode[] {
  for (const node of nodes) {
    if (node.menu_type === 'page') {
      result.push(node)
    }
    if (node.children && node.children.length > 0) {
      collectPages(node.children, result)
    }
  }
  return result
}

const staticRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/403',
    name: 'forbidden',
    component: () => import('@/views/ForbiddenView.vue'),
    meta: { title: '没有访问权限' },
  },
]

/** 布局路由在会话恢复后注册，其子路由来自当前用户的菜单。 */
const layoutRoute: RouteRecordRaw = {
  path: '/',
  name: 'root',
  component: () => import('@/layouts/BasicLayout.vue'),
  children: [],
}

const notFoundRoute: RouteRecordRaw = {
  path: '/:pathMatch(.*)*',
  name: 'not-found',
  component: () => import('@/views/NotFoundView.vue'),
  meta: { title: '页面不存在' },
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [...staticRoutes, layoutRoute, notFoundRoute],
  scrollBehavior: () => ({ top: 0 }),
})

let registeredSignature = ''
let removeDynamicRoutes: (() => void) | null = null

/** 清空动态路由（退出登录、切换账号时必须调用，避免权限串号）。 */
export function resetDynamicRoutes(): void {
  if (removeDynamicRoutes) {
    removeDynamicRoutes()
    removeDynamicRoutes = null
  }
  registeredSignature = ''
}

export function registerMenuRoutes(menus: MenuNode[]): boolean {
  const pages = collectPages(menus)
  const signature = pages
    .map((page) => `${page.path}|${page.component}|${page.name}`)
    .sort()
    .join(';')

  if (signature === registeredSignature) {
    return false
  }

  if (removeDynamicRoutes) {
    removeDynamicRoutes()
    removeDynamicRoutes = null
  }

  const children: RouteRecordRaw[] = []
  for (const page of pages) {
    const loader = resolveView(page.component)
    if (!loader) {
      // 菜单声明的组件缺失属于配置错误：不注册空路由，避免出现点进去就白屏的菜单
      console.warn(`[router] 菜单 ${page.code} 的组件未找到：${page.component}`)
      continue
    }
    const record = {
      path: page.path.replace(/^\//, ''),
      name: `menu-${page.code}`,
      component: loader as RouteRecordRaw['component'],
      meta: {
        title: page.name,
        icon: page.icon,
        menuCode: page.code,
        permissionCode: page.permission_code,
      },
    }
    children.push(record as RouteRecordRaw)
  }

  // 逐条注册到布局路由下：这样布局的 router-view 直接渲染页面组件，
  // 不额外插入空壳父路由（否则会出现「布局正常但内容空白」）。
  const removers = children.map((child) => {
    const remove = router.addRoute('root', child)
    return () => {
      try {
        remove()
      } catch {
        // 路由已被移除时忽略
      }
    }
  })
  removeDynamicRoutes = () => {
    for (const remove of removers) {
      remove()
    }
  }
  registeredSignature = signature
  return true
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public === true) {
    return true
  }

  if (!auth.loaded) {
    await auth.fetchSession()
  }

  if (!auth.isAuthenticated) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }

  const changed = registerMenuRoutes(auth.menus)
  if (changed) {
    // 路由表刚变化，重新解析目标地址
    return { ...to, replace: true }
  }

  if (to.name === 'login') {
    return { path: '/' }
  }
  return true
})