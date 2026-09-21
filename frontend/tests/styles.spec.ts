import fs from 'node:fs'
import path from 'node:path'

import postcss from 'postcss'
import { describe, expect, it } from 'vitest'

/**
 * 共享样式类的契约测试。
 *
 * 背景：多个视图曾经各自定义 `.ys-section-title`（4 份）、统计标签/数值（3 套）、
 * 白色面板（3 份），导致同一个界面元素在不同页面观感不一致。
 * 现在这些统一下沉到 `src/styles/index.css`，本测试锁定：
 * 1) 每个共享类在全局样式里确实有定义；
 * 2) 任何 .vue 的 scoped 样式不得再重新定义共享类（防止再次分叉）；
 * 3) 曾经手写面板/统计块的页面确实改用了共享类。
 */

const srcDir = path.resolve(process.cwd(), 'src')
const globalCssPath = path.join(srcDir, 'styles', 'index.css')
const globalCss = fs.readFileSync(globalCssPath, 'utf-8')
const globalSheet = postcss.parse(globalCss)

/** 共享类清单（定义处唯一：src/styles/index.css） */
const SHARED_CLASSES = [
  'ys-page',
  'ys-page__title',
  'ys-page__description',
  'ys-page__header-actions',
  'ys-filter-bar',
  'ys-toolbar',
  'ys-table-card',
  'ys-panel',
  'ys-panel--flush',
  'ys-section-title',
  'ys-stat-cards',
  'ys-stat-card',
  'ys-stat__label',
  'ys-stat__value',
  'ys-stat__hint',
  'ys-code-block',
  'ys-pagination',
  'ys-ml-4',
  'ys-muted',
  'ys-mono',
  'ys-definition',
  'ys-form-error',
]

function listVueFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      listVueFiles(full, acc)
    } else if (entry.name.endsWith('.vue')) {
      acc.push(full)
    }
  }
  return acc
}

interface RuleInfo {
  file: string
  selector: string
  decls: Record<string, string>
}

function scopedRules(): RuleInfo[] {
  const rules: RuleInfo[] = []
  for (const file of listVueFiles(srcDir)) {
    const source = fs.readFileSync(file, 'utf-8')
    const match = /<style[^>]*>([\s\S]*?)<\/style>/.exec(source)
    if (!match) {
      continue
    }
    const sheet = postcss.parse(match[1])
    sheet.walkRules((rule) => {
      const decls: Record<string, string> = {}
      rule.walkDecls((decl) => {
        decls[decl.prop] = decl.value
      })
      rules.push({ file: path.relative(srcDir, file), selector: rule.selector, decls })
    })
  }
  return rules
}

function globalDecls(fragment: string): Record<string, string> {
  const merged: Record<string, string> = {}
  globalSheet.walkRules((rule) => {
    for (const part of rule.selector.split(',')) {
      if (part.trim().endsWith(fragment)) {
        rule.walkDecls((decl) => {
          merged[decl.prop] = decl.value
        })
      }
    }
  })
  return merged
}
describe('共享样式类：唯一定义处 + 实际使用', () => {
  const rules = scopedRules()

  it('src 下存在带 scoped 样式的组件', () => {
    expect(rules.length).toBeGreaterThan(0)
  })

  it.each(SHARED_CLASSES)('共享类 %s 在全局样式中有定义', (className) => {
    expect(globalCss).toContain(`.${className}`)
  })

  it('任何 .vue 的 scoped 样式都不得重新定义共享类', () => {
    const offenders: string[] = []
    for (const rule of rules) {
      const tokens = [...rule.selector.matchAll(/\.([A-Za-z0-9_-]+)/g)].map((m) => m[1])
      for (const token of tokens) {
        if (SHARED_CLASSES.includes(token)) {
          offenders.push(`${rule.file}: ${rule.selector}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('面板类使用同一份视觉令牌（.ys-panel 与 .ys-table-card 一致）', () => {
    const panel = globalDecls('.ys-panel')
    const tableCard = globalDecls('.ys-table-card')
    expect(panel['border-radius']).toBe('var(--ys-radius)')
    expect(tableCard['border-radius']).toBe('var(--ys-radius)')
    expect(tableCard['box-shadow']).toBe(panel['box-shadow'])
    expect(tableCard['border']).toBe(panel['border'])
  })

  it('区块标题带主色竖条，统计数值使用品牌深蓝', () => {
    expect(globalSheet.toString()).toContain('.ys-section-title::before')
    expect(globalDecls('.ys-section-title')['font-weight']).toBe('600')
    expect(globalDecls('.ys-stat__value')['color']).toBe('var(--ys-navy-900)')
  })

  it.each([
    ['views/integration/OutboxList.vue', 'ys-panel'],
    ['views/system/PermissionList.vue', 'ys-panel'],
    ['views/system/ProgressView.vue', 'ys-stat__value'],
    ['views/workspace/Index.vue', 'ys-stat-cards'],
    ['views/planning/BomList.vue', 'ys-code-block'],
  ])('%s 已改用共享类 %s，不再手写同款样式', (file, className) => {
    const source = fs.readFileSync(path.join(srcDir, file), 'utf-8')
    expect(source).toContain(className)
    const localStyle = /<style[^>]*>([\s\S]*?)<\/style>/.exec(source)
    expect(localStyle?.[1] ?? '').not.toContain(`.${className} {`)
  })
})