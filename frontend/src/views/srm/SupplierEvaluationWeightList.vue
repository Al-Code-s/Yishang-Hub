<template>
  <entity-list-page
    title="评价权重配置"
    entity-label="权重版本"
    description="五类权重（质量 / 技术 / 响应 / 交付 / 成本）合计必须正好是 100%。权重配置只增不改：点「编辑」会派生出一个新版本，旧版本原样保留，历史评价仍按打分当时的权重解释。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{
      create: 'srm.evaluation_weight.create',
      update: 'srm.evaluation_weight.update',
    }"
    :searchable="false"
    default-ordering="-version_no"
    :page-size="20"
    :action-width="160"
  >
    <template #column-version_no="{ row }">
      <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
        v{{ row.version_no }}
      </el-tag>
      <span v-if="row.is_active" class="ys-muted ys-ml-4">当前启用</span>
    </template>
    <template #column-total_weight="{ row }">
      <span class="ys-mono">{{ row.total_weight }}%</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { supplierEvaluationWeightApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'

const api = supplierEvaluationWeightApi as never

const columns: ProTableColumn[] = [
  { prop: 'version_no', label: '版本', width: 130, sortable: true },
  { prop: 'quality_weight', label: '质量', width: 100 },
  { prop: 'technology_weight', label: '技术', width: 100 },
  { prop: 'response_weight', label: '响应', width: 100 },
  { prop: 'delivery_weight', label: '交付', width: 100 },
  { prop: 'cost_weight', label: '成本', width: 100 },
  { prop: 'total_weight', label: '合计', width: 110 },
  { prop: 'is_active', label: '状态', width: 90 },
  { prop: 'remark', label: '备注', minWidth: 160 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'version_no', label: '版本号' },
  { prop: 'total_weight', label: '合计' },
  { prop: 'remark', label: '备注' },
]

const weightField = (prop: string, label: string): FormFieldDef => ({
  prop,
  label,
  type: 'decimal',
  help: '单位 %，可填 0',
})

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'company_id',
    label: '所属公司',
    type: 'select',
    required: true,
    optionsLoader: companyOptions,
    onlyOnCreate: true,
  },
  weightField('quality_weight', '质量权重'),
  weightField('technology_weight', '技术权重'),
  weightField('response_weight', '响应权重'),
  weightField('delivery_weight', '交付权重'),
  weightField('cost_weight', '成本权重'),
  { prop: 'is_active', label: '启用', type: 'switch', defaultValue: true },
  {
    prop: 'remark',
    label: '备注',
    type: 'textarea',
    span: 24,
    help: '编辑保存后会生成新版本；旧版本保留，历史评价不受影响',
  },
])
</script>
