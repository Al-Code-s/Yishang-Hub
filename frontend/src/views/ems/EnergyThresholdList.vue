<template>
  <entity-list-page
    title="阈值管理"
    entity-label="阈值"
    description="阈值定义什么情况算异常：仪表读数超过上下限、当日用量超过日限额、单位产品能耗超限，或仪表超过设定分钟数没有新读数（离线）。系统按这里的规则自动生成报警，未配置阈值的仪表不会触发越限报警。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ems.threshold.create', update: 'ems.threshold.update' }"
    search-placeholder="搜索阈值方案名称"
    default-ordering="name"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { energyThresholdApi } from '@/api/endpoints'
import { companyOptions, energyMeterOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'

const api = energyThresholdApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'name', label: '阈值名称', minWidth: 170 },
  { prop: 'medium', label: '介质', width: 80 },
  { prop: 'meter_name', label: '适用仪表', width: 160 },
  { prop: 'upper_limit', label: '上限', width: 110, formatter: (row) => formatDecimal(row.upper_limit as string) },
  { prop: 'lower_limit', label: '下限', width: 110, formatter: (row) => formatDecimal(row.lower_limit as string) },
  { prop: 'daily_limit', label: '日用量上限', width: 120, formatter: (row) => formatDecimal(row.daily_limit as string) },
  { prop: 'offline_minutes', label: '离线判定（分钟）', width: 150 },
  { prop: 'alarm_level', label: '报警级别', width: 100 },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'medium', label: '介质', type: 'select' as const, options: meta.options('energy_media') },
  { prop: 'meter_id', label: '适用仪表', type: 'select' as const, optionsLoader: energyMeterOptions },
  { prop: 'alarm_level', label: '报警级别', type: 'select' as const, options: meta.options('alarm_levels') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'unit_consumption_limit', label: '单耗上限' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'name', label: '阈值名称', required: true },
  { prop: 'medium', label: '计量介质', type: 'select', required: true, options: meta.options('energy_media'), defaultValue: "electricity" },
  { prop: 'meter_id', label: '适用仪表', type: 'select', optionsLoader: energyMeterOptions, help: '留空表示按介质整体生效' },
  { prop: 'upper_limit', label: '读数上限', type: 'decimal', nullable: true },
  { prop: 'lower_limit', label: '读数下限', type: 'decimal', nullable: true },
  { prop: 'daily_limit', label: '日用量上限', type: 'decimal', nullable: true },
  { prop: 'unit_consumption_limit', label: '单耗上限', type: 'decimal', help: '单位产品能耗上限，用于单耗报警', nullable: true },
  { prop: 'offline_minutes', label: '离线判定（分钟）', type: 'number', defaultValue: 0, help: '0 表示不做离线报警' },
  { prop: 'alarm_level', label: '报警级别', type: 'select', options: meta.options('alarm_levels'), defaultValue: "warning" },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
