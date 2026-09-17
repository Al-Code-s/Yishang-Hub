<template>
  <entity-list-page
    title="供应商联系人"
    entity-label="联系人"
    description="联系人通过所属供应商继承公司数据范围。同一供应商下只能有一个主联系人，切换主联系人会自动取消原主联系人标记。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'srm.supplier_contact.create', update: 'srm.supplier_contact.update' }"
    search-placeholder="搜索姓名、电话或职务"
    default-ordering="id"
    :page-size="20"
  >
    <template #column-is_primary="{ row }">
      <el-tag v-if="row.is_primary" type="success" size="small" effect="light">主联系人</el-tag>
      <span v-else class="ys-muted">-</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { supplierApi, supplierContactApi } from '@/api/endpoints'
import type { EnumOption } from '@/types/models'

const api = supplierContactApi as never

/** 供应商下拉只显示启用中的供应商。 */
async function supplierOptions(): Promise<EnumOption[]> {
  const page = await supplierApi.list({ page_size: 200, is_active: true, ordering: 'code' })
  return page.results.map((row) => ({
    value: row.id,
    label: `${row.code} ${row.name}`,
  }))
}

const columns: ProTableColumn[] = [
  { prop: 'supplier_name', label: '所属供应商', minWidth: 180 },
  { prop: 'name', label: '姓名', width: 120 },
  { prop: 'position', label: '职务', width: 130 },
  { prop: 'phone', label: '电话', width: 140 },
  { prop: 'email', label: '邮箱', minWidth: 180 },
  { prop: 'is_primary', label: '主要联系人', width: 120 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'supplier_id',
    label: '所属供应商',
    type: 'select' as const,
    optionsLoader: supplierOptions,
  },
])

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'supplier_id',
    label: '所属供应商',
    type: 'select',
    required: true,
    optionsLoader: supplierOptions,
  },
  { prop: 'name', label: '姓名', required: true, help: '同一供应商下不允许同名联系人' },
  { prop: 'position', label: '职务' },
  { prop: 'phone', label: '电话' },
  { prop: 'email', label: '邮箱' },
  {
    prop: 'is_primary',
    label: '主要联系人',
    type: 'switch',
    defaultValue: false,
    help: '开启后，该供应商原有主联系人会被自动取消标记',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>