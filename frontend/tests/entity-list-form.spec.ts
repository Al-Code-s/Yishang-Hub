import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'

/**
 * 通用列表页表单字段的「按模式可见」契约。
 *
 * 背景：主数据编码（客户编码）由后端按编码规则自动生成，新增时不应要求人工输入，
 * 否则用户要么去查规则、要么随手编一个，反而破坏编码口径。
 * 这里锁定 `onlyOnCreate` / `onlyOnUpdate` 两个开关的真实行为，
 * 避免以后调整过滤逻辑时把系统托管字段又漏回到新增表单里。
 *
 * 另外校验：新增时不展示的字段不会被提交（后端才能走自动取号分支）。
 */

const columns: ProTableColumn[] = [
  { prop: 'code', label: '客户编码' },
  { prop: 'name', label: '客户名称' },
]

const formFields: FormFieldDef[] = [
  { prop: 'code', label: '客户编码', onlyOnUpdate: true },
  { prop: 'name', label: '客户名称', required: true },
  { prop: 'initial_password', label: '初始密码', onlyOnCreate: true },
]

function makeApi() {
  return {
    list: vi.fn().mockResolvedValue({
      count: 1,
      results: [{ id: 7, code: 'CUS20260001', name: '甲客户' }],
    }),
    create: vi.fn().mockResolvedValue({ id: 8 }),
    update: vi.fn().mockResolvedValue({ id: 7 }),
  }
}

async function mountPage() {
  const api = makeApi()
  const wrapper = mount(EntityListPage, {
    props: {
      title: '客户档案',
      entityLabel: '客户',
      api: api as never,
      columns,
      formFields,
      defaultOrdering: 'code',
    },
    global: { plugins: [createPinia(), ElementPlus] },
  })
  await flushPromises()
  await nextTick()
  return { wrapper, api }
}

function buttonByText(wrapper: Awaited<ReturnType<typeof mountPage>>['wrapper'], text: string) {
  const button = wrapper.findAll('button').find((item) => item.text().includes(text))
  expect(button, `未找到按钮：${text}`).toBeTruthy()
  return button!
}

/**
 * 只取弹窗里的表单文本。
 * 页面整文里本来就含表头（列名），用整页文本判断字段是否展示会永远命中。
 */
function dialogFormText(wrapper: Awaited<ReturnType<typeof mountPage>>['wrapper']): string {
  const form = wrapper.find('.el-dialog .el-form')
  expect(form.exists(), '新增/编辑弹窗未渲染出表单').toBe(true)
  return form.text()
}

describe('EntityListPage 表单字段可见性', () => {
  it('新增时不显示系统托管字段，也不显示仅编辑字段', async () => {
    const { wrapper } = await mountPage()
    await buttonByText(wrapper, '新增客户').trigger('click')
    await nextTick()
    await nextTick()

    const text = dialogFormText(wrapper)
    expect(text).toContain('客户名称')
    expect(text).toContain('初始密码')
    expect(text).not.toContain('客户编码')
  })

  it('编辑时显示系统托管字段，不显示仅新增字段', async () => {
    const { wrapper } = await mountPage()
    await buttonByText(wrapper, '编辑').trigger('click')
    await nextTick()
    await nextTick()

    const text = dialogFormText(wrapper)
    expect(text).toContain('客户编码')
    expect(text).toContain('客户名称')
    expect(text).not.toContain('初始密码')
  })

  it('新增提交的载荷里不含未展示的编码字段', async () => {
    const { wrapper, api } = await mountPage()
    await buttonByText(wrapper, '新增客户').trigger('click')
    await nextTick()
    await nextTick()

    const nameInput = wrapper.find('input[placeholder="请输入客户名称"]')
    expect(nameInput.exists()).toBe(true)
    await nameInput.setValue('乙客户')

    const saveButton = buttonByText(wrapper, '保存')
    await saveButton.trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledTimes(1)
    const payload = api.create.mock.calls[0][0] as Record<string, unknown>
    expect(payload).toEqual({ name: '乙客户' })
    expect('code' in payload).toBe(false)
  })
})

describe('EntityListPage 数值字段回填', () => {
  const decimalColumns: ProTableColumn[] = [
    { prop: 'code', label: '物料编码' },
    { prop: 'purchase_factor', label: '采购换算率' },
  ]
  const decimalFormFields: FormFieldDef[] = [
    { prop: 'code', label: '物料编码', onlyOnUpdate: true },
    { prop: 'purchase_factor', label: '采购换算率', type: 'decimal' },
  ]

  async function mountDecimalPage() {
    const api = {
      list: vi.fn().mockResolvedValue({
        count: 1,
        results: [{ id: 1, code: 'M-001', purchase_factor: '12.000000' }],
      }),
      create: vi.fn(),
      update: vi.fn(),
    }
    const wrapper = mount(EntityListPage, {
      props: {
        title: '物料档案',
        entityLabel: '物料',
        api: api as never,
        columns: decimalColumns,
        formFields: decimalFormFields,
        defaultOrdering: 'code',
      },
      global: { plugins: [createPinia(), ElementPlus] },
    })
    await flushPromises()
    await nextTick()
    return wrapper
  }

  /**
   * 操作列 fixed="right"，Element Plus 会把固定列 DOM 渲染两份；
   * 第一份是虚拟表（点不到真实行），必须取最后一份才是页面上的按钮。
   */
  function lastButtonByText(
    wrapper: Awaited<ReturnType<typeof mountDecimalPage>>,
    text: string,
  ) {
    const buttons = wrapper.findAll('button').filter((item) => item.text().includes(text))
    expect(buttons.length, `未找到按钮：${text}`).toBeGreaterThan(0)
    return buttons[buttons.length - 1]
  }

  it('编辑回填时去掉末尾 0，输入框不再出现 12.000000', async () => {
    const wrapper = await mountDecimalPage()
    await lastButtonByText(wrapper, '编辑').trigger('click')
    await nextTick()
    await nextTick()

    const input = wrapper.find('input[placeholder="十进制数值，例如 12.50"]')
    expect(input.exists()).toBe(true)
    expect((input.element as HTMLInputElement).value).toBe('12')
  })

  it('列表里的数值列按 2 位小数展示', async () => {
    const wrapper = await mountDecimalPage()
    expect(wrapper.text()).toContain('12.00')
    expect(wrapper.text()).not.toContain('12.000000')
  })
})
