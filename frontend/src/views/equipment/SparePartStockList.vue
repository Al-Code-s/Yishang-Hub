<template>
  <entity-list-page
    title="库存台账"
    entity-label="备件现存量"
    description="按仓库与储位查看备件现存量：可用量 = 实存量 − 冻结量 − 占用量。数据直接来自仓储模块的库存余额，这里只读；低于安全库存的备件会被标记出来，便于安排采购。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :detail-fields="detailFields"
    readonly
    search-placeholder="搜索备件编码、名称或规格"
    default-ordering="code"
    :page-size="20"
    empty-text="暂无备件库存"
  >
    <template #column-below_safety="{ row }">
      <el-tag v-if="row.below_safety" type="danger" size="small" effect="light">低于安全库存</el-tag>
      <span v-else class="ys-muted">正常</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FilterDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { sparePartStockApi } from '@/api/endpoints'
import { companyOptions, warehouseOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const api = sparePartStockApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '备件编码', width: 150 },
  { prop: 'name', label: '备件名称', minWidth: 150 },
  { prop: 'part_type', label: '备件类别', width: 110 },
  { prop: 'spec', label: '规格型号', width: 130 },
  { prop: 'equipment_type_name', label: '适用设备类型', width: 140 },
  { prop: 'warehouse_name', label: '仓库', width: 130 },
  { prop: 'location_name', label: '储位', width: 110 },
  { prop: 'batch_no', label: '批次', width: 110 },
  {
    prop: 'on_hand',
    label: '实存量',
    width: 100,
    formatter: (row) => formatAmount(row.on_hand as string),
  },
  {
    prop: 'reserved',
    label: '占用量',
    width: 100,
    formatter: (row) => formatAmount(row.reserved as string),
  },
  {
    prop: 'available',
    label: '可用量',
    width: 100,
    formatter: (row) => formatAmount(row.available as string),
  },
  {
    prop: 'safety_stock',
    label: '安全库存',
    width: 100,
    formatter: (row) => formatAmount(row.safety_stock as string),
  },
  { prop: 'below_safety', label: '库存状态', width: 130 },
  { prop: 'life_days', label: '参考寿命（天）', width: 130 },
]

const filters = computed<FilterDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', optionsLoader: companyOptions },
  { prop: 'warehouse_id', label: '仓库', type: 'select', optionsLoader: warehouseOptions },
  {
    prop: 'part_type',
    label: '备件类别',
    type: 'select',
    options: meta.options('part_types'),
  },
  {
    prop: 'below_safety',
    label: '库存状态',
    type: 'select',
    options: [{ value: 'true', label: '仅看低于安全库存' }],
  },
])

const detailFields = [
  { prop: 'uom_name', label: '单位' },
  { prop: 'quality_status', label: '质量状态' },
  {
    prop: 'life_days',
    label: '参考寿命（天）',
  },
]
</script>