import fs from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

/**
 * 界面文案契约测试：可见文字用「使用者视角」，不出现开发视角的内部标识。
 *
 * 背景：界面曾把内部标识直接显示给业务人员——审计日志的「对象类型」显示
 * `masterdata.Material`，内部协同页显示 `sales.SalesOrder`，个别列标题叫「对象 ID」
 * 「业务 ID」「审批实例」。本轮统一改为中文展示名与业务叫法，展示名一律由后端算好
 * （见 `backend/tests/test_audit_display.py`），前端不自己维护翻译表。
 *
 * 这里只做静态源码检查，锁定最容易改回去的几种写法；真实观感仍需人工确认。
 */

const projectRoot = process.cwd()
const scanDirs = [
  path.join(projectRoot, 'src', 'views'),
  path.join(projectRoot, 'src', 'components'),
]

function vueSources(): { file: string; text: string }[] {
  const files: string[] = []
  for (const dir of scanDirs) {
    for (const name of fs.readdirSync(dir, { recursive: true, encoding: 'utf-8' })) {
      if (name.endsWith('.vue')) {
        files.push(path.join(dir, name))
      }
    }
  }
  return files.map((file) => ({
    file: path.relative(projectRoot, file).split(path.sep).join('/'),
    text: fs.readFileSync(file, 'utf-8'),
  }))
}

const sources = vueSources()

function find(fileSuffix: string): { file: string; text: string } {
  return sources.find((item) => item.file.endsWith(fileSuffix)) as { file: string; text: string }
}

describe('界面文案：不把内部标识显示给业务人员', () => {
  it('表格与详情不用内部标识当列标题', () => {
    const forbidden = ['label="对象 ID"', 'label="业务 ID"', 'label="事件 ID"', 'label="审批实例"']
    const offenders: string[] = []
    for (const { file, text } of sources) {
      for (const token of forbidden) {
        if (text.includes(token)) {
          offenders.push(`${file} 仍在使用 ${token}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })

  it('内部协同页展示后端算好的中文业务对象名，而不是 sales.SalesOrder', () => {
    const { text } = find('views/integration/OutboxList.vue')
    expect(text).toContain('aggregate_type_display')
    expect(text).not.toContain('prop="aggregate_type"')
  })

  it('审计页展示后端算好的中文对象类型与变更摘要', () => {
    const { text } = find('views/system/AuditLogList.vue')
    expect(text).toContain('object_type_display')
    expect(text).toContain('changes_display')
  })

  it('工作台的最近业务动态用中文句子，不渲染原始 JSON', () => {
    const { text } = find('views/workspace/Index.vue')
    expect(text).toContain('object_type_display')
    expect(text).toContain('action_display')
    expect(text).not.toContain('changes_display')
  })
})
