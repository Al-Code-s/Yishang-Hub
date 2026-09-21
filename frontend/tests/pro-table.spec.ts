import ElementPlus from 'element-plus'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'

/**
 * 通用表格组件测试。
 *
 * 重点验证两件事：
 * 1) 有数据时按列渲染，布尔与空值有明确展示（不出现 undefined / null 字样）；
 * 2) 无数据时展示空状态，而不是一张空白表格让人以为「接口挂了」。
 */
const columns: ProTableColumn[] = [
  { prop: 'code', label: '编码' },
  { prop: 'name', label: '名称' },
  { prop: 'is_active', label: '启用' },
  { prop: 'phone', label: '电话' },
]

/**
 * Element Plus 的表格在挂载后才把 el-table-column 注册进内部 store，
 * 因此必须等一次 tick 才能渲染出表体；断言前先 flush，避免误报。
 */
async function mountTable(rows: Record<string, unknown>[]) {
  const wrapper = mount(ProTable, {
    props: { columns, rows, total: rows.length, page: 1, pageSize: 20 },
    global: { plugins: [ElementPlus] },
  })
  await nextTick()
  await nextTick()
  return wrapper
}

describe('ProTable 数值显示口径', () => {
  const numericColumns: ProTableColumn[] = [
    { prop: 'quantity', label: '数量' },
    { prop: 'phone', label: '电话' },
    { prop: 'tax_no', label: '纳税人识别号' },
  ]

  async function mountNumericTable(rows: Record<string, unknown>[]) {
    const wrapper = mount(ProTable, {
      props: { columns: numericColumns, rows, total: rows.length, page: 1, pageSize: 20 },
      global: { plugins: [ElementPlus] },
    })
    await nextTick()
    await nextTick()
    return wrapper
  }

  it('十进制字符串按 2 位小数显示，纯整数文本保持原样', async () => {
    const wrapper = await mountNumericTable([
      { id: 1, quantity: '12.000000', phone: '13800138000', tax_no: '913301001234567890' },
    ])

    const text = wrapper.text()
    expect(text).toContain('12.00')
    expect(text).not.toContain('12.000000')
    // 手机号、税号是文本，不能被当成数字加千分位
    expect(text).toContain('13800138000')
    expect(text).toContain('913301001234567890')
    expect(text).not.toContain('13,800,138,000')
  })
})

describe('ProTable', () => {
  it('渲染列标题与数据行', async () => {
    const wrapper = await mountTable([
      { id: 1, code: 'M-001', name: '白色棉布', is_active: true, phone: null },
    ])

    expect(wrapper.text()).toContain('编码')
    expect(wrapper.text()).toContain('M-001')
    expect(wrapper.text()).toContain('白色棉布')
  })

  it('布尔值展示为是/否，空值展示为 -', async () => {
    const wrapper = await mountTable([
      { id: 1, code: 'M-001', name: '白色棉布', is_active: true, phone: null },
      { id: 2, code: 'M-002', name: '黑色涤纶', is_active: false, phone: '13800000000' },
    ])

    const text = wrapper.text()
    expect(text).toContain('是')
    expect(text).toContain('否')
    expect(text).not.toContain('null')
    expect(text).toContain('13800000000')
  })

  it('无数据时展示空状态说明', async () => {
    const wrapper = await mountTable([])
    expect(wrapper.text()).toContain('暂无数据')
  })

  it('枚举列优先展示后端返回的中文标签，而不是英文键', async () => {
    const enumColumns: ProTableColumn[] = [
      { prop: 'code', label: '仓库编码' },
      { prop: 'warehouse_type', label: '仓库类型' },
      { prop: 'warehouse_type_display', label: '仓库类型标签' },
    ]
    const wrapper = mount(ProTable, {
      props: {
        columns: enumColumns,
        rows: [
          {
            id: 1,
            code: 'WH-FG-01',
            warehouse_type: 'finished',
            warehouse_type_display: '成品仓',
          },
        ],
        total: 1,
        page: 1,
        pageSize: 20,
      },
      global: { plugins: [ElementPlus] },
    })
    await nextTick()
    await nextTick()

    const text = wrapper.text()
    expect(text).toContain('成品仓')
    expect(text).not.toContain('finished')
  })

  it('没有中文标签时退回原始值，不显示 undefined', async () => {
    const enumColumns: ProTableColumn[] = [{ prop: 'warehouse_type', label: '仓库类型' }]
    const wrapper = mount(ProTable, {
      props: {
        columns: enumColumns,
        rows: [{ id: 1, warehouse_type: 'raw' }],
        total: 1,
        page: 1,
        pageSize: 20,
      },
      global: { plugins: [ElementPlus] },
    })
    await nextTick()
    await nextTick()

    const text = wrapper.text()
    expect(text).toContain('raw')
    expect(text).not.toContain('undefined')
  })

  it('有错误信息时展示告警而不是静默空白', async () => {
    const wrapper = mount(ProTable, {
      props: {
        columns,
        rows: [],
        total: 0,
        page: 1,
        pageSize: 20,
        errorMessage: '加载数据失败（NETWORK_ERROR）',
      },
      global: { plugins: [ElementPlus] },
    })
    await nextTick()
    expect(wrapper.text()).toContain('加载数据失败（NETWORK_ERROR）')
  })
})