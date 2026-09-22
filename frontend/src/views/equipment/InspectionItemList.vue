<template>
  <entity-list-page
    title="点巡检项目"
    entity-label="点巡检项目"
    description="点巡检项目说明「检查什么、用什么方法、合格范围是多少」。设了下限与上限后，记录里的实测值可以直观对照；项目可按需复用。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.inspection_item.create', update: 'equipment.inspection_item.update', deactivate: 'equipment.inspection_item.update' }"
    search-placeholder="搜索项目编码、名称或标准"
    :page-size="20"
  >
    <template #column-limits="{ row }">
      <span v-if="row.lower_limit === null && row.upper_limit === null" class="ys-muted">不限定</span>
      <span v-else>{{ limitText(row) }}</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { inspectionItemApi } from '@/api/endpoints'
import { uomOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = inspectionItemApi as never

function limitText(row: Record<string, unknown>): string {
  const lower = row.lower_limit === null || row.lower_limit === undefined ? '不限' : String(row.lower_limit)
  const upper = row.upper_limit === null || row.upper_limit === undefined ? '不限' : String(row.upper_limit)
  const uom = row.uom_name ? ` ${String(row.uom_name)}` : ''
  return `${lower} ~ ${upper}${uom}`
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '项目编码', width: 140, sortable: true },
  { prop: 'name', label: '项目名称', minWidth: 150 },
  { prop: 'method', label: '检查方法', width: 110 },
  { prop: 'limits', label: '合格范围', width: 170 },
  { prop: 'standard', label: '检查标准', minWidth: 200 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'method',
    label: '检查方法',
    type: 'select' as const,
    options: meta.options('inspection_methods'),
  },
])

const detailFields = [
  { prop: 'standard', label: '检查标准' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '项目编码', required: true, help: '平台内唯一' },
  { prop: 'name', label: '项目名称', required: true },
  {
    prop: 'method',
    label: '检查方法',
    type: 'select',
    options: meta.options('inspection_methods'),
  },
  { prop: 'uom_id', label: '计量单位', type: 'select', optionsLoader: uomOptions },
  { prop: 'lower_limit', label: '下限', type: 'decimal', nullable: true },
  { prop: 'upper_limit', label: '上限', type: 'decimal', nullable: true },
  { prop: 'standard', label: '检查标准', type: 'textarea', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>