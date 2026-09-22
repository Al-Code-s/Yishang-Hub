<template>
  <entity-list-page
    title="报警管理"
    entity-label="报警"
    description="汇集四类报警：读数越限、仪表离线、单位产量能耗超限、当日能耗超限。系统按阈值管理里的规则自动触发，也可以人工上报。处理中→已关闭的每一步都留痕，不提供直接改状态的捷径。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ems.alarm.create', update: 'ems.alarm.update' }"
    search-placeholder="搜索报警编号、内容或仪表"
    default-ordering="-occurred_at"
    :toggleable="false"
    :page-size="20"
    :action-width="200"
    ref="pageRef"
  >
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ row.level_display || meta.label('alarm_levels', String(row.level)) }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('alarm_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #toolbar="{ reload }">
      <el-button v-if="canHandle" @click="scanOffline(reload)">立即扫描离线仪表</el-button>
      <el-button @click="reload">刷新</el-button>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canHandle && row.status === 'pending'"
        link
        type="primary"
        size="small"
        @click="handleAlarm(row, reload)"
      >
        开始处理
      </el-button>
      <el-button
        v-if="canHandle && row.status !== 'closed'"
        link
        type="success"
        size="small"
        @click="openClose(row)"
      >
        关闭
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="closeVisible" title="关闭报警" width="600px" :close-on-click-modal="false">
    <el-alert v-if="closeError" type="error" :closable="false" show-icon :title="closeError" class="ys-form-error" />
    <el-form :model="closeForm" label-width="120px">
      <el-form-item label="报警编号">
        <el-input v-model="closeForm.alarm_no" disabled />
      </el-form-item>
      <el-form-item label="处理说明" required>
        <el-input v-model="closeForm.note" type="textarea" :rows="3" placeholder="记录实际原因与处置措施" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="closeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitClose">确认关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { energyActions } from '@/api/energy'
import { energyAlarmApi } from '@/api/endpoints'
import { companyOptions, energyAreaOptions, energyMeterOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()
const api = energyAlarmApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canHandle = computed(() => auth.hasPermission('ems.alarm.handle'))

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (level === 'critical') return 'danger'
  if (level === 'warning') return 'warning'
  return 'info'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'handling') return 'primary'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'alarm_no', label: '报警编号', width: 160, sortable: true },
  { prop: 'alarm_type', label: '报警类型', width: 120 },
  { prop: 'level', label: '级别', width: 90 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'meter_name', label: '计量设备', minWidth: 140 },
  { prop: 'area_name', label: '所属区域', width: 130 },
  { prop: 'message', label: '报警内容', minWidth: 180 },
  {
    prop: 'triggered_value',
    label: '触发值',
    width: 110,
    formatter: (row) => formatDecimal(row.triggered_value as string),
  },
  {
    prop: 'threshold_value',
    label: '阈值',
    width: 110,
    formatter: (row) => formatDecimal(row.threshold_value as string),
  },
  {
    prop: 'occurred_at',
    label: '发生时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.occurred_at ?? '')),
  },
  { prop: 'handler_name', label: '处理人', width: 110 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'meter_id', label: '计量设备', type: 'select' as const, optionsLoader: energyMeterOptions },
  { prop: 'area_id', label: '所属区域', type: 'select' as const, optionsLoader: energyAreaOptions },
  { prop: 'alarm_type', label: '报警类型', type: 'select' as const, options: meta.options('alarm_types') },
  { prop: 'level', label: '级别', type: 'select' as const, options: meta.options('alarm_levels') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('alarm_statuses') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'handle_note', label: '处理说明' },
  { prop: 'handled_at', label: '处理时间' },
  { prop: 'closed_at', label: '关闭时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'meter_id', label: '计量设备', type: 'select', optionsLoader: energyMeterOptions },
  {
    prop: 'alarm_type',
    label: '报警类型',
    type: 'select',
    required: true,
    options: meta.options('alarm_types'),
    defaultValue: 'over_limit',
  },
  {
    prop: 'level',
    label: '报警级别',
    type: 'select',
    required: true,
    options: meta.options('alarm_levels'),
    defaultValue: 'warning',
  },
  { prop: 'occurred_at', label: '发生时间', type: 'date' },
  { prop: 'message', label: '报警内容', required: true, span: 24 },
  { prop: 'triggered_value', label: '触发值', type: 'decimal', nullable: true },
  { prop: 'threshold_value', label: '阈值', type: 'decimal', nullable: true },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const closeVisible = ref(false)
const closeError = ref('')
const submitting = ref(false)
const closeTarget = ref<Record<string, unknown> | null>(null)
const closeForm = reactive<Record<string, unknown>>({ alarm_no: '', note: '' })

async function handleAlarm(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await energyAlarmApi.action(Number(row.id), 'handle', { note: '', handler_id: null })
    ElMessage.success('已开始处理')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function openClose(row: Record<string, unknown>): void {
  closeTarget.value = row
  closeError.value = ''
  closeForm.alarm_no = String(row.alarm_no ?? '')
  closeForm.note = ''
  closeVisible.value = true
}

async function submitClose(): Promise<void> {
  const target = closeTarget.value
  if (!target) {
    return
  }
  if (!String(closeForm.note ?? '').trim()) {
    closeError.value = '关闭报警必须填写处理说明。'
    return
  }
  submitting.value = true
  closeError.value = ''
  try {
    await energyAlarmApi.action(Number(target.id), 'close', { note: closeForm.note })
    ElMessage.success('报警已关闭')
    closeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    closeError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function scanOffline(reload: () => Promise<void>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '将立即按阈值里的离线判定规则扫描一次仪表，超过设定分钟数没有新读数的仪表会生成离线报警。继续？',
    '离线扫描',
    { type: 'info', confirmButtonText: '开始扫描', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    const result = await energyActions.scanOffline()
    ElMessage.success('扫描完成，新增报警 ' + result.created + ' 条')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '扫描失败')
  }
}
</script>
