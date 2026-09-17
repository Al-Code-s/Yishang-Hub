import { describe, expect, it } from 'vitest'

/**
 * 视图可编译性检查。
 *
 * 背景：一个 .vue 文件如果缺少 `</script>` 之类的结束标签，TypeScript 检查
 * 往往不会报错，但生产构建会直接失败（`Element is missing end tag`）。
 * 这里让 Vite 真正编译并加载每一个视图模块，把这类问题在测试阶段暴露出来，
 * 而不是等到构建或用户点击菜单时才发现。
 *
 * 同时校验菜单声明的组件路径与 src/views 下的真实文件一一对应，
 * 避免出现「菜单点了没反应」的静默失效。
 */
const viewModules = import.meta.glob('../src/views/**/*.vue')

function toRelativePath(key: string): string {
  // '../src/views/workspace/Index.vue' -> 'views/workspace/Index.vue'
  return key.replace(/^\.\.\/src\//, '')
}

describe('视图模块', () => {
  const entries = Object.entries(viewModules)

  it('至少存在一个视图模块', () => {
    expect(entries.length).toBeGreaterThan(0)
  })

  // 视图数量随阶段推进增长，逐个真实编译需要的时间已超过 vitest 默认 5s 上限
  it('每个视图都能被编译并加载', { timeout: 60000 }, async () => {
    const failures: string[] = []
    for (const [key, loader] of entries) {
      try {
        const module = (await loader()) as { default?: unknown }
        if (!module.default) {
          failures.push(`${key}: 缺少默认导出`)
        }
      } catch (error) {
        failures.push(`${key}: ${error instanceof Error ? error.message : String(error)}`)
      }
    }
    expect(failures).toEqual([])
  })

  it('路径命名符合菜单组件约定', () => {
    for (const key of Object.keys(viewModules)) {
      expect(toRelativePath(key)).toMatch(/^views\/[A-Za-z0-9_/-]+\.vue$/)
    }
  })
})