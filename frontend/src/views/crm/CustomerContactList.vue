<template>
  <entity-list-page
    title="客户联系人"
    entity-label="联系人"
    description="联系人通过所属客户继承公司数据范围：看不到客户的人，也看不到其联系人。同一客户下只能有一个主联系人，切换主联系人会自动取消原主联系人标记。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'crm.customer_contact.create', update: 'crm.customer_contact.update' }"
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
import { customerApi, customerContactApi } from '@/api/endpoints'
import type { EnumOption } from '@/types/models'

const api = customerContactApi as never

/** 客户下拉只显示启用中的客户，避免把联系人挂到已停用客户上。 */
async function customerOptions(): Promise<EnumOption[]> {
  const page = await customerApi.list({ page_size: 200, is_active: true, ordering: 'code' })
  return page.results.map((row) => ({
    value: row.id,
    label: `${row.code} ${row.name}`,
  }))
}

const columns: ProTableColumn[] = [
  { prop: 'customer_name', label: '所属客户', minWidth: 180 },
  { prop: 'name', label: '姓名', width: 120 },
  { prop: 'position', label: '职务', width: 130 },
  { prop: 'phone', label: '电话', width: 140 },
  { prop: 'email', label: '邮箱', minWidth: 180 },
  { prop: 'is_primary', label: '主要联系人', width: 120 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'customer_id', label: '所属客户', type: 'select' as const, optionsLoader: customerOptions },
])

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'customer_id',
    label: '所属客户',
    type: 'select',
    required: true,
    optionsLoader: customerOptions,
  },
  { prop: 'name', label: '姓名', required: true, help: '同一客户下不允许同名联系人' },
  { prop: 'position', label: '职务' },
  { prop: 'phone', label: '电话' },
  { prop: 'email', label: '邮箱' },
  {
    prop: 'is_primary',
    label: '主要联系人',
    type: 'switch',
    defaultValue: false,
    help: '开启后，该客户原有主联系人会被自动取消标记',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>