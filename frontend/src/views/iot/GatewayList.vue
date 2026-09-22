<template>
  <entity-list-page
    title="数采设备"
    entity-label="数采设备"
    description="数采设备是挂在连接下的采集单元（采集网关、传感器、智能水表、智能电表等）。每台设备使用独立令牌上报，不复用员工登录会话；令牌只在生成或轮换时显示一次，平台只保存摘要，轮换后旧令牌立即失效。在线状态由最近一次上报时间自动判定，界面不提供手工改状态的入口。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'iot.gateway.create', update: 'iot.gateway.update' }"
    search-placeholder="搜索设备编码、名称或安装位置"
    default-ordering="code"
    :page-size="20"
    :action-width="300"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('iot_gateway_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-has_token="{ row }">
      <el-tag v-if="row.has_token" type="success" size="small" effect="light">已下发</el-tag>
      <el-tag v-else type="info" size="small" effect="light">未下发</el-tag>
    </template>
    <template #column-is_simulated="{ row }">
      <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
      <span v-else class="ys-muted">真实</span>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button v-if="canRotate" link type="warning" size="small" @click="rotateToken(row, reload)">
        {{ row.has_token ? '轮换令牌' : '生成令牌' }}
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog
    v-model="tokenVisible"
    title="设备令牌（只显示这一次）"
    width="640px"
    :close-on-click-modal="false"
  >
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="请立即把令牌写入设备侧并妥善保存；关闭窗口后平台不再提供明文，只能重新轮换。"
    />
    <p>设备：{{ tokenGateway }}</p>
    <pre class="ys-code-block">{{ issuedToken }}</pre>
    <p class="ys-muted">
      上报方式：向 /api/v1/iot/ingest/ 发送 POST，请求头带 X-Device-Token（值为上面的令牌），
      请求体含 message_id 与 points（每个测点的编码与读数）。令牌与设备一一对应，不要把同一令牌用于多台设备。
    </p>
    <template #footer>
      <el-button @click="copyToken">复制令牌</el-button>
      <el-button type="primary" @click="tokenVisible = false">我已保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { iotGatewayApi } from '@/api/endpoints'
import { iotGatewayActions } from '@/api/iot'
import {
  companyOptions,
  equipmentOptions,
  iotConnectionOptions,
  workshopOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()
const api = iotGatewayApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canRotate = computed(() => auth.hasPermission('iot.gateway.rotate_token'))

const tokenVisible = ref(false)
const issuedToken = ref('')
const tokenGateway = ref('')

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'online') return 'success'
  if (status === 'offline') return 'danger'
  if (status === 'disabled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '设备编码', width: 150, sortable: true },
  { prop: 'name', label: '设备名称', minWidth: 160 },
  { prop: 'gateway_type', label: '设备类型', width: 120 },
  { prop: 'connection_name', label: '所属连接', minWidth: 140 },
  { prop: 'equipment_name', label: '关联设备', width: 140 },
  { prop: 'status', label: '在线状态', width: 100 },
  {
    prop: 'last_seen_at',
    label: '最近上报时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.last_seen_at ?? '')),
  },
  { prop: 'offline_minutes', label: '离线判定（分钟）', width: 140 },
  { prop: 'has_token', label: '设备令牌', width: 100 },
  { prop: 'is_simulated', label: '数据标识', width: 100 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'gateway_type',
    label: '设备类型',
    type: 'select' as const,
    options: meta.options('iot_gateway_types'),
  },
  {
    prop: 'status',
    label: '在线状态',
    type: 'select' as const,
    options: meta.options('iot_gateway_statuses'),
  },
  { prop: 'equipment_id', label: '关联设备', type: 'select' as const, optionsLoader: equipmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'factory_name', label: '所属工厂' },
  { prop: 'workshop_name', label: '所属车间' },
  { prop: 'production_line_name', label: '所属产线' },
  { prop: 'location', label: '安装位置' },
  { prop: 'token_prefix', label: '令牌前缀' },
  { prop: 'token_rotated_at', label: '令牌下发时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'code',
    label: '设备编码',
    onlyOnUpdate: true,
    help: '留空时由系统按编号规则（IOTGW）自动生成',
  },
  { prop: 'name', label: '设备名称', required: true },
  {
    prop: 'gateway_type',
    label: '设备类型',
    type: 'select',
    required: true,
    options: meta.options('iot_gateway_types'),
    defaultValue: 'gateway',
  },
  { prop: 'connection_id', label: '所属连接', type: 'select', optionsLoader: iotConnectionOptions },
  { prop: 'equipment_id', label: '关联设备', type: 'select', optionsLoader: equipmentOptions },
  { prop: 'workshop_id', label: '所属车间', type: 'select', optionsLoader: workshopOptions },
  { prop: 'location', label: '安装位置' },
  {
    prop: 'offline_minutes',
    label: '离线判定（分钟）',
    type: 'number',
    defaultValue: 30,
    help: '超过该时长没有新上报即判定为离线；模拟设备不参与离线判定',
  },
  {
    prop: 'is_simulated',
    label: '模拟设备',
    type: 'switch',
    defaultValue: false,
    help: '开启后该设备产生的报文与读数都会标注为「模拟」',
  },
  { prop: 'is_active', label: '启用', type: 'switch', defaultValue: true },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function rotateToken(
  row: Record<string, unknown>,
  reload: () => Promise<void>,
): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '生成或轮换后旧令牌立即失效，仍在使用旧令牌的设备会认证失败并停止上报。确认继续？',
    '设备令牌',
    { type: 'warning', confirmButtonText: '确认生成', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    const result = await iotGatewayActions.rotateToken(Number(row.id))
    issuedToken.value = result.token
    tokenGateway.value = `${result.gateway_code} ${String(row.name ?? '')}`.trim()
    tokenVisible.value = true
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '生成令牌失败')
  }
}

async function copyToken(): Promise<void> {
  try {
    await navigator.clipboard.writeText(issuedToken.value)
    ElMessage.success('令牌已复制到剪贴板')
  } catch {
    ElMessage.warning('浏览器未允许自动复制，请手工选中上面的令牌再复制')
  }
}
</script>
