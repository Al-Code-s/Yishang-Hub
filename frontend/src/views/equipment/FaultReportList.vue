<template>
  <entity-list-page
    title="故障保修"
    entity-label="故障保修"
    description="设备出故障先在这里登记报修单（报修单号自动生成）。未派工的报修单可以「派工」生成维修任务，也可以直接「关闭」（例如现场已自行处理）。维修任务完成后，报修单会自动关闭。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.fault_report.create', update: 'equipment.fault_report.update' }"
    search-placeholder="搜索报修单号、设备或故障描述"
    default-ordering="-reported_at"
    :toggleable="false"
    :page-size="20"
    :action-width="240"
    ref="pageRef"
  >
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ row.level_display || meta.label('fault_levels', String(row.level)) }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('fault_report_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canDispatch && row.status !== 'closed' && row.status !== 'cancelled'"
        link
        type="primary"
        size="small"
        @click="openDispatch(row)"
      >
        派工
      </el-button>
      <el-button
        v-if="canClose && row.status !== 'closed' && row.status !== 'cancelled'"
        link
        type="warning"
        size="small"
        @click="closeReport(row)"
      >
        关闭
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="dispatchVisible" title="故障派工" width="620px" :close-on-click-modal="false">
    <el-alert
      v-if="dispatchError"
      type="error"
      :closable="false"
      show-icon
      :title="dispatchError"
      class="ys-form-error"
    />
    <el-form :model="dispatchForm" label-width="110px">
      <el-form-item label="维修人">
        <el-select v-model="dispatchForm.assignee_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in assigneeOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="故障等级">
        <el-select v-model="dispatchForm.level" clearable style="width: 100%">
          <el-option
            v-for="option in meta.options('fault_levels')"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="派工日期">
        <el-date-picker
          v-model="dispatchForm.assigned_date"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="故障描述">
        <el-input v-model="dispatchForm.symptom" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="dispatchForm.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dispatchVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitDispatch">确认派工</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { faultReportApi } from '@/api/endpoints'
import { employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = faultReportApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canDispatch = computed(() => auth.hasPermission('equipment.repair_task.create'))
const canClose = computed(() => auth.hasPermission('equipment.fault_report.update'))

function levelTagType(level: string): 'info' | 'warning' | 'danger' {
  if (level === 'critical' || level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'info'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'repairing') return 'primary'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'report_no', label: '报修单号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'level', label: '故障等级', width: 100 },
  { prop: 'description', label: '故障现象', minWidth: 200 },
  { prop: 'reporter_name', label: '报修人', width: 110 },
  { prop: 'reported_at', label: '报修时间', width: 170 },
  { prop: 'status', label: '处理状态', width: 110 },
  { prop: 'closed_at', label: '关闭时间', width: 170 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'status',
    label: '处理状态',
    type: 'select' as const,
    options: meta.options('fault_report_statuses'),
  },
  {
    prop: 'level',
    label: '故障等级',
    type: 'select' as const,
    options: meta.options('fault_levels'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
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
  {
    prop: 'level',
    label: '故障等级',
    type: 'select',
    options: meta.options('fault_levels'),
    defaultValue: 'medium',
  },
  { prop: 'description', label: '故障现象', type: 'textarea', span: 24, required: true },
  { prop: 'reporter_id', label: '报修人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const dispatchVisible = ref(false)
const dispatchError = ref('')
const submitting = ref(false)
const dispatchTarget = ref<Record<string, unknown> | null>(null)
const assigneeOptions = ref<EnumOption[]>([])
const dispatchForm = reactive<Record<string, unknown>>({
  assignee_id: null,
  level: 'medium',
  assigned_date: '',
  symptom: '',
  remark: '',
})

onMounted(async () => {
  assigneeOptions.value = await employeeOptions().catch(() => [])
})

function openDispatch(row: Record<string, unknown>): void {
  dispatchTarget.value = row
  dispatchError.value = ''
  dispatchForm.assignee_id = null
  dispatchForm.level = String(row.level ?? 'medium')
  dispatchForm.assigned_date = new Date().toISOString().slice(0, 10)
  dispatchForm.symptom = String(row.description ?? '')
  dispatchForm.remark = ''
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
    await faultReportApi.action(Number(target.id), 'dispatch', {
      assignee_id: dispatchForm.assignee_id || null,
      level: dispatchForm.level || null,
      assigned_date: dispatchForm.assigned_date || null,
      symptom: dispatchForm.symptom,
      remark: dispatchForm.remark,
    })
    ElMessage.success('已派工，维修任务已生成')
    dispatchVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dispatchError.value = error instanceof ApiError ? error.message : '派工失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function closeReport(row: Record<string, unknown>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '关闭后该报修单不再需要维修。确认关闭？',
    '关闭确认',
    { type: 'warning', confirmButtonText: '确认关闭', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await faultReportApi.action(Number(row.id), 'close')
    ElMessage.success('已关闭')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>