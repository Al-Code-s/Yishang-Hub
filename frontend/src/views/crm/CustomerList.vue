<template>
  <entity-list-page
    title="客户档案"
    entity-label="客户"
    description="客户档案与联系人。新增客户不必手工输入编码，留空即按编号规则自动生成（可在「系统管理 → 编码规则」调整格式）。客户按所属公司归集；信用额度仅作管理参考，不等同应收账款台账。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'crm.customer.create', update: 'crm.customer.update' }"
    search-placeholder="搜索客户编码、名称或简称"
    :page-size="20"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('customer_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-level="{ row }">
      {{ meta.label('customer_levels', String(row.level)) }}
    </template>
    <template #toolbar>
      <el-tag type="info" effect="plain">客户等级与分类的可选值由平台统一提供</el-tag>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { customerApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const api = customerApi as never

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'active') return 'success'
  if (status === 'suspended') return 'warning'
  if (status === 'terminated') return 'danger'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '客户编码', width: 140, sortable: true },
  { prop: 'name', label: '客户名称', minWidth: 180 },
  { prop: 'short_name', label: '简称', width: 120 },
  { prop: 'level', label: '等级', width: 130 },
  { prop: 'status', label: '合作状态', width: 110 },
  {
    prop: 'credit_limit',
    label: '信用额度',
    width: 130,
    formatter: (row) => formatAmount(row.credit_limit as string),
  },
  { prop: 'salesman_name', label: '业务员', width: 120 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'category',
    label: '客户分类',
    type: 'select' as const,
    options: meta.options('customer_categories'),
  },
  { prop: 'level', label: '客户等级', type: 'select' as const, options: meta.options('customer_levels') },
  {
    prop: 'status',
    label: '合作状态',
    type: 'select' as const,
    options: meta.options('customer_statuses'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'tax_no', label: '纳税人识别号' },
  { prop: 'payment_terms', label: '结算方式' },
  { prop: 'primary_contact_name', label: '主要联系人' },
  { prop: 'primary_contact_phone', label: '主要联系电话' },
  { prop: 'address', label: '地址' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'code',
    label: '客户编码',
    // 新增时由后端按编码规则（CUS）自动取号，不要求人工输入；编辑时展示以便核对
    onlyOnUpdate: true,
    help: '同一公司内唯一，被订单引用后不建议修改',
  },
  { prop: 'name', label: '客户名称', required: true },
  { prop: 'short_name', label: '客户简称' },
  {
    prop: 'category',
    label: '客户分类',
    type: 'select',
    options: meta.options('customer_categories'),
  },
  { prop: 'level', label: '客户等级', type: 'select', options: meta.options('customer_levels') },
  {
    prop: 'status',
    label: '合作状态',
    type: 'select',
    options: meta.options('customer_statuses'),
  },
  {
    prop: 'credit_limit',
    label: '信用额度',
    type: 'decimal',
    defaultValue: '0',
    help: '仅作管理参考，不等于财务应收余额',
  },
  { prop: 'payment_terms', label: '结算方式' },
  { prop: 'tax_no', label: '纳税人识别号' },
  { prop: 'primary_contact_name', label: '主要联系人' },
  { prop: 'primary_contact_phone', label: '主要联系电话' },
  { prop: 'salesman_id', label: '业务员', type: 'select', optionsLoader: employeeOptions },
  { prop: 'address', label: '地址', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>