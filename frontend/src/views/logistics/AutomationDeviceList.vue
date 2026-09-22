<template>
  <entity-list-page
    title="自动化设备"
    entity-label="自动化设备"
    description="AGV、穿梭车、堆垛机、工业机器人、输送线等物流自动化设备的台账。新建时设备默认为「空闲」，之后的状态一律用列表里的「变更状态」动作维护——每次变更都会自动写一条操作日志，便于追溯设备在什么时候被谁停用或报修。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'logistics.device.create', update: 'logistics.device.update' }"
    search-placeholder="搜索设备编码、名称或位置"
    default-ordering="code"
    :page-size="20"
    :action-width="220"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('automation_device_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canUpdate"
        link
        type="primary"
        size="small"
        @click="openStatus(row)"
      >
        变更状态
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="statusVisible" title="变更设备状态" width="560px" :close-on-click-modal="false">
    <el-alert v-if="statusError" type="error" :closable="false" show-icon :title="statusError" class="ys-form-error" />
    <el-form :model="statusForm" label-width="120px">
      <el-form-item label="设备">
        <el-input :model-value="statusTargetLabel" disabled />
      </el-form-item>
      <el-form-item label="新状态" required>
        <el-select v-model="statusForm.status" style="width: 100%">
          <el-option
            v-for="option in statusOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="电量（%）">
        <el-input-number v-model="statusForm.battery_level as number" :min="0" :max="100" style="width: 100%" />
      </el-form-item>
      <el-form-item label="说明">
        <el-input v-model="statusForm.detail as string" type="textarea" :rows="2" placeholder="例如：更换电池后恢复作业" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="statusVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitStatus">确认变更</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { automationDeviceApi } from '@/api/endpoints'
import { companyOptions, workshopOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'

const auth = useAuthStore()
const meta = useMetaStore()
const api = automationDeviceApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canUpdate = computed(() => auth.hasPermission('logistics.device.update'))
const statusOptions = computed(() => meta.options('automation_device_statuses'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'running') return 'primary'
  if (status === 'idle') return 'success'
  if (status === 'fault') return 'danger'
  if (status === 'offline') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '设备编码', width: 150, sortable: true },
  { prop: 'name', label: '设备名称', minWidth: 150 },
  { prop: 'device_type', label: '设备类型', width: 130 },
  { prop: 'status', label: '当前状态', width: 110 },
  { prop: 'workshop_name', label: '所属车间', width: 140 },
  { prop: 'location', label: '位置', width: 140 },
  { prop: 'max_load', label: '最大载重', width: 110, formatter: (row) => formatDecimal(row.max_load as string) },
  { prop: 'speed', label: '速度', width: 100, formatter: (row) => formatDecimal(row.speed as string) },
  { prop: 'battery_level', label: '电量（%）', width: 100 },
  { prop: 'next_maintenance_date', label: '下次保养日期', width: 140, sortable: true },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'device_type', label: '设备类型', type: 'select' as const, options: meta.options('automation_device_types') },
  { prop: 'status', label: '当前状态', type: 'select' as const, options: meta.options('automation_device_statuses') },
  { prop: 'workshop_id', label: '所属车间', type: 'select' as const, optionsLoader: workshopOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'commissioned_date', label: '投用日期' },
  { prop: 'last_maintenance_date', label: '上次保养日期' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '设备编码', onlyUpdate: true, help: '同一公司内唯一；留空时由系统按编号规则自动生成' },
  { prop: 'name', label: '设备名称', required: true },
  {
    prop: 'device_type',
    label: '设备类型',
    type: 'select',
    required: true,
    options: meta.options('automation_device_types'),
    defaultValue: 'agv',
  },
  { prop: 'workshop_id', label: '所属车间', type: 'select', optionsLoader: workshopOptions },
  { prop: 'location', label: '位置' },
  { prop: 'max_load', label: '最大载重', type: 'decimal', def: '0' },
  { prop: 'speed', label: '速度', type: 'decimal', def: '0' },
  { prop: 'battery_level', label: '电量（%）', type: 'number', nullable: true },
  { prop: 'commissioned_date', label: '投用日期', type: 'date' },
  { prop: 'last_maintenance_date', label: '上次保养日期', type: 'date' },
  { prop: 'next_maintenance_date', label: '下次保养日期', type: 'date' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const statusVisible = ref(false)
const statusError = ref('')
const submitting = ref(false)
const statusTarget = ref<Record<string, unknown> | null>(null)
const statusForm = reactive<Record<string, unknown>>({ status: 'idle', battery_level: null, detail: '' })

const statusTargetLabel = computed(() => {
  const row = statusTarget.value
  return row ? String(row.code ?? '') + ' ' + String(row.name ?? '') : ''
})

function openStatus(row: Record<string, unknown>): void {
  statusTarget.value = row
  statusError.value = ''
  statusForm.status = String(row.status ?? 'idle')
  statusForm.battery_level = row.battery_level ?? null
  statusForm.detail = ''
  statusVisible.value = true
}

async function submitStatus(): Promise<void> {
  const target = statusTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  statusError.value = ''
  try {
    await automationDeviceApi.action(Number(target.id), 'set-status', {
      status: statusForm.status,
      battery_level: statusForm.battery_level,
      detail: statusForm.detail,
    })
    ElMessage.success('设备状态已更新')
    statusVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    statusError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
