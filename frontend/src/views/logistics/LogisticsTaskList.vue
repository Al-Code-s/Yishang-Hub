<template>
  <entity-list-page
    title="任务管理"
    entity-label="物流任务"
    description="物流任务的状态只能按「待下发 → 已下发 → 执行中 → 已完成」推进，或从任一未完成状态取消；每一步都由服务层校验并写操作日志，界面上不提供直接改状态的入口。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'logistics.task.create', update: 'logistics.task.update' }"
    search-placeholder="搜索任务编号、容器号或设备"
    default-ordering="-created_at"
    :toggleable="false"
    :page-size="20"
    :action-width="300"
    ref="pageRef"
  >
    <template #column-priority="{ row }">
      <el-tag :type="priorityTagType(String(row.priority))" size="small" effect="light">
        {{ row.priority_display || meta.label('logistics_task_priorities', String(row.priority)) }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('logistics_task_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canDispatch && row.status === 'pending'"
        link
        type="primary"
        size="small"
        @click="openDispatch(row)"
      >
        下发
      </el-button>
      <el-button
        v-if="canExecute && row.status === 'dispatched'"
        link
        type="primary"
        size="small"
        @click="startTask(row, reload)"
      >
        开始执行
      </el-button>
      <el-button
        v-if="canExecute && (row.status === 'dispatched' || row.status === 'executing')"
        link
        type="success"
        size="small"
        @click="openFinish(row)"
      >
        完成
      </el-button>
      <el-button
        v-if="canDispatch && row.status !== 'finished' && row.status !== 'cancelled'"
        link
        type="danger"
        size="small"
        @click="cancelTask(row, reload)"
      >
        取消
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="dispatchVisible" title="下发物流任务" width="600px" :close-on-click-modal="false">
    <el-alert v-if="dispatchError" type="error" :closable="false" show-icon :title="dispatchError" class="ys-form-error" />
    <el-form :model="dispatchForm" label-width="130px">
      <el-form-item label="任务编号">
        <el-input v-model="dispatchForm.task_no" disabled />
      </el-form-item>
      <el-form-item label="执行设备">
        <el-select v-model="dispatchForm.device_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in deviceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="执行人">
        <el-select v-model="dispatchForm.assignee_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="计划执行时间">
        <el-date-picker
          v-model="dispatchForm.planned_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 100%"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dispatchVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitDispatch">确认下发</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="finishVisible" title="完成物流任务" width="600px" :close-on-click-modal="false">
    <el-alert v-if="finishError" type="error" :closable="false" show-icon :title="finishError" class="ys-form-error" />
    <el-form :model="finishForm" label-width="130px">
      <el-form-item label="实际数量">
        <el-input v-model="finishForm.quantity" placeholder="留空表示与计划数量一致" />
      </el-form-item>
      <el-form-item label="目标库位">
        <el-select v-model="finishForm.to_location_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in locationChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="操作人">
        <el-select v-model="finishForm.operator_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="执行结果">
        <el-input v-model="finishForm.result" type="textarea" :rows="2" placeholder="例如：3 号库位已满，改放 4 号库位" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="finishVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitFinish">确认完成</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { logisticsTaskApi } from '@/api/endpoints'
import {
  automationDeviceOptions,
  companyOptions,
  employeeOptions,
  locationOptions,
  materialOptions,
  warehouseOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = logisticsTaskApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canDispatch = computed(() => auth.hasPermission('logistics.task.update'))
const canExecute = computed(() => auth.hasPermission('logistics.task.execute'))

function priorityTagType(priority: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (priority === 'urgent') return 'danger'
  if (priority === 'high') return 'warning'
  if (priority === 'low') return 'info'
  return 'primary'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'finished') return 'success'
  if (status === 'executing') return 'primary'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'task_no', label: '任务编号', width: 160, sortable: true },
  { prop: 'task_type', label: '任务类型', width: 120 },
  { prop: 'priority', label: '优先级', width: 90 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'device_name', label: '执行设备', width: 140 },
  { prop: 'assignee_name', label: '执行人', width: 110 },
  { prop: 'warehouse_name', label: '仓库', width: 130 },
  { prop: 'from_location_name', label: '起始库位', width: 130 },
  { prop: 'to_location_name', label: '目标库位', width: 130 },
  { prop: 'material_name', label: '物料', minWidth: 140 },
  { prop: 'quantity', label: '数量', width: 110, formatter: (row) => formatDecimal(row.quantity as string) },
  { prop: 'container_no', label: '容器号', width: 120 },
  {
    prop: 'planned_at',
    label: '计划执行时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.planned_at ?? '')),
  },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'task_type', label: '任务类型', type: 'select' as const, options: meta.options('logistics_task_types') },
  { prop: 'priority', label: '优先级', type: 'select' as const, options: meta.options('logistics_task_priorities') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('logistics_task_statuses') },
  { prop: 'device_id', label: '执行设备', type: 'select' as const, optionsLoader: automationDeviceOptions },
  { prop: 'warehouse_id', label: '仓库', type: 'select' as const, optionsLoader: warehouseOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'requested_by_name', label: '申请人' },
  { prop: 'dispatched_at', label: '下发时间' },
  { prop: 'started_at', label: '开始时间' },
  { prop: 'finished_at', label: '完成时间' },
  { prop: 'result', label: '执行结果' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'task_no', label: '任务编号', onlyUpdate: true, help: '留空时由系统按编号规则自动生成' },
  {
    prop: 'task_type',
    label: '任务类型',
    type: 'select',
    required: true,
    options: meta.options('logistics_task_types'),
    defaultValue: 'move',
  },
  {
    prop: 'priority',
    label: '优先级',
    type: 'select',
    options: meta.options('logistics_task_priorities'),
    defaultValue: 'normal',
  },
  { prop: 'warehouse_id', label: '仓库', type: 'select', optionsLoader: warehouseOptions },
  { prop: 'from_location_id', label: '起始库位', type: 'select', optionsLoader: locationOptions },
  { prop: 'to_location_id', label: '目标库位', type: 'select', optionsLoader: locationOptions },
  { prop: 'material_id', label: '物料', type: 'select', optionsLoader: materialOptions },
  { prop: 'quantity', label: '计划数量', type: 'decimal', def: '0' },
  { prop: 'container_no', label: '容器号' },
  { prop: 'requested_by_id', label: '申请人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'planned_at', label: '计划执行时间', type: 'date' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const dispatchVisible = ref(false)
const dispatchError = ref('')
const finishVisible = ref(false)
const finishError = ref('')
const submitting = ref(false)
const dispatchTarget = ref<Record<string, unknown> | null>(null)
const finishTarget = ref<Record<string, unknown> | null>(null)
const deviceOptions = ref<EnumOption[]>([])
const employeeChoiceOptions = ref<EnumOption[]>([])
const locationChoiceOptions = ref<EnumOption[]>([])

const dispatchForm = reactive<Record<string, unknown>>({
  task_no: '',
  device_id: null,
  assignee_id: null,
  planned_at: '',
})
const finishForm = reactive<Record<string, unknown>>({
  quantity: '',
  to_location_id: null,
  operator_id: null,
  result: '',
})

onMounted(async () => {
  deviceOptions.value = await automationDeviceOptions().catch(() => [])
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
  locationChoiceOptions.value = await locationOptions().catch(() => [])
})

function openDispatch(row: Record<string, unknown>): void {
  dispatchTarget.value = row
  dispatchError.value = ''
  dispatchForm.task_no = String(row.task_no ?? '')
  dispatchForm.device_id = row.device_id ?? null
  dispatchForm.assignee_id = row.assignee_id ?? null
  dispatchForm.planned_at = ''
  dispatchVisible.value = true
}

async function submitDispatch(): Promise<void> {
  const target = dispatchTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  dispatchError.value = ''
  try {
    await logisticsTaskApi.action(Number(target.id), 'dispatch', {
      device_id: dispatchForm.device_id,
      assignee_id: dispatchForm.assignee_id,
      planned_at: dispatchForm.planned_at || null,
    })
    ElMessage.success('任务已下发')
    dispatchVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dispatchError.value = error instanceof ApiError ? error.message : '下发失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function openFinish(row: Record<string, unknown>): void {
  finishTarget.value = row
  finishError.value = ''
  finishForm.quantity = ''
  finishForm.to_location_id = row.to_location_id ?? null
  finishForm.operator_id = row.assignee_id ?? null
  finishForm.result = ''
  finishVisible.value = true
}

async function submitFinish(): Promise<void> {
  const target = finishTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  finishError.value = ''
  try {
    await logisticsTaskApi.action(Number(target.id), 'finish', {
      quantity: finishForm.quantity || null,
      to_location_id: finishForm.to_location_id,
      operator_id: finishForm.operator_id,
      result: finishForm.result || '',
    })
    ElMessage.success('任务已完成')
    finishVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    finishError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function startTask(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await logisticsTaskApi.action(Number(row.id), 'start', { operator_id: row.assignee_id ?? null })
    ElMessage.success('任务已开始执行')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function cancelTask(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const input = await ElMessageBox.prompt('取消后该任务不再执行。请填写取消原因：', '取消任务', {
    confirmButtonText: '确认取消',
    cancelButtonText: '再想想',
    inputPlaceholder: '例如：计划变更，物料不再需要搬运',
  }).catch(() => null)
  if (!input) {
    return
  }
  try {
    await logisticsTaskApi.action(Number(row.id), 'cancel', { reason: input.value })
    ElMessage.success('任务已取消')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>
