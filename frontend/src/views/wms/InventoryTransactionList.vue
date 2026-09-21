<template>
  <div class="ys-page">
    <entity-list-page
      title="库存流水"
      description="库存流水记录每一笔库存变化，只增不改，平台不提供新增、修改或删除的功能。数量为有符号数：入库为正、出库为负。"
      entity-label="库存流水"
      readonly
      :api="transactionApiRef"
      :columns="columns"
      :filters="filters"
      search-placeholder="搜索物料编码、名称、单据编号或原因"
      default-ordering="-id"
      empty-text="暂无库存流水。流水在库存单据过账后才会产生。"
    >
      <template #column-transaction_type="{ row }">
        <el-tag :type="typeTagType(String(row.transaction_type))" size="small" effect="light">
          {{ row.transaction_type_display || row.transaction_type }}
        </el-tag>
      </template>
      <template #column-quantity="{ row }">
        <span class="ys-mono" :class="signedClass(String(row.quantity ?? '0'))">
          {{ signedAmount(String(row.quantity ?? '0')) }}
        </span>
      </template>
      <template #column-on_hand_after="{ row }">
        <span class="ys-mono">{{ formatAmount(String(row.on_hand_after ?? '0')) }}</span>
      </template>
      <template #column-document_no="{ row }">
        <span class="ys-mono">{{ row.document_no || '-' }}</span>
      </template>
    </entity-list-page>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FilterDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { inventoryTransactionApi } from '@/api/endpoints'
import { materialOptions, warehouseOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()

const transactionApiRef = inventoryTransactionApi as never

const columns: ProTableColumn[] = [
  { prop: 'id', label: '流水号', width: 100, sortable: true },
  { prop: 'created_at', label: '发生时间', width: 170, sortable: true },
  { prop: 'transaction_type', label: '流水类型', width: 120 },
  { prop: 'material_code', label: '物料编码', width: 140 },
  { prop: 'material_name', label: '物料名称', minWidth: 130 },
  { prop: 'warehouse_code', label: '仓库', width: 110 },
  { prop: 'location_code', label: '储位', width: 110 },
  { prop: 'batch_no', label: '批次号', width: 110 },
  { prop: 'roll_no', label: '卷号', width: 100 },
  { prop: 'quality_status_display', label: '质量状态', width: 100 },
  { prop: 'quantity', label: '数量', width: 120 },
  { prop: 'on_hand_after', label: '过账后实存', width: 130 },
  { prop: 'document_no', label: '来源单据', width: 160 },
  { prop: 'operator_name', label: '操作人', width: 110 },
  { prop: 'reason', label: '原因', minWidth: 140 },
]

const filters = computed<FilterDef[]>(() => [
  { prop: 'material_id', label: '物料', type: 'select' as const, optionsLoader: materialOptions },
  { prop: 'warehouse_id', label: '仓库', type: 'select' as const, optionsLoader: warehouseOptions },
  {
    prop: 'transaction_type',
    label: '流水类型',
    type: 'select' as const,
    options: meta.options('inventory_transaction_types'),
  },
  { prop: 'batch_no', label: '批次号' },
])

function typeTagType(type: string): 'success' | 'warning' | 'danger' | 'info' {
  if (type.startsWith('receipt') || type.endsWith('_in')) return 'success'
  if (type.startsWith('issue') || type.endsWith('_out')) return 'warning'
  return 'info'
}

function signedAmount(value: string): string {
  const amount = Number(value)
  const text = formatAmount(value)
  return amount > 0 ? `+${text}` : text
}

function signedClass(value: string): string {
  const amount = Number(value)
  if (amount > 0) return 'ys-amount--in'
  if (amount < 0) return 'ys-amount--out'
  return ''
}
</script>

<style scoped>
.ys-amount--in {
  color: var(--el-color-success);
}

.ys-amount--out {
  color: var(--el-color-warning);
}
</style>