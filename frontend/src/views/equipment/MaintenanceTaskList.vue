<template>
  <entity-list-page
    title="保养任务"
    entity-label="保养任务"
    description="保养任务是要执行的保养工作。点「开始保养」记录开工时间，点「完成保养」填写保养内容与结论——完成后系统会在同一事务里生成保养记录，不需要再手工补一条。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.maintenance_task.create', update: 'equipment.maintenance_task.update' }"
    search-placeholder="搜索任务编号或设备"
    default-ordering="-plan_date"
    :toggleable="false"
    :page-size="20"
    :action-width="280"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('task_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canExecute && row.status === 'pending'"
        link
        type="primary"
        size="small"
        @click="startTask(row, reload)"
      >
        开始保养
      </el-button>
      <el-button
        v-if="canExecute && (row.status === 'pending' || row.status === 'in_progress')"
        link
        type="success"
        size="small"
        @click="openComplete(row)"
      >
        完成保养
      </el-button>
      <el-button
        v-if="canUpdate && (row.status === 'pending' || row.status === 'in_progress')"
        link
        type="danger"
        size="small"
        @click="cancelTask(row, reload)"
      >
        取消
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="completeVisible" title="完成保养" width="640px" :close-on-click-modal="false">
    <el-alert
      v-if="completeError"
      type="error"
      :closable="false"
      show-icon
      :title="completeError"
      class="ys-form-error"
    />
    <el-form :model="completeForm" label-width="120px">
      <el-form-item label="保养人">
        <el-select v-model="completeForm.executor_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in executorOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="保养日期">
        <el-date-picker
          v-model="completeForm.maintain_date"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="保养内容">
        <el-input v-model="completeForm.content" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="保养结果">
        <el-input v-model="completeForm.result" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="验收合格">
        <el-switch v-model="completeForm.is_qualified" />
      </el-form-item>
      <el-form-item label="保养费用">
        <el-input v-model="completeForm.cost" placeholder="0" />
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
import { maintenanceTaskApi } from '@/api/endpoints'
import {
  employeeOptions,
  equipmentOptions,
  maintenanceItemOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = maintenanceTaskApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canExecute = computed(() => auth.hasPermission('equipment.maintenance_task.execute'))
const canUpdate = computed(() => auth.hasPermission('equipment.maintenance_task.update'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'primary'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'task_no', label: '任务编号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'item_name', label: '保养项目', width: 140 },
  { prop: 'plan_date', label: '计划日期', width: 120, sortable: true },
  { prop: 'status', label: '任务状态', width: 110 },
  { prop: 'assignee_name', label: '执行人', width: 110 },
  { prop: 'finished_at', label: '完成时间', width: 170 },
  { prop: 'result', label: '保养结论', minWidth: 160 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'status',
    label: '任务状态',
    type: 'select' as const,
    options: meta.options('task_statuses'),
  },
  {
    prop: 'assignee_id',
    label: '执行人',
    type: 'select' as const,
    optionsLoader: employeeOptions,
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'plan_no', label: '来源计划' },
  { prop: 'started_at', label: '开始时间' },
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
  { prop: 'plan_date', label: '计划日期', type: 'date', required: true },
  {
    prop: 'item_id',
    label: '保养项目',
    type: 'select',
    optionsLoader: maintenanceItemOptions,
  },
  { prop: 'assignee_id', label: '执行人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'result', label: '保养结论' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const completeVisible = ref(false)
const completeError = ref('')
const submitting = ref(false)
const completeTarget = ref<Record<string, unknown> | null>(null)
const executorOptions = ref<EnumOption[]>([])
const completeForm = reactive<Record<string, unknown>>({
  executor_id: null,
  maintain_date: '',
  content: '',
  result: '',
  is_qualified: true,
  cost: '0',
})

onMounted(async () => {
  executorOptions.value = await employeeOptions().catch(() => [])
})

async function startTask(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await maintenanceTaskApi.action(Number(row.id), 'start')
    ElMessage.success('已开始保养')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function cancelTask(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const confirmed = await ElMessageBox.confirm('取消后该任务不再需要执行。确认取消？', '取消确认', {
    type: 'warning',
    confirmButtonText: '确认取消',
    cancelButtonText: '再想想',
  }).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await maintenanceTaskApi.action(Number(row.id), 'cancel', { reason: '' })
    ElMessage.success('已取消')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function openComplete(row: Record<string, unknown>): void {
  completeTarget.value = row
  completeError.value = ''
  completeForm.executor_id = row.assignee_id ?? null
  completeForm.maintain_date = new Date().toISOString().slice(0, 10)
  completeForm.content = ''
  completeForm.result = ''
  completeForm.is_qualified = true
  completeForm.cost = '0'
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
    await maintenanceTaskApi.action(Number(target.id), 'complete', {
      executor_id: completeForm.executor_id || null,
      maintain_date: completeForm.maintain_date || null,
      content: completeForm.content,
      result: completeForm.result,
      is_qualified: Boolean(completeForm.is_qualified),
      cost: completeForm.cost || '0',
    })
    ElMessage.success('保养已完成，保养记录已生成')
    completeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    completeError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>