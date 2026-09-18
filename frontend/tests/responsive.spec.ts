import fs from 'node:fs'
import path from 'node:path'

import { mount } from '@vue/test-utils'
import postcss from 'postcss'
import { describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'

import { NARROW_BREAKPOINT, useAutoCollapse, type AutoCollapse } from '@/composables/useAutoCollapse'

/**
 * 窄屏响应式契约测试。
 *
 * 背景：主布局原来不分屏幕宽度，侧边栏恒定 220px；在 1366 及以下的笔记本上表格被挤到不可读。
 * 本轮加了「窄屏自动折叠 + 表格横向滚动 + 统计卡改 flex 栅格」。
 *
 * 这里锁定三类容易悄悄回退的东西：
 * 1) JS 断点与 CSS 断点必须一致（两边各写一份常量，最容易改一边忘另一边）；
 * 2) 响应式规则本身存在（用 postcss 真实解析样式表，而不是字符串包含）；
 * 3) 视图不再用 <el-row> + 固定 :span 做统计卡栅格（那是窄屏被挤爆的根因）。
 *
 * 说明：真机观感仍需人工确认，本文件只能证明规则被正确声明和生效路径存在。
 * 数据来源与安全：纯静态检查，不访问网络、不写文件。
 */

const srcDir = path.resolve(process.cwd(), 'src')
const globalCss = fs.readFileSync(path.join(srcDir, 'styles', 'index.css'), 'utf-8')
const globalSheet = postcss.parse(globalCss)

interface RuleInfo {
  selector: string
  decls: Record<string, string>
}

/** 取某个 max-width 断点下的所有规则（含 `!important` 标记，便于断言覆盖方式） */
function rulesInsideMedia(maxWidth: number): RuleInfo[] {
  const found: RuleInfo[] = []
  globalSheet.walkAtRules('media', (atRule) => {
    if (!atRule.params.includes(`max-width: ${maxWidth}px`)) {
      return
    }
    atRule.walkRules((rule) => {
      const decls: Record<string, string> = {}
      rule.walkDecls((decl) => {
        decls[decl.prop] = decl.important ? `${decl.value} !important` : decl.value
      })
      found.push({ selector: rule.selector, decls })
    })
  })
  return found
}

/** 顶层规则（不含 @media 内部） */
const topLevelRules: RuleInfo[] = []
globalSheet.walkRules((rule) => {
  if (rule.parent?.type !== 'root') {
    return
  }
  const decls: Record<string, string> = {}
  rule.walkDecls((decl) => {
    decls[decl.prop] = decl.value
  })
  topLevelRules.push({ selector: rule.selector, decls })
})

function lookup(rules: RuleInfo[], selector: string): Record<string, string> {
  const merged: Record<string, string> = {}
  for (const rule of rules) {
    for (const part of rule.selector.split(',')) {
      if (part.trim() === selector) {
        Object.assign(merged, rule.decls)
      }
    }
  }
  return merged
}

function readSource(relativePath: string): string {
  return fs.readFileSync(path.join(srcDir, relativePath), 'utf-8')
}

function setViewportWidth(width: number): void {
  Object.defineProperty(window, 'innerWidth', { value: width, configurable: true, writable: true })
}

describe('窄屏响应式：断点与样式规则', () => {
  it('JS 断点常量与全局样式表里的 1200px 断点一致', () => {
    expect(NARROW_BREAKPOINT).toBe(1200)
    expect(globalCss).toContain(`max-width: ${NARROW_BREAKPOINT}px`)
    expect(rulesInsideMedia(NARROW_BREAKPOINT).length).toBeGreaterThan(0)
  })

  it('≤1440px 时表格改为容器内横向滚动，不再挤压列宽', () => {
    const rules = rulesInsideMedia(1440)
    expect(lookup(rules, '.ys-table-card')['overflow-x']).toBe('auto')
    expect(lookup(rules, '.ys-table-card .el-table')['min-width']).toBe('720px')
  })

  it('≤1200px 时收窄页面内边距与统计卡', () => {
    const rules = rulesInsideMedia(1200)
    expect(lookup(rules, '.ys-page')['padding']).toBe('12px')
    expect(lookup(rules, '.ys-panel')['padding']).toBe('12px')
    expect(lookup(rules, '.ys-table-card')['padding']).toBe('12px')
    expect(lookup(rules, '.ys-stat-card')['min-width']).toBe('140px')
  })

  it('≤992px 时标题竖排、统计卡整行、双列区块改单列', () => {
    const rules = rulesInsideMedia(992)
    expect(lookup(rules, '.ys-page__header')['flex-direction']).toBe('column')
    expect(lookup(rules, '.ys-stat-card')['flex']).toBe('1 1 100%')
    expect(lookup(rules, '.ys-grid-2')['grid-template-columns']).toBe('minmax(0, 1fr)')
  })

  it('≤992px 时弹窗与抽屉铺满，且用 !important 覆盖内联宽度', () => {
    const rules = rulesInsideMedia(992)
    expect(lookup(rules, '.el-dialog:not(.is-fullscreen)')['width']).toBe('92% !important')
    expect(lookup(rules, '.el-drawer:not(.is-fullscreen)')['width']).toBe('92% !important')
  })

  it('.ys-grid-2 默认是双列栅格', () => {
    expect(lookup(topLevelRules, '.ys-grid-2')['grid-template-columns']).toBe(
      'repeat(2, minmax(0, 1fr))',
    )
  })

  it('.ys-stat-card 默认是可伸缩的 flex 子项', () => {
    expect(lookup(topLevelRules, '.ys-stat-card')['flex']).toBe('1 1 168px')
  })
})

function mountCollapse(breakpoint: number = NARROW_BREAKPOINT) {
  const holder: { api: AutoCollapse | null } = { api: null }
  const wrapper = mount(
    defineComponent({
      setup() {
        const api = useAutoCollapse(breakpoint)
        holder.api = api
        return () => h('div', api.collapsed.value ? 'collapsed' : 'expanded')
      },
    }),
  )
  const api = holder.api
  if (api === null) {
    throw new Error('useAutoCollapse 未在 setup 中初始化')
  }
  return { api, unmount: () => wrapper.unmount() }
}

describe('窄屏响应式：侧边栏自动折叠', () => {
  it('宽屏默认展开', () => {
    setViewportWidth(1440)
    const { api, unmount } = mountCollapse()
    expect(api.narrow.value).toBe(false)
    expect(api.collapsed.value).toBe(false)
    unmount()
  })

  it('窄屏默认折叠，用户仍可手动展开', async () => {
    setViewportWidth(1000)
    const { api, unmount } = mountCollapse()
    expect(api.narrow.value).toBe(true)
    expect(api.collapsed.value).toBe(true)

    api.toggle()
    await nextTick()
    expect(api.collapsed.value).toBe(false)
    unmount()
  })

  it('视口变窄时自动折叠', async () => {
    setViewportWidth(1440)
    const { api, unmount } = mountCollapse()

    setViewportWidth(900)
    window.dispatchEvent(new Event('resize'))
    await nextTick()

    expect(api.narrow.value).toBe(true)
    expect(api.collapsed.value).toBe(true)
    unmount()
  })

  it('视口跨过断点后清除手动偏好，回到跟随视口', async () => {
    setViewportWidth(1440)
    const { api, unmount } = mountCollapse()

    api.toggle()
    await nextTick()
    expect(api.collapsed.value).toBe(true)

    setViewportWidth(900)
    window.dispatchEvent(new Event('resize'))
    await nextTick()
    expect(api.collapsed.value).toBe(true)

    setViewportWidth(1440)
    window.dispatchEvent(new Event('resize'))
    await nextTick()
    expect(api.narrow.value).toBe(false)
    expect(api.collapsed.value).toBe(false)
    unmount()
  })

  it('卸载后不再响应 resize（避免离开页面后仍改状态）', async () => {
    setViewportWidth(1440)
    const { api, unmount } = mountCollapse()
    unmount()

    setViewportWidth(900)
    window.dispatchEvent(new Event('resize'))
    await nextTick()
    expect(api.narrow.value).toBe(false)
  })
})

describe('窄屏响应式：视图不再用固定栅格', () => {
  it('OutboxList 统计卡改用 .ys-stat-cards，不再用 el-row + :span', () => {
    const source = readSource('views/integration/OutboxList.vue')
    expect(source).toContain('ys-stat-cards')
    expect(source).not.toContain('<el-row')
    expect(source).not.toContain(':span=')
  })

  it('ProgressView 统计卡与双列区块改用共享栅格类', () => {
    const source = readSource('views/system/ProgressView.vue')
    expect(source).toContain('ys-stat-cards')
    expect(source).toContain('ys-grid-2')
    expect(source).not.toContain('<el-row')
  })

  it('BasicLayout 使用自动折叠组合式函数，而非固定展开状态', () => {
    const source = readSource('layouts/BasicLayout.vue')
    expect(source).toContain('useAutoCollapse')
    expect(source).toContain('toggleCollapsed')
    expect(source).not.toContain('const collapsed = ref(false)')
  })
})
