import fs from 'node:fs'
import path from 'node:path'

import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import postcss from 'postcss'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { identityApi } from '@/api/identity'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'

/**
 * 登录页契约测试。
 *
 * 本轮把登录页从「居中一张小卡片」改成「左侧品牌区 + 右侧登录卡」的商用布局，
 * 并把登录页样式从全局样式表移入组件（原先 `.ys-login*` 定义在
 * `src/styles/index.css`，改样式要跳到另一个文件）。
 *
 * 左栏要点是给业务用户看的，必须用业务价值描述，不能出现开发/实现视角的术语
 * （权限分层、前后端职责、数据表字段名等）——这类回归肉眼容易漏，所以写进测试。
 *
 * 这里锁定三类容易悄悄回退的东西：
 * 1) 关键元素仍渲染（品牌、标题、账号/密码、登录按钮、安全提示）；
 * 2) 提交流程仍是「先取 CSRF → 再登录 → 跳转」；
 * 3) 样式单一定义处 + 窄屏/动效偏好规则确实存在（用 postcss 真实解析样式块）。
 *
 * **未覆盖（jsdom 限制，不得视为通过）**：表单必填校验。
 * Element Plus 的 `el-form-item` 在 jsdom 下不会注册进 `el-form` 的 fields，
 * `validate()` 走 `fields.length === 0 → true` 分支并直接放行。
 * 已用一个最小复现确认这是环境限制而非本页缺陷（真实浏览器不受影响）。
 * 必填校验、错误文案需要人工在浏览器确认，见 `docs/test-report.md`。
 *
 * 说明：样式断言只能证明规则被正确声明，真机观感仍需人工确认。
 */

const srcDir = path.resolve(process.cwd(), 'src')
const loginSource = fs.readFileSync(path.join(srcDir, 'views', 'LoginView.vue'), 'utf-8')
const styleBlock = /<style[^>]*>([\s\S]*?)<\/style>/.exec(loginSource)?.[1] ?? ''
const sheet = postcss.parse(styleBlock)
const globalCss = fs.readFileSync(path.join(srcDir, 'styles', 'index.css'), 'utf-8')

interface RuleInfo {
  selector: string
  decls: Record<string, string>
}

function rulesInsideMedia(params: string): RuleInfo[] {
  const found: RuleInfo[] = []
  sheet.walkAtRules('media', (atRule) => {
    if (!atRule.params.includes(params)) {
      return
    }
    atRule.walkRules((rule) => {
      const decls: Record<string, string> = {}
      rule.walkDecls((decl) => {
        decls[decl.prop] = decl.value
      })
      found.push({ selector: rule.selector, decls })
    })
  })
  return found
}

/** 顶层规则（不含 @media 覆盖）里某选择器的声明 */
function declsFor(fragment: string): Record<string, string> {
  const merged: Record<string, string> = {}
  sheet.walkRules((rule) => {
    if (rule.parent?.type !== 'root') {
      return
    }
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

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'root', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: LoginView },
      { path: '/:pathMatch(.*)*', name: 'catchall', component: { template: '<div />' } },
    ],
  })
}

async function mountLogin(redirect?: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = makeRouter()
  await router.push(redirect ? `/login?redirect=${redirect}` : '/login')
  await router.isReady()

  // 不整模块 mock `@/api/identity`：自动 mock 会让 csrf 变成返回 undefined 的桩，
  // 掩盖「先取 CSRF」这一步。这里只替换 csrf，其余保持真实实现。
  const csrfSpy = vi.spyOn(identityApi, 'csrf').mockResolvedValue(undefined as never)
  const loginSpy = vi.spyOn(useAuthStore(), 'login').mockResolvedValue(undefined as never)

  const wrapper = mount(LoginView, { global: { plugins: [pinia, ElementPlus, router] } })
  await nextTick()
  return { wrapper, router, csrfSpy, loginSpy }
}

type Wrapper = Awaited<ReturnType<typeof mountLogin>>['wrapper']

function buttonByText(wrapper: Wrapper, text: string) {
  const button = wrapper.findAll('button').find((item) => item.text().includes(text))
  expect(button, `未找到按钮：${text}`).toBeTruthy()
  return button!
}

describe('登录页渲染', () => {
  it('渲染品牌、表单与登录按钮', async () => {
    const { wrapper } = await mountLogin()
    const text = wrapper.text()

    expect(text).toContain('意尚智造')
    expect(text).toContain('集成平台')
    expect(text).toContain('服饰企业一体化经营管理平台')
    expect(text).toContain('账号登录')
    expect(text).toContain('账号')
    expect(text).toContain('密码')
    expect(text).toContain('登录')
    // 安全提示必须保留：账号锁定规则要让用户在登录前就看到
    expect(text).toContain('连续登录失败会被锁定账号')
  })

  it('账号与密码输入框带上正确的 autocomplete，便于密码管理器工作', async () => {
    const { wrapper } = await mountLogin()
    const inputs = wrapper.findAll('input')

    expect(inputs[0].attributes('autocomplete')).toBe('username')
    expect(inputs[1].attributes('autocomplete')).toBe('current-password')
  })

  it('左侧要点用面向使用者的业务描述，不出现开发术语', async () => {
    const { wrapper } = await mountLogin()
    const text = wrapper.text()

    expect(text).toContain('一套账号，权限分明')
    expect(text).toContain('基础资料统一维护')
    expect(text).toContain('采购到销售全程贯通')
    expect(text).toContain('单据与审批全程留痕')

    // 左栏面向业务用户：不得出现开发/实现视角的术语
    for (const jargon of ['四层权限', '后端', '前端', '接口', 'SKU', 'BOM']) {
      expect(text).not.toContain(jargon)
    }

    // 未实施的模块不得出现在登录页（否则等于虚假宣传）
    expect(text).not.toContain('MES')
    expect(text).not.toContain('WMS')
    expect(text).not.toContain('QMS')
  })
})

describe('登录提交流程', () => {
  it('先取 CSRF 再调用登录接口', async () => {
    const { wrapper, csrfSpy, loginSpy } = await mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('secret')

    await buttonByText(wrapper, '登录').trigger('click')
    await flushPromises()

    expect(csrfSpy).toHaveBeenCalledTimes(1)
    expect(loginSpy).toHaveBeenCalledWith('admin', 'secret')
    // 顺序：CSRF 必须先于登录（登录接口自身也做 CSRF 校验）
    expect(csrfSpy.mock.invocationCallOrder[0]).toBeLessThan(loginSpy.mock.invocationCallOrder[0])
  })

  it('登录成功后跳转到 redirect 指定的地址', async () => {
    const { wrapper, router } = await mountLogin('/system/users')
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('secret')

    await buttonByText(wrapper, '登录').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/system/users')
  })

  it('账号两侧空格会被去掉再提交', async () => {
    const { wrapper, loginSpy } = await mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('  admin  ')
    await inputs[1].setValue('secret')

    await buttonByText(wrapper, '登录').trigger('click')
    await flushPromises()

    expect(loginSpy).toHaveBeenCalledWith('admin', 'secret')
  })
})

describe('登录页样式', () => {
  it('样式定义在组件内，全局样式表不再重复定义 .ys-login', () => {
    expect(Object.keys(declsFor('.ys-login')).length).toBeGreaterThan(0)
    // 全局表里不能有第二处定义（避免两处打架、改一处不生效）
    expect(globalCss).not.toContain('.ys-login')
  })

  it('窄屏隐藏左侧品牌区，并在卡片内显示紧凑品牌', () => {
    const narrow = rulesInsideMedia('max-width: 960px')
    const intro = narrow.find((rule) => rule.selector === '.ys-login__intro')
    expect(intro?.decls['display']).toBe('none')

    const compact = narrow.find((rule) => rule.selector === '.ys-login__brand--compact')
    expect(compact?.decls['display']).toBe('flex')

    // 宽屏时紧凑品牌不应出现（否则会出现两个 logo）
    expect(declsFor('.ys-login__brand--compact')['display']).toBe('none')
  })

  it('登录按钮使用品牌渐变，且宽度占满卡片', () => {
    const submit = declsFor('.ys-login__submit')
    expect(submit['width']).toBe('100%')
    expect(submit['background']).toContain('gradient')
  })

  it('动效受 prefers-reduced-motion 保护', () => {
    const motion = rulesInsideMedia('prefers-reduced-motion: no-preference')
    expect(motion.length).toBeGreaterThan(0)
    expect(motion.some((rule) => rule.decls['animation']?.includes('ys-login-rise'))).toBe(true)
  })

  it('装饰层不拦截鼠标事件，且不引入任何外链资源', () => {
    expect(declsFor('.ys-login__aurora')['pointer-events']).toBe('none')
    // 离线可用：不得出现 http(s) 外链（字体、图片、CDN）
    expect(styleBlock).not.toMatch(/url\(\s*['"]?https?:/)
  })
})
