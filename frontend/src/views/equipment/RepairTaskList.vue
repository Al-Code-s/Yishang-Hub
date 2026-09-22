<template>
  <entity-list-page
    title="维修任务"
    entity-label="维修任务"
    description="维修任务承接故障派工，也可以直接为设备下维修单。点「开始维修」记录开工时间，点「完成维修」填写故障原因、维修措施与停机时长——完成后系统生成维修记录，并自动关闭来源报修单。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.repair_task.create', update: 'equipment.repair_task.update' }"
    search-placeholder="搜索任务编号、设备或故障描述"
    default-ordering="-id"
    :toggleable="false"
    :page-size="20"
    :action-width="280"
    ref="pageRef"
  >
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ row.level_display || meta.label('fault_levels', String(row.level)) }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('task_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canExecute && row.status === 'pending'"
        link
        type="primary"
        size="small"
        @click="startTask(row)"
      >
        开始维修
      </el-button>
      <el-button
        v-if="canExecute && (row.status === 'pending' || row.status === 'in_progress')"
        link
        type="success"
        size="small"
        @click="openComplete(row)"
      >
        完成维修
      </el-button>
      <el-button
        v-if="canUpdate && (row.status === 'pending' || row.status === 'in_progress')"
        link
        type="danger"
        size="small"
        @click="cancelTask(row)"
      >
        取消
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="completeVisible" title="完成维修" width="680px" :close-on-click-modal="false">
    <el-alert
      v-if="completeError"
      type="error"
      :closable="false"
      show-icon
      :title="completeError"
      class="ys-form-error"
    />
    <el-form :model="completeForm" label-width="120px">
      <el-form-item label="维修人">
        <el-select v-model="completeForm.repairer_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in repairerOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="维修日期">
        <el-date-picker
          v-model="completeForm.repair_date"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="故障原因">
        <el-input v-model="completeForm.fault_reason" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="维修措施">
        <el-input v-model="completeForm.solution" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="领用备件说明">
        <el-input v-model="completeForm.parts_used" type="textarea" :rows="2" />
        <span class="ys-muted">如需扣减库存，请到仓储模块登记领料出库，这里只登记文字说明。</span>
      </el-form-item>
      <el-form-item label="停机时长（分钟）">
        <el-input v-model="completeForm.downtime_minutes" placeholder="0" />
      </el-form-item>
      <el-form-item label="维修费用">
        <el-input v-model="completeForm.cost" placeholder="0" />
      </el-form-item>
      <el-form-item label="维修结果">
        <el-input v-model="completeForm.result" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="completeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitComplete">确认完成</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { repairTaskApi } from '@/api/endpoints'
import { employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = repairTaskApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canExecute = computed(() => auth.hasPermission('equipment.repair_task.execute'))
const canUpdate = computed(() => auth.hasPermission('equipment.repair_task.update'))

function levelTagType(level: string): 'info' | 'warning' | 'danger' {
  if (level === 'critical' || level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'info'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'primary'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'task_no', label: '任务编号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'symptom', label: '故障描述', minWidth: 200 },
  { prop: 'level', label: '故障等级', width: 100 },
  { prop: 'report_no', label: '来源报修单', width: 150 },
  { prop: 'assignee_name', label: '维修人', width: 110 },
  { prop: 'assigned_date', label: '派工日期', width: 120 },
  { prop: 'status', label: '任务状态', width: 110 },
  { prop: 'downtime_minutes', label: '停机时长（分钟）', width: 140 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'status',
    label: '任务状态',
    type: 'select' as const,
    options: meta.options('task_statuses'),
  },
  { prop: 'assignee_id', label: '维修人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'started_at', label: '开始维修时间' },
  { prop: 'finished_at', label: '完成时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'equipment_id',
    label: '设备',
    type: 'select',
    required: true,
    optionsLoader: equipmentOptions,
  },
  { prop: 'symptom', label: '故障描述', type: 'textarea', span: 24 },
  {
    prop: 'level',
    label: '故障等级',
    type: 'select',
    options: meta.options('fault_levels'),
    defaultValue: 'medium',
  },
  { prop: 'assignee_id', label: '维修人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'assigned_date', label: '派工日期', type: 'date' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const completeVisible = ref(false)
const completeError = ref('')
const submitting = ref(false)
const completeTarget = ref<Record<string, unknown> | null>(null)
const repairerOptions = ref<EnumOption[]>([])
const completeForm = reactive<Record<string, unknown>>({
  repairer_id: null,
  repair_date: '',
  fault_reason: '',
  solution: '',
  parts_used: '',
  downtime_minutes: '0',
  cost: '0',
  result: '',
})

onMounted(async () => {
  repairerOptions.value = await employeeOptions().catch(() => [])
})

async function startTask(row: Record<string, unknown>): Promise<void> {
  try {
    await repairTaskApi.action(Number(row.id), 'start')
    ElMessage.success('已开始维修')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function cancelTask(row: Record<string, unknown>): Promise<void> {
  const confirmed = await ElMessageBox.confirm('取消后该维修任务不再执行。确认取消？', '取消确认', {
    type: 'warning',
    confirmButtonText: '确认取消',
    cancelButtonText: '再想想',
  }).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await repairTaskApi.action(Number(row.id), 'cancel', { reason: '' })
    ElMessage.success('已取消')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function openComplete(row: Record<string, unknown>): void {
  completeTarget.value = row
  completeError.value = ''
  completeForm.repairer_id = row.assignee_id ?? null
  completeForm.repair_date = new Date().toISOString().slice(0, 10)
  completeForm.fault_reason = ''
  completeForm.solution = ''
  completeForm.parts_used = ''
  completeForm.downtime_minutes = String(row.downtime_minutes ?? 0)
  completeForm.cost = '0'
  completeForm.result = ''
  completeVisible.value = true
}

async function submitComplete(): Promise<void> {
  const target = completeTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  completeError.value = ''
  try {
    await repairTaskApi.action(Number(target.id), 'complete', {
      repairer_id: completeForm.repairer_id || null,
      repair_date: completeForm.repair_date || null,
      fault_reason: completeForm.fault_reason,
      solution: completeForm.solution,
      parts_used: completeForm.parts_used,
      downtime_minutes: Number(completeForm.downtime_minutes || 0),
      cost: completeForm.cost || '0',
      result: completeForm.result,
    })
    ElMessage.success('维修已完成，维修记录已生成')
    completeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    completeError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>