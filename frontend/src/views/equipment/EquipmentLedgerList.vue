<template>
  <entity-list-page
    title="设备台账"
    entity-label="设备"
    description="设备台账按资产视角查看每台设备的归属、原值、启用与保修情况，用于年度盘点与折旧核对。数据的修改入口在「设备信息管理」。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :detail-fields="detailFields"
    readonly
    search-placeholder="搜索设备编号、名称或出厂编号"
    :page-size="20"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('equipment_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-is_special="{ row }">
      <el-tag v-if="row.is_special" type="warning" size="small" effect="light">特种设备</el-tag>
      <span v-else>—</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { equipmentApi } from '@/api/endpoints'
import { companyOptions, equipmentTypeOptions, factoryOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const api = equipmentApi as never

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'in_use') return 'success'
  if (status === 'repairing') return 'warning'
  if (status === 'scrapped' || status === 'stopped') return 'danger'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '设备编号', width: 150, sortable: true },
  { prop: 'name', label: '设备名称', minWidth: 160 },
  { prop: 'equipment_type_name', label: '设备类型', width: 140 },
  { prop: 'status', label: '设备状态', width: 110 },
  { prop: 'factory_name', label: '所属工厂', width: 140 },
  { prop: 'location', label: '安装位置', width: 140 },
  {
    prop: 'original_value',
    label: '资产原值',
    width: 130,
    formatter: (row) => formatAmount(row.original_value as string),
  },
  { prop: 'start_date', label: '启用日期', width: 120 },
  { prop: 'warranty_until', label: '保修截止', width: 120 },
  { prop: 'owner_employee_name', label: '责任人', width: 110 },
  { prop: 'is_special', label: '特种设备', width: 100 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'equipment_type_id',
    label: '设备类型',
    type: 'select' as const,
    optionsLoader: equipmentTypeOptions,
  },
  {
    prop: 'status',
    label: '设备状态',
    type: 'select' as const,
    options: meta.options('equipment_statuses'),
  },
  { prop: 'factory_id', label: '所属工厂', type: 'select' as const, optionsLoader: factoryOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'brand', label: '品牌' },
  { prop: 'model_no', label: '规格型号' },
  { prop: 'serial_no', label: '出厂编号' },
  { prop: 'supplier_name', label: '供应商' },
  { prop: 'purchase_date', label: '采购日期' },
  { prop: 'owner_department_name', label: '负责部门' },
  { prop: 'original_value', label: '资产原值' },
  { prop: 'remark', label: '备注' },
]
</script>