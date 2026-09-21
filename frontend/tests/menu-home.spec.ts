import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import { menuTrail, resolveHomePath, router } from '@/router'
import { useAuthStore } from '@/stores/auth'
import type { CurrentUser, MenuNode } from '@/types/models'

/**
 * 登录后的落地页与面包屑契约测试。
 *
 * 真实缺陷（本轮修复）：登录成功后前端 `router.replace('/')`，而 `/` 只是布局外壳、
 * 本身**没有页面组件**。于是登录后停在 `/`：侧边栏、顶部、标签页都在（面包屑当时还
 * 写死「工作台」），内容区却是空的，用户看到的正是「工作台是空的」。
 *
 * 修复分两处，这里各锁一条：
 * 1. 路由守卫把 `/` 解析成「该账号菜单里的第一个页面」（通常是工作台），
 *    因此没有工作台权限的账号也会落到自己的第一个可用页面；
 * 2. 面包屑按菜单层级生成，不再无条件显示「工作台」。
 */

// jsdom 未实现 window.scrollTo，而 router 配置了 scrollBehavior：不桩掉会打印无意义的报错
vi.stubGlobal('scrollTo', () => undefined)

function menu(
  partial: Partial<MenuNode> & Pick<MenuNode, 'code' | 'name' | 'path' | 'menu_type'>,
): MenuNode {
  return {
    id: 1,
    parent_id: null,
    component: '',
    icon: '',
    sort_order: 0,
    visible: true,
    permission_code: '',
    children: [],
    ...partial,
  }
}

const workspace = menu({
  id: 1,
  code: 'workspace',
  name: '工作台',
  path: '/workspace',
  menu_type: 'page',
  component: 'views/workspace/Index.vue',
})

const crm = menu({
  id: 2,
  code: 'crm',
  name: '客户管理',
  path: '/crm',
  menu_type: 'directory',
  children: [
    menu({
      id: 3,
      code: 'crm.customer',
      name: '客户档案',
      path: '/crm/customers',
      menu_type: 'page',
      parent_id: 2,
      component: 'views/crm/CustomerList.vue',
    }),
  ],
})

describe('落地页解析（resolveHomePath）', () => {
  it('菜单里第一个页面就是落地页', () => {
    expect(resolveHomePath([workspace, crm])).toBe('/workspace')
  })

  it('目录本身不是页面，落地页取目录下的第一个页面', () => {
    expect(resolveHomePath([crm])).toBe('/crm/customers')
  })

  it('没有可用页面时返回空串，由调用方保留原地址', () => {
    expect(resolveHomePath([])).toBe('')
  })
})

describe('面包屑层级（menuTrail）', () => {
  it('二级页面返回目录 + 页面的链路', () => {
    expect(menuTrail([workspace, crm], '/crm/customers').map((node) => node.name)).toEqual([
      '客户管理',
      '客户档案',
    ])
  })

  it('一级页面只返回自身', () => {
    expect(menuTrail([workspace, crm], '/workspace').map((node) => node.name)).toEqual(['工作台'])
  })

  it('不在菜单里的地址返回空链路，避免显示错误的层级', () => {
    expect(menuTrail([workspace, crm], '/system/progress')).toEqual([])
  })
})

describe('登录后访问根路径', () => {
  it('自动跳到账号菜单里的第一个页面，而不是停在空白布局', async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.loaded = true
    auth.user = { id: 1, username: 'tester', display_name: '测试用户' } as unknown as CurrentUser
    auth.menus = [workspace, crm]

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/workspace')
  })
})
