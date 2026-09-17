<template>
  <entity-list-page
    title="公司"
    entity-label="公司"
    description="平台按单企业、多工厂、多部门设计，但数据模型保留公司归属；这不等于已实现 SaaS 多租户隔离。"
    :api="api"
    :columns="columns"
    :form-fields="formFields"
    :permissions="{ create: 'factory.company.create', update: 'factory.company.update' }"
    search-placeholder="搜索公司编码或名称"
  />
</template>

<script setup lang="ts">
import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { companyApi } from '@/api/endpoints'

const api = companyApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '公司编码', width: 140, sortable: true },
  { prop: 'name', label: '公司名称', minWidth: 200 },
  { prop: 'short_name', label: '简称', width: 120 },
  { prop: 'contact_person', label: '联系人', width: 120 },
  { prop: 'contact_phone', label: '联系电话', width: 140 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const formFields: FormFieldDef[] = [
  { prop: 'code', label: '公司编码', required: true },
  { prop: 'name', label: '公司名称', required: true },
  { prop: 'short_name', label: '简称' },
  { prop: 'contact_person', label: '联系人' },
  { prop: 'contact_phone', label: '联系电话' },
  { prop: 'address', label: '地址', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]
</script>