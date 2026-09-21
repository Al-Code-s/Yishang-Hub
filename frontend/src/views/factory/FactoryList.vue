<template>
  <entity-list-page
    title="工厂"
    entity-label="工厂"
    description="工厂是数据权限的主要维度之一：被授权某个工厂的角色，只能看到并操作该工厂范围内的数据。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'factory.factory.create', update: 'factory.factory.update' }"
    search-placeholder="搜索工厂编码或名称"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { factoryApi as factoryCrudApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'

const api = factoryCrudApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '工厂编码', width: 130, sortable: true },
  { prop: 'name', label: '工厂名称', minWidth: 180 },
  { prop: 'company_name', label: '所属公司', width: 180 },
  { prop: 'manager_name', label: '负责人', width: 120 },
  { prop: 'address', label: '地址', minWidth: 200 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '工厂编码', required: true },
  { prop: 'name', label: '工厂名称', required: true },
  { prop: 'manager_id', label: '负责人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'address', label: '地址', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>