<template>
  <entity-list-page
    title="异常类型"
    entity-label="异常类型"
    description="异常类型用于归类现场发现的设备异常（异响、渗漏、参数漂移等），并给出默认等级，便于按等级安排处理顺序。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.abnormal_type.create', update: 'equipment.abnormal_type.update', deactivate: 'equipment.abnormal_type.update' }"
    search-placeholder="搜索类型编码或名称"
    :page-size="20"
  >
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ row.level_display || meta.label('fault_levels', String(row.level)) }}
      </el-tag>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { abnormalTypeApi } from '@/api/endpoints'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = abnormalTypeApi as never

function levelTagType(level: string): 'info' | 'warning' | 'danger' {
  if (level === 'critical' || level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '类型编码', width: 140, sortable: true },
  { prop: 'name', label: '类型名称', minWidth: 160 },
  { prop: 'level', label: '默认等级', width: 110 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'level',
    label: '默认等级',
    type: 'select' as const,
    options: meta.options('fault_levels'),
  },
])

const detailFields = [{ prop: 'remark', label: '备注' }]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '类型编码', required: true, help: '平台内唯一' },
  { prop: 'name', label: '类型名称', required: true },
  {
    prop: 'level',
    label: '默认等级',
    type: 'select',
    options: meta.options('fault_levels'),
    defaultValue: 'medium',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>