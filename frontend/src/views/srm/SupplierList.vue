<template>
  <entity-list-page
    title="供应商档案"
    entity-label="供应商"
    description="供应商档案、联系人与资质有效期。寻源、报价与评分评价将在后续版本提供，本页不展示尚未实现的评分数字。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'srm.supplier.create', update: 'srm.supplier.update' }"
    search-placeholder="搜索供应商编码、名称或简称"
    :page-size="20"
  >
    <template #column-admission_status="{ row }">
      <el-tag :type="admissionTagType(String(row.admission_status))" size="small" effect="light">
        {{ meta.label('admission_statuses', String(row.admission_status)) }}
      </el-tag>
    </template>
    <template #column-grade="{ row }">
      {{ meta.label('supplier_grades', String(row.grade)) }}
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { supplierApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = supplierApi as never

function admissionTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'admitted') return 'success'
  if (status === 'suspended') return 'warning'
  if (status === 'rejected' || status === 'terminated') return 'danger'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '供应商编码', width: 140, sortable: true },
  { prop: 'name', label: '供应商名称', minWidth: 180 },
  { prop: 'category', label: '供货类别', width: 110 },
  { prop: 'grade', label: '等级', width: 130 },
  { prop: 'admission_status', label: '准入状态', width: 110 },
  { prop: 'primary_contact_name', label: '主要联系人', width: 120 },
  { prop: 'buyer_name', label: '采购员', width: 110 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'category',
    label: '供货类别',
    type: 'select' as const,
    options: meta.options('supplier_categories'),
  },
  {
    prop: 'grade',
    label: '供应商等级',
    type: 'select' as const,
    options: meta.options('supplier_grades'),
  },
  {
    prop: 'admission_status',
    label: '准入状态',
    type: 'select' as const,
    options: meta.options('admission_statuses'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'tax_no', label: '纳税人识别号' },
  { prop: 'payment_terms', label: '结算方式' },
  { prop: 'primary_contact_phone', label: '主要联系电话' },
  { prop: 'address', label: '地址' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '供应商编码', required: true, help: '同一公司内唯一' },
  { prop: 'name', label: '供应商名称', required: true },
  { prop: 'short_name', label: '供应商简称' },
  {
    prop: 'category',
    label: '供货类别',
    type: 'select',
    options: meta.options('supplier_categories'),
  },
  { prop: 'grade', label: '供应商等级', type: 'select', options: meta.options('supplier_grades') },
  {
    prop: 'admission_status',
    label: '准入状态',
    type: 'select',
    options: meta.options('admission_statuses'),
    help: '此处只登记档案信息，不作为审批记录；准入审批流程将在后续版本提供',
  },
  { prop: 'payment_terms', label: '结算方式' },
  { prop: 'tax_no', label: '纳税人识别号' },
  { prop: 'primary_contact_name', label: '主要联系人' },
  { prop: 'primary_contact_phone', label: '主要联系电话' },
  { prop: 'buyer_id', label: '采购员', type: 'select', optionsLoader: employeeOptions },
  { prop: 'address', label: '地址', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>