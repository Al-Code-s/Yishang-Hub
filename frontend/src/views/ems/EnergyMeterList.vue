<template>
  <entity-list-page
    title="设备管理"
    entity-label="计量设备"
    description="计量设备是抄表与能耗统计的入口：水表、电表、气表、液表都在这登记。仪表编码留空时按编号规则自动生成；只有勾选「纳入监控」的仪表才会出现在设备监控页与首页统计里。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ems.meter.create', update: 'ems.meter.update' }"
    search-placeholder="搜索仪表编码、名称、位置或出厂编号"
    default-ordering="code"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { energyMeterApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, energyAreaOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'

const api = energyMeterApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'code', label: '仪表编码', width: 150, sortable: true },
  { prop: 'name', label: '仪表名称', minWidth: 160 },
  { prop: 'medium', label: '介质', width: 80 },
  { prop: 'area_name', label: '所属区域', width: 140 },
  { prop: 'meter_model', label: '规格型号', width: 140 },
  { prop: 'unit', label: '计量单位', width: 90 },
  { prop: 'status', label: '状态', width: 90 },
  {
    prop: 'last_reading_at',
    label: '最近抄表时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.last_reading_at ?? '')),
  },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'medium', label: '介质', type: 'select' as const, options: meta.options('energy_media') },
  { prop: 'area_id', label: '所属区域', type: 'select' as const, optionsLoader: energyAreaOptions },
  { prop: 'status', label: '仪表状态', type: 'select' as const, options: meta.options('meter_statuses') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'equipment_name', label: '关联设备' },
  { prop: 'serial_no', label: '出厂编号' },
  { prop: 'location', label: '安装位置' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '仪表编码', help: '同一公司内唯一；留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'name', label: '仪表名称', required: true },
  { prop: 'medium', label: '计量介质', type: 'select', required: true, options: meta.options('energy_media'), defaultValue: "electricity" },
  { prop: 'area_id', label: '所属区域', type: 'select', optionsLoader: energyAreaOptions },
  { prop: 'equipment_id', label: '关联设备', type: 'select', optionsLoader: equipmentOptions, help: '关联后单耗与设备运行记录可自动统计' },
  { prop: 'department_id', label: '使用部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'meter_model', label: '规格型号' },
  { prop: 'serial_no', label: '出厂编号' },
  { prop: 'multiplier', label: '倍率', type: 'decimal', defaultValue: "1", help: '带互感器的电表填倍率，抄表用量会自动乘以倍率' },
  { prop: 'unit', label: '计量单位', defaultValue: "kWh" },
  { prop: 'status', label: '仪表状态', type: 'select', options: meta.options('meter_statuses'), defaultValue: "online" },
  { prop: 'location', label: '安装位置' },
  { prop: 'install_date', label: '安装日期', type: 'date' },
  { prop: 'is_monitored', label: '纳入监控', type: 'switch', defaultValue: true },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
