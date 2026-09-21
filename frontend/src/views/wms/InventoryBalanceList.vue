<template>
  <div class="ys-page">
    <entity-list-page
      title="库存余额"
      description="库存数量只能通过出入库过账改变，本页只提供查询。可用量 = 实存量 - 冻结量 - 占用量，均由系统计算；冻结与占用不会对同一批数量重复扣减。"
      entity-label="库存余额"
      readonly
      :api="balanceApiRef"
      :columns="columns"
      :filters="filters"
      search-placeholder="搜索物料编码、名称、批次号或卷号"
      default-ordering="-updated_at"
      empty-text="暂无库存余额。库存余额在库存单据过账后才会产生。"
    >
      <template #filters="{ filters: values }">
        <el-select v-model="values.has_stock" placeholder="是否有库存" clearable style="width: 140px">
          <el-option label="有库存" value="true" />
          <el-option label="零库存" value="false" />
        </el-select>
      </template>
      <template #column-quality_status="{ row }">
        <el-tag :type="qualityTagType(String(row.quality_status))" size="small" effect="light">
          {{ row.quality_status_display || row.quality_status }}
        </el-tag>
      </template>
      <template #column-on_hand="{ row }">
        <span class="ys-mono">{{ formatAmount(String(row.on_hand ?? '0')) }}</span>
      </template>
      <template #column-frozen="{ row }">
        <span class="ys-mono">{{ formatAmount(String(row.frozen ?? '0')) }}</span>
      </template>
      <template #column-reserved="{ row }">
        <span class="ys-mono">{{ formatAmount(String(row.reserved ?? '0')) }}</span>
      </template>
      <template #column-available="{ row }">
        <span class="ys-mono">{{ formatAmount(String(row.available ?? '0')) }}</span>
      </template>
    </entity-list-page>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FilterDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { inventoryBalanceApi } from '@/api/endpoints'
import { materialOptions, warehouseOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()

const balanceApiRef = inventoryBalanceApi as never

const columns: ProTableColumn[] = [
  { prop: 'material_code', label: '物料编码', width: 140, sortable: true },
  { prop: 'material_name', label: '物料名称', minWidth: 140 },
  { prop: 'warehouse_name', label: '仓库', width: 140 },
  { prop: 'location_code', label: '储位', width: 110 },
  { prop: 'batch_no', label: '批次号', width: 120 },
  { prop: 'roll_no', label: '卷号', width: 110 },
  { prop: 'quality_status', label: '质量状态', width: 100 },
  { prop: 'on_hand', label: '实存量', width: 130 },
  { prop: 'frozen', label: '冻结量', width: 120 },
  { prop: 'reserved', label: '占用量', width: 120 },
  { prop: 'available', label: '可用量', width: 130 },
]

const filters = computed<FilterDef[]>(() => [
  { prop: 'material_id', label: '物料', type: 'select' as const, optionsLoader: materialOptions },
  { prop: 'warehouse_id', label: '仓库', type: 'select' as const, optionsLoader: warehouseOptions },
  {
    prop: 'quality_status',
    label: '质量状态',
    type: 'select' as const,
    options: meta.options('quality_statuses'),
  },
  { prop: 'batch_no', label: '批次号' },
])

function qualityTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'qualified') return 'success'
  if (status === 'quarantine') return 'warning'
  if (status === 'rejected') return 'danger'
  return 'info'
}
</script>