<template>
  <entity-list-page
    title="采集测点"
    entity-label="测点"
    description="测点是一台数采设备上的一个具体物理量（温度、电压、电流、振动、流量等）。上报时以测点编码对应，平台按编码入账。测点的公司归属由所属设备推导，客户端不需要、也不允许指定，避免把 A 公司的测点挂到 B 公司。勾选「越限报警」并填写上下限后，超限读数会自动写入能源管理的报警台账；模拟数据不会写入真实抄表。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'iot.point.create', update: 'iot.point.update' }"
    search-placeholder="搜索测点编码或名称"
    default-ordering="code"
    :page-size="20"
    :action-width="200"
  >
    <template #column-quantity="{ row }">
      <el-tag type="info" size="small" effect="light">
        {{ row.quantity_display || meta.label('iot_point_quantities', String(row.quantity)) }}
      </el-tag>
    </template>
    <template #column-is_cumulative="{ row }">
      <el-tag v-if="row.is_cumulative" type="success" size="small" effect="light">累计量</el-tag>
      <el-tag v-else type="info" size="small" effect="light">瞬时量</el-tag>
    </template>
    <template #column-alarm_enabled="{ row }">
      <el-tag v-if="row.alarm_enabled" type="warning" size="small" effect="light">已开启</el-tag>
      <span v-else class="ys-muted">未开启</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { iotPointApi } from '@/api/endpoints'
import { energyMeterOptions, iotGatewayOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = iotPointApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '测点编码', width: 150, sortable: true },
  { prop: 'name', label: '测点名称', minWidth: 160 },
  { prop: 'gateway_code', label: '所属设备', width: 140 },
  { prop: 'gateway_name', label: '设备名称', minWidth: 140 },
  { prop: 'quantity', label: '物理量', width: 100 },
  { prop: 'unit', label: '单位', width: 80 },
  { prop: 'precision', label: '小数位', width: 90 },
  { prop: 'is_cumulative', label: '量值类型', width: 100 },
  { prop: 'upper_limit', label: '报警上限', width: 110 },
  { prop: 'lower_limit', label: '报警下限', width: 110 },
  { prop: 'alarm_enabled', label: '越限报警', width: 100 },
  { prop: 'meter_code', label: '对照能源仪表', width: 140 },
]

const filters = computed(() => [
  { prop: 'gateway_id', label: '数采设备', type: 'select' as const, optionsLoader: iotGatewayOptions },
  {
    prop: 'quantity',
    label: '物理量',
    type: 'select' as const,
    options: meta.options('iot_point_quantities'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'range_min', label: '量程下限' },
  { prop: 'range_max', label: '量程上限' },
  { prop: 'meter_code', label: '对照能源仪表编码' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'gateway_id',
    label: '数采设备',
    type: 'select',
    required: true,
    optionsLoader: iotGatewayOptions,
    help: '测点归属的公司由所选设备决定，不需要单独选择公司',
  },
  {
    prop: 'code',
    label: '测点编码',
    onlyOnUpdate: true,
    help: '留空时由系统按编号规则（IOTPT）自动生成；上报时必须与设备侧一致',
  },
  { prop: 'name', label: '测点名称', required: true },
  {
    prop: 'quantity',
    label: '物理量',
    type: 'select',
    required: true,
    options: meta.options('iot_point_quantities'),
    defaultValue: 'temperature',
  },
  { prop: 'unit', label: '单位', help: '如 ℃、V、A、mm/s、m³/h' },
  { prop: 'precision', label: '小数位', type: 'number', defaultValue: 2 },
  {
    prop: 'is_cumulative',
    label: '累计量',
    type: 'switch',
    defaultValue: false,
    help: '读数是否为一个累计总量（如电表读数），开启后界面按累计量展示',
  },
  { prop: 'range_min', label: '量程下限', type: 'decimal', nullable: true },
  { prop: 'range_max', label: '量程上限', type: 'decimal', nullable: true },
  { prop: 'lower_limit', label: '报警下限', type: 'decimal', nullable: true },
  { prop: 'upper_limit', label: '报警上限', type: 'decimal', nullable: true },
  {
    prop: 'alarm_enabled',
    label: '越限报警',
    type: 'switch',
    defaultValue: true,
    help: '开启且填写了上下限后，超限读数会生成报警',
  },
  {
    prop: 'meter_id',
    label: '对照能源仪表',
    type: 'select',
    optionsLoader: energyMeterOptions,
    help: '只作为对照线索，不会把采集读数写进能源抄表，避免重复计量',
  },
  { prop: 'is_active', label: '启用', type: 'switch', defaultValue: true },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
