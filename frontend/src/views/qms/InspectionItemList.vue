<template>
  <entity-list-page
    title="检验项目"
    entity-label="检验项目"
    description="检验项目是检验单明细的判定依据，也是判定口径的唯一来源。定量项目必须给出上限或下限之一，检验时由系统按标准区间自动判合格；定性项目（如外观、手感）没有数值口径，由检验员给出结论。项目编码留空时按编号规则自动生成。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'qms.inspection_item.create', update: 'qms.inspection_item.update' }"
    search-placeholder="搜索项目编码、名称、检验方法或标准要求"
    default-ordering="code"
    :page-size="20"
  >
    <template #column-value_type="{ row }">
      <el-tag
        :type="String(row.value_type) === 'quantitative' ? 'primary' : 'warning'"
        size="small"
        effect="light"
      >
        {{ meta.label('inspection_value_types', String(row.value_type)) }}
      </el-tag>
    </template>
    <template #column-category="{ row }">
      {{ meta.label('inspection_categories', String(row.category)) }}
    </template>
    <template #column-limits="{ row }">
      <span v-if="limitsText(row)" class="ys-mono">{{ limitsText(row) }}</span>
      <span v-else class="ys-muted">无数值口径</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { qualityInspectionItemApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const api = qualityInspectionItemApi as never
const meta = useMetaStore()

function limitsText(row: Record<string, unknown>): string {
  const lower = row.lower_limit
  const upper = row.upper_limit
  if (lower === null && upper === null) {
    return ''
  }
  return `${lower ?? '-'} ~ ${upper ?? '-'}`
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '项目编码', width: 150, sortable: true },
  { prop: 'name', label: '项目名称', minWidth: 180 },
  { prop: 'category', label: '项目类别', width: 110 },
  { prop: 'value_type', label: '判定方式', width: 170 },
  { prop: 'limits', label: '标准区间', width: 160 },
  { prop: 'unit', label: '单位', width: 80 },
  { prop: 'method', label: '检验方法与工具', minWidth: 180 },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'category',
    label: '项目类别',
    type: 'select' as const,
    options: meta.options('inspection_categories'),
  },
  {
    prop: 'value_type',
    label: '判定方式',
    type: 'select' as const,
    options: meta.options('inspection_value_types'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'standard_text', label: '标准要求' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'code',
    label: '项目编码',
    onlyOnUpdate: true,
    help: '同一公司内唯一；留空时由系统按编号规则自动生成',
  },
  { prop: 'name', label: '项目名称', required: true, span: 24 },
  {
    prop: 'category',
    label: '项目类别',
    type: 'select',
    required: true,
    options: meta.options('inspection_categories'),
    defaultValue: 'appearance',
  },
  {
    prop: 'value_type',
    label: '判定方式',
    type: 'select',
    required: true,
    options: meta.options('inspection_value_types'),
    defaultValue: 'quantitative',
    help: '定量由系统按上下限自动判定；定性由检验员给出结论',
  },
  { prop: 'unit', label: '单位' },
  { prop: 'lower_limit', label: '标准下限', type: 'decimal', nullable: true, help: '包含端点；留空表示不设下限' },
  { prop: 'upper_limit', label: '标准上限', type: 'decimal', nullable: true, help: '包含端点；留空表示不设上限' },
  { prop: 'method', label: '检验方法与工具', span: 24 },
  { prop: 'standard_text', label: '标准要求', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
