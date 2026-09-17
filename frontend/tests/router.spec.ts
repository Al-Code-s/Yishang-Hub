import { describe, expect, it } from 'vitest'

import { resolveView } from '@/router'

import declaredMenus from './fixtures/menu-components.json'

interface DeclaredMenu {
  code: string
  path: string
  component: string
  menu_type: string
  permission_code: string
}

/**
 * 菜单与前端组件的契约测试。
 *
 * `tests/fixtures/menu-components.json` 由后端
 * `apps/identity/permissions_registry.py` 导出（一次性生成，随注册表更新）。
 * 前端路由按后端菜单的 component 字段动态加载组件：路径对不上时不会注册路由，
 * 用户会看到「菜单点了没反应」。这里把这个隐性故障变成显式的测试失败。
 */
describe('菜单组件解析', () => {
  const pages = (declaredMenus as DeclaredMenu[]).filter((menu) => menu.menu_type === 'page')

  it('后端声明的页面菜单至少有一个', () => {
    expect(pages.length).toBeGreaterThan(0)
  })

  it.each(pages.map((menu) => [menu.code, menu.component] as const))(
    '菜单 %s 的组件 %s 能被前端解析',
    (_code, component) => {
      expect(resolveView(component)).toBeTypeOf('function')
    },
  )

  it('目录菜单不带组件，不应被解析成页面', () => {
    const directories = (declaredMenus as DeclaredMenu[]).filter(
      (menu) => menu.menu_type === 'directory',
    )
    expect(directories.length).toBeGreaterThan(0)
    for (const directory of directories) {
      expect(directory.component).toBe('Layout')
    }
  })

  it('容忍前导斜杠', () => {
    expect(resolveView('/views/workspace/Index.vue')).toBeTypeOf('function')
  })

  it('未知组件返回 undefined，而不是抛错或返回空壳', () => {
    expect(resolveView('views/not-exist/Nowhere.vue')).toBeUndefined()
    expect(resolveView('')).toBeUndefined()
  })
})