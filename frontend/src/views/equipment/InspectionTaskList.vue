<template>
  <entity-list-page
    title="点巡检任务"
    entity-label="点巡检任务"
    description="点巡检任务是要执行的检查工作，可挂多个点巡检项目。点「开始」记录开工时间，点「完成」结束任务；每一项的实测值与判定到「点巡检记录」里登记，判定异常的可一键转报修。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.inspection_task.create', update: 'equipment.inspection_task.update' }"
    search-placeholder="搜索任务编号或设备"
    default-ordering="-plan_date"
    :toggleable="false"
    :page-size="20"
    :action-width="260"
    ref="pageRef"
  >
    <template #column-task_type="{ row }">
      {{ row.task_type_display || meta.label('inspection_task_types', String(row.task_type)) }}
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
        开始
      </el-button>
      <el-button
        v-if="canExecute && (row.status === 'pending' || row.status === 'in_progress')"
        link
        type="success"
        size="small"
        @click="completeTask(row)"
      >
        完成
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
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { inspectionTaskApi } from '@/api/endpoints'
import {
  employeeOptions,
  equipmentOptions,
  inspectionItemOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'

const auth = useAuthStore()
const meta = useMetaStore()
const api = inspectionTaskApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canExecute = computed(() => auth.hasPermission('equipment.inspection_task.execute'))
const canUpdate = computed(() => auth.hasPermission('equipment.inspection_task.update'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'primary'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'task_no', label: '任务编号', width: 160, sortable: true },
  { prop: 'task_type', label: '任务类型', width: 100 },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'plan_date', label: '计划日期', width: 120, sortable: true },
  { prop: 'status', label: '任务状态', width: 110 },
  { prop: 'assignee_name', label: '执行人', width: 110 },
  { prop: 'item_names', label: '点巡检项目', minWidth: 200 },
  { prop: 'finished_at', label: '完成时间', width: 170 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'task_type',
    label: '任务类型',
    type: 'select' as const,
    options: meta.options('inspection_task_types'),
  },
  {
    prop: 'status',
    label: '任务状态',
    type: 'select' as const,
    options: meta.options('task_statuses'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'started_at', label: '开始时间' },
  { prop: 'result', label: '任务结论' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'task_type',
    label: '任务类型',
    type: 'select',
    options: meta.options('inspection_task_types'),
    defaultValue: 'point',
  },
  {
    prop: 'equipment_id',
    label: '设备',
    type: 'select',
    required: true,
    optionsLoader: equipmentOptions,
  },
  { prop: 'plan_date', label: '计划日期', type: 'date', required: true },
  { prop: 'assignee_id', label: '执行人', type: 'select', optionsLoader: employeeOptions },
  {
    prop: 'item_ids',
    label: '点巡检项目',
    type: 'select',
    multiple: true,
    optionsLoader: inspectionItemOptions,
    help: '可多选；记录按项目逐条登记',
  },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function startTask(row: Record<string, unknown>): Promise<void> {
  try {
    await inspectionTaskApi.action(Number(row.id), 'start')
    ElMessage.success('已开始')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function completeTask(row: Record<string, unknown>): Promise<void> {
  const result = await ElMessageBox.prompt('填写任务结论（例如：全部正常 / 2 项异常）', '完成点巡检任务', {
    confirmButtonText: '确认完成',
    cancelButtonText: '取消',
    inputValue: '',
  }).catch(() => null)
  if (!result) {
    return
  }
  try {
    await inspectionTaskApi.action(Number(row.id), 'complete', { result: result.value ?? '' })
    ElMessage.success('已完成')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function cancelTask(row: Record<string, unknown>): Promise<void> {
  const confirmed = await ElMessageBox.confirm('取消后该任务不再执行。确认取消？', '取消确认', {
    type: 'warning',
    confirmButtonText: '确认取消',
    cancelButtonText: '再想想',
  }).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await inspectionTaskApi.action(Number(row.id), 'cancel', { reason: '' })
    ElMessage.success('已取消')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>