<template>
  <entity-list-page
    title="排污监测"
    entity-label="监测记录"
    description="废水、废气、噪声等排放口的监测记录：限值、实测值、是否达标由后端按限值自动判定，超标记录会标记出来。监测编号留空时按编号规则自动生成。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.env_monitor.create', update: 'ehs.env_monitor.update' }"
    search-placeholder="搜索监测编号、排放口、污染物或许可证号"
    default-ordering="-monitored_at"
    :toggleable="false"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { environmentMonitorApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const api = environmentMonitorApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'monitor_no', label: '监测编号', width: 150, sortable: true },
  { prop: 'medium', label: '排放介质', width: 100 },
  { prop: 'point_name', label: '排放口', width: 150 },
  { prop: 'pollutant', label: '污染物', width: 130 },
  { prop: 'limit_value', label: '限值', width: 100, formatter: (row) => formatDecimal(row.limit_value as string) },
  { prop: 'measured_value', label: '实测值', width: 100, formatter: (row) => formatDecimal(row.measured_value as string) },
  { prop: 'unit', label: '单位', width: 90 },
  {
    prop: 'monitored_at',
    label: '监测时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.monitored_at ?? '')),
  },
  { prop: 'is_compliant', label: '是否达标', width: 100 },
  { prop: 'permit_no', label: '排污许可证号', width: 150 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'medium', label: '排放介质', type: 'select' as const, options: meta.options('environment_media') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'monitor_org', label: '监测机构' },
  { prop: 'is_over_limit', label: '是否超标' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'monitor_no', label: '监测编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'medium', label: '排放介质', type: 'select', required: true, options: meta.options('environment_media'), defaultValue: "waste_water" },
  { prop: 'point_name', label: '排放口', required: true },
  { prop: 'pollutant', label: '污染物', required: true },
  { prop: 'limit_value', label: '限值', type: 'decimal', help: '留空表示不做达标判定', nullable: true },
  { prop: 'measured_value', label: '实测值', type: 'decimal', nullable: true },
  { prop: 'unit', label: '计量单位', defaultValue: "mg/L" },
  { prop: 'monitored_at', label: '监测时间', type: 'date', required: true },
  { prop: 'permit_no', label: '排污许可证号' },
  { prop: 'monitor_org', label: '监测机构' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
