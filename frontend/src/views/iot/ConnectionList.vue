<template>
  <entity-list-page
    title="数采连接配置"
    entity-label="连接"
    description="连接配置描述「数据从哪来、用什么协议、一次能收多少、一分钟最多收几次」。首版只实现了 HTTP 上报与内置模拟器；MQTT / Modbus 属于待协议确认的选项，未实现的协议在采集入口会被明确拒绝，不会静默丢数据。凭证只登记引用位置（如「网关令牌」「厂内网段」），平台不在业务表里保存明文密钥。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'iot.connection.create', update: 'iot.connection.update' }"
    search-placeholder="搜索连接编码、名称或接入地址"
    :page-size="20"
  >
    <template #column-protocol="{ row }">
      <el-tag :type="protocolTagType(String(row.protocol))" size="small" effect="light">
        {{ row.protocol_display || meta.label('iot_protocols', String(row.protocol)) }}
      </el-tag>
    </template>
    <template #column-is_simulated="{ row }">
      <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
      <span v-else class="ys-muted">真实</span>
    </template>
    <template #toolbar>
      <el-tag type="info" effect="plain">模拟连接产生的读数会全程标注为「模拟」</el-tag>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { iotConnectionApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = iotConnectionApi as never

function protocolTagType(protocol: string): 'success' | 'warning' | 'info' {
  if (protocol === 'http') return 'success'
  if (protocol === 'simulator') return 'warning'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '连接编码', width: 150, sortable: true },
  { prop: 'name', label: '连接名称', minWidth: 160 },
  { prop: 'protocol', label: '协议', width: 110 },
  { prop: 'endpoint', label: '接入地址', minWidth: 180 },
  { prop: 'batch_limit', label: '单批上限', width: 100 },
  { prop: 'rate_limit_per_minute', label: '每分钟上限', width: 110 },
  { prop: 'is_enabled', label: '启用采集', width: 100 },
  { prop: 'is_simulated', label: '数据标识', width: 100 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'protocol',
    label: '协议',
    type: 'select' as const,
    options: meta.options('iot_protocols'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'credential_ref', label: '凭证引用' },
  { prop: 'timeout_seconds', label: '超时（秒）' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'code',
    label: '连接编码',
    onlyOnUpdate: true,
    help: '留空时由系统按编号规则（IOTCN）自动生成',
  },
  { prop: 'name', label: '连接名称', required: true },
  {
    prop: 'protocol',
    label: '采集协议',
    type: 'select',
    required: true,
    options: meta.options('iot_protocols'),
    defaultValue: 'http',
  },
  { prop: 'endpoint', label: '接入地址', span: 24, help: '如 http://10.0.0.8:8080/report' },
  {
    prop: 'credential_ref',
    label: '凭证引用',
    span: 24,
    help: '只写凭证的存放位置或说明，不要在此填写明文密码',
  },
  { prop: 'timeout_seconds', label: '超时（秒）', type: 'number', defaultValue: 10 },
  { prop: 'batch_limit', label: '单次上报测点上限', type: 'number', defaultValue: 200 },
  {
    prop: 'rate_limit_per_minute',
    label: '每分钟上报上限',
    type: 'number',
    defaultValue: 60,
    help: '按设备统计；0 表示不限制',
  },
  { prop: 'is_enabled', label: '启用采集', type: 'switch' },
  {
    prop: 'is_simulated',
    label: '模拟连接',
    type: 'switch',
    help: '开启后该连接产生的报文与读数都会标注为「模拟」',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
