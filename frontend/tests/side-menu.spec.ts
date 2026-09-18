import fs from 'node:fs'
import path from 'node:path'

import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import postcss from 'postcss'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import SideMenu from '@/components/SideMenu.vue'
import type { MenuNode } from '@/types/models'

/**
 * 侧边导航的层级样式契约测试。
 *
 * 需求：一级目录与二级页面在视觉上必须能区分开。
 * 区分靠 class（ys-menu-group--dN / ys-menu-node--dN）+ 样式表规则实现，
 * 因此这里锁定两件事：
 * 1) 渲染出的 DOM 按层级带上了不同的 class；
 * 2) 样式表真的为这两级写了不同的规则（用 postcss 真实解析，不是字符串猜测）。
 */

function node(partial: Partial<MenuNode> & { id: number; name: string }): MenuNode {
  return {
    code: `menu_${partial.id}`,
    parent_id: null,
    path: '',
    component: '',
    icon: '',
    menu_type: 'page',
    sort_order: 0,
    visible: true,
    permission_code: '',
    children: [],
    ...partial,
  }
}

const menus: MenuNode[] = [
  node({
    id: 1,
    name: '基础资料',
    menu_type: 'directory',
    path: '/masterdata',
    icon: 'Collection',
    children: [
      node({ id: 11, name: '物料档案', path: '/masterdata/materials' }),
      node({ id: 12, name: '款式档案', path: '/masterdata/styles' }),
    ],
  }),
  node({ id: 2, name: '工作台', path: '/workspace', icon: 'House' }),
]

async function mountMenu() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/', '/masterdata/materials', '/masterdata/styles', '/workspace'].map((path) => ({
      path,
      component: { template: '<div />' },
    })),
  })
  await router.push('/masterdata/materials')
  await router.isReady()
  const wrapper = mount(SideMenu, {
    props: { nodes: menus, collapsed: false, activePath: '/masterdata/materials' },
    global: { plugins: [ElementPlus, router] },
  })
  await nextTick()
  return wrapper
}

// vitest 的 cwd 是 frontend 目录（vitest.config.ts 所在位置）
const cssPath = path.resolve(process.cwd(), 'src/styles/index.css')
const cssText = fs.readFileSync(cssPath, 'utf-8')

/** 用真实 CSS 解析器读取样式表：语法错误会在这里直接抛错。 */
const sheet = postcss.parse(cssText)

interface MatchedRule {
  selector: string
  decls: Record<string, string>
}

function rulesMatching(fragment: string): MatchedRule[] {
  const found: MatchedRule[] = []
  sheet.walkRules((rule) => {
    const decls: Record<string, string> = {}
    rule.walkDecls((decl) => {
      // postcss 把 !important 放在 important 标记上，这里拼回值里，便于断言真实优先级
      decls[decl.prop] = decl.important ? `${decl.value} !important` : decl.value
    })
    if (rule.selector.includes(fragment)) {
      found.push({ selector: rule.selector, decls })
    }
  })
  return found
}

/**
 * 只取「作用在该元素自身」的规则：
 * 选择器必须以 fragment 结尾，排除 `.el-icon`、`::before` 这类子元素与伪元素规则，
 * 否则图标字号、圆点颜色会污染对条目排版的断言。
 */
function ownDecls(fragment: string): Record<string, string> {
  const merged: Record<string, string> = {}
  for (const rule of rulesMatching(fragment)) {
    for (const part of rule.selector.split(',')) {
      if (part.trim().endsWith(fragment)) {
        Object.assign(merged, rule.decls)
      }
    }
  }
  return merged
}

/** 多选择器合并（例如同一级同时存在「分组标题」与「叶子条目」两种形态）。 */
function mergedOwnDecls(...fragments: string[]): Record<string, string> {
  const merged: Record<string, string> = {}
  for (const fragment of fragments) {
    Object.assign(merged, ownDecls(fragment))
  }
  return merged
}
describe('侧边导航：一级目录与二级页面的层级区分', () => {
  it('一级目录渲染为分组（ys-menu-group--d0），二级页面渲染为条目（ys-menu-node--d1）', async () => {
    const wrapper = await mountMenu()

    expect(wrapper.text()).toContain('基础资料')
    expect(wrapper.text()).toContain('物料档案')

    const groups = wrapper.findAll('li.el-sub-menu')
    expect(groups.length).toBe(1)
    expect(groups[0].classes()).toContain('ys-menu-group--d0')

    const nodes = wrapper.findAll('li.el-menu-item')
    // 二级页面（展开的子菜单内）
    const level2 = nodes.filter((item) => item.classes().includes('ys-menu-node--d1'))
    expect(level2.length).toBe(2)
    // 根级叶子页面（工作台）按一级处理，不与二级混用同一 class
    const level1 = nodes.filter((item) => item.classes().includes('ys-menu-node--d0'))
    expect(level1.length).toBe(1)
    expect(level1[0].text()).toContain('工作台')
    expect(level2.some((item) => item.classes().includes('ys-menu-node--d0'))).toBe(false)
  })

  it('展开的子菜单外层容器带 el-menu--inline，二级条目位于其中', async () => {
    const wrapper = await mountMenu()
    const inline = wrapper.findAll('ul.el-menu--inline')
    expect(inline.length).toBe(1)
    expect(inline[0].findAll('li.el-menu-item').length).toBe(2)
  })

  it('一级与二级在样式表中有不同的排版规则（字号/字距/缩进）', () => {
    const level1 = mergedOwnDecls('ys-menu-group--d0 > .el-sub-menu__title', 'ys-menu-node--d0')
    const level2 = ownDecls('ys-menu-node--d1')

    expect(level1['font-size']).toBe('12px')
    expect(level1['font-weight']).toBe('600')
    expect(level1['letter-spacing']).toBeDefined()
    expect(level2['font-size']).toBe('13px')
    expect(level2['padding-left']).toBeDefined()
    expect(level1['font-size']).not.toBe(level2['font-size'])
  })

  it('只有二级条目带圆点标记，一级目录不带', () => {
    expect(rulesMatching('.ys-menu-node--d1::before').length).toBeGreaterThan(0)
    expect(rulesMatching('.ys-menu-group--d0::before').length).toBe(0)
    expect(rulesMatching('.ys-menu-node--d0::before').length).toBe(0)
  })

  it('二级选中态是高亮块，一级目录展开态是分组底色', () => {
    const active = ownDecls('ys-menu-node--d1.is-active')
    expect(active['background']).toContain('linear-gradient')
    expect(active['color']).toBe('#fff')

    const opened = mergedOwnDecls('ys-menu-group--d0.is-opened > .el-sub-menu__title')
    expect(opened['background']).toBeDefined()
  })

  it('展开的子菜单容器有独立底色，把同一目录下的页面框成一组', () => {
    const inline = ownDecls('el-menu--inline')
    expect(inline['background']).toBeDefined()
    expect(inline['border-radius']).toBeDefined()
  })

  it('折叠态有专门规则（图标居中、隐藏圆点与箭头）', () => {
    const collapsed = ownDecls('ys-layout__aside--collapsed .ys-layout__menu .el-menu-item')
    expect(collapsed['padding-left']).toBe('0 !important')
    expect(rulesMatching('ys-layout__aside--collapsed .ys-layout__menu .el-menu-item::before').length).toBeGreaterThan(0)
  })

  it('菜单行高由侧边栏变量统一收窄，不沿用 Element 默认 56px', () => {
    const sidebarMenu = ownDecls('ys-layout__menu .el-menu')
    expect(sidebarMenu['--el-menu-item-height']).toBe('40px')
    expect(sidebarMenu['--el-menu-sub-item-height']).toBe('36px')

    // 一级目录标题 40px、二级条目 36px，都由本项目的规则显式声明，
    // 保证 Element 变量被改动时不会静默走样
    expect(ownDecls('ys-menu-group--d0 > .el-sub-menu__title')['height']).toBe('40px')
    expect(ownDecls('ys-layout__menu .el-menu-item')['height']).toBe('36px')
  })

  it('当前页面所属的一级目录有定位提示（左侧竖条 + 提亮）', () => {
    expect(rulesMatching('.ys-menu-group--d0.is-active > .el-sub-menu__title').length).toBeGreaterThan(0)
    expect(rulesMatching('.ys-menu-group--d0.is-active > .el-sub-menu__title::after').length).toBeGreaterThan(0)

    const opened = ownDecls('ys-menu-group--d0.is-opened > .el-sub-menu__title')
    const active = ownDecls('ys-menu-group--d0.is-active > .el-sub-menu__title')
    expect(opened['color']).toBe('#fff')
    expect(active['color']).toBe('#fff')
  })

  it('样式表能被真实 CSS 解析器完整解析（语法合法性）', () => {
    const parsed: string[] = []
    sheet.walkRules((rule) => {
      parsed.push(rule.selector)
    })
    expect(parsed.length).toBeGreaterThan(50)
    expect(cssText).toContain('--el-color-primary: #1668dc')
  })
})