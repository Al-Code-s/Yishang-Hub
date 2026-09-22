<template>
  <entity-list-page
    :title="title"
    entity-label="作业许可"
    :description="description"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.permit.create', update: 'ehs.permit.update' }"
    search-placeholder="搜索许可编号、作业内容或作业地点"
    default-ordering="-created_at"
    :toggleable="false"
    :page-size="20"
    :action-width="300"
    :initial-filters="{ permit_type: permitType }"
    :transform="transform"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('permit_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-risk_level="{ row }">
      <el-tag :type="riskTagType(String(row.risk_level))" size="small" effect="light">
        {{ row.risk_level_display || meta.label('permit_risk_levels', String(row.risk_level)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canApprove && row.status === 'applied'"
        link
        type="primary"
        size="small"
        @click="openApprove(row)"
      >
        批准
      </el-button>
      <el-button
        v-if="canApprove && row.status === 'applied'"
        link
        type="danger"
        size="small"
        @click="openReject(row)"
      >
        驳回
      </el-button>
      <el-button
        v-if="canExecute && row.status === 'approved'"
        link
        type="primary"
        size="small"
        @click="startWork(row, reload)"
      >
        开始作业
      </el-button>
      <el-button
        v-if="canExecute && row.status === 'working'"
        link
        type="success"
        size="small"
        @click="openFinish(row)"
      >
        完工
      </el-button>
      <el-button
        v-if="canAccept && row.status === 'finished'"
        link
        type="success"
        size="small"
        @click="openAccept(row)"
      >
        验收
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="approveVisible" title="批准作业许可" width="620px" :close-on-click-modal="false">
    <el-alert v-if="approveError" type="error" :closable="false" show-icon :title="approveError" class="ys-form-error" />
    <el-form :model="approveForm" label-width="130px">
      <el-form-item label="审批人">
        <el-select v-model="approveForm.approver_id" clearable filterable style="width: 100%">
          <el-option v-for="option in employeeChoiceOptions" :key="String(option.value)" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="监护人">
        <el-select v-model="approveForm.guardian_id" clearable filterable style="width: 100%">
          <el-option v-for="option in employeeChoiceOptions" :key="String(option.value)" :label="option.label" :value="option.value" />
        </el-select>
        <div v-if="guardianRequired" class="ys-muted">本类作业属于安全硬要求，批准时必须指定监护人。</div>
      </el-form-item>
      <el-form-item label="审批说明">
        <el-input v-model="approveForm.note as string" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="approveVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitApprove">确认批准</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="rejectVisible" title="驳回作业许可" width="600px" :close-on-click-modal="false">
    <el-alert v-if="rejectError" type="error" :closable="false" show-icon :title="rejectError" class="ys-form-error" />
    <el-form :model="rejectForm" label-width="130px">
      <el-form-item label="驳回理由" required>
        <el-input v-model="rejectForm.reason as string" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="审批人">
        <el-select v-model="rejectForm.approver_id" clearable filterable style="width: 100%">
          <el-option v-for="option in employeeChoiceOptions" :key="String(option.value)" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="rejectVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitReject">确认驳回</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="finishVisible" title="作业完工" width="600px" :close-on-click-modal="false">
    <el-alert v-if="finishError" type="error" :closable="false" show-icon :title="finishError" class="ys-form-error" />
    <el-form :model="finishForm" label-width="130px">
      <el-form-item label="完工说明">
        <el-input v-model="finishForm.result as string" type="textarea" :rows="3" placeholder="例如：动火作业结束，现场已清理并恢复防护" />
      </el-form-item>
      <el-form-item label="操作人">
        <el-select v-model="finishForm.operator_id" clearable filterable style="width: 100%">
          <el-option v-for="option in employeeChoiceOptions" :key="String(option.value)" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="finishVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitFinish">确认完工</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="acceptVisible" title="现场验收" width="600px" :close-on-click-modal="false">
    <el-alert v-if="acceptError" type="error" :closable="false" show-icon :title="acceptError" class="ys-form-error" />
    <el-form :model="acceptForm" label-width="130px">
      <el-form-item label="验收结论" required>
        <el-input v-model="acceptForm.result as string" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="验收人">
        <el-select v-model="acceptForm.accepted_by_id" clearable filterable style="width: 100%">
          <el-option v-for="option in employeeChoiceOptions" :key="String(option.value)" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="acceptVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitAccept">确认验收</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { workPermitApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'
import type { EnumOption } from '@/types/models'

const props = defineProps<{ title: string; description: string; permitType: string }>()

const auth = useAuthStore()
const meta = useMetaStore()
const api = workPermitApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canApprove = computed(() => auth.hasPermission('ehs.permit.approve'))
const canExecute = computed(() => auth.hasPermission('ehs.permit.execute'))
const canAccept = computed(() => auth.hasPermission('ehs.permit.accept'))
const guardianRequired = computed(() =>
  ['hot_work', 'explosion_proof', 'confined_space'].includes(props.permitType),
)

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'accepted') return 'success'
  if (status === 'working') return 'primary'
  if (status === 'rejected') return 'danger'
  if (status === 'applied') return 'warning'
  return 'info'
}

function riskTagType(level: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'permit_no', label: '许可编号', width: 160, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'risk_level', label: '风险等级', width: 100 },
  { prop: 'work_content', label: '作业内容', minWidth: 180 },
  { prop: 'work_location', label: '作业地点', width: 150 },
  { prop: 'applicant_name', label: '申请人', width: 110 },
  { prop: 'department_name', label: '申请部门', width: 140 },
  {
    prop: 'start_at',
    label: '计划开始',
    width: 170,
    formatter: (row) => formatDateTime(String(row.start_at ?? '')),
  },
  {
    prop: 'end_at',
    label: '计划结束',
    width: 170,
    formatter: (row) => formatDateTime(String(row.end_at ?? '')),
  },
  { prop: 'approver_name', label: '审批人', width: 110 },
  { prop: 'guardian_name', label: '监护人', width: 110 },
  { prop: 'accepted_by_name', label: '验收人', width: 110 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('permit_statuses') },
  { prop: 'risk_level', label: '风险等级', type: 'select' as const, options: meta.options('permit_risk_levels') },
  { prop: 'department_id', label: '申请部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'protective_measures', label: '安全防护措施' },
  { prop: 'approved_at', label: '批准时间' },
  { prop: 'started_at', label: '实际开始时间' },
  { prop: 'finished_at', label: '实际完工时间' },
  { prop: 'accepted_at', label: '验收时间' },
  { prop: 'result', label: '审批/完工/验收结论' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'permit_no', label: '许可编号', onlyOnUpdate: true, help: '留空时由系统按编号规则自动生成' },
  { prop: 'work_content', label: '作业内容', required: true, span: 24 },
  { prop: 'work_location', label: '作业地点', required: true },
  { prop: 'risk_level', label: '风险等级', type: 'select', options: meta.options('permit_risk_levels'), defaultValue: 'medium' },
  { prop: 'applicant_id', label: '申请人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'department_id', label: '申请部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'start_at', label: '计划开始时间', type: 'date' },
  { prop: 'end_at', label: '计划结束时间', type: 'date' },
  { prop: 'protective_measures', label: '安全防护措施', type: 'textarea', span: 24, help: '写明隔离、置换、气体检测、消防器材等具体措施' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

function transform(payload: Record<string, unknown>): Record<string, unknown> {
  return { ...payload, permit_type: props.permitType }
}

const approveVisible = ref(false)
const approveError = ref('')
const rejectVisible = ref(false)
const rejectError = ref('')
const finishVisible = ref(false)
const finishError = ref('')
const acceptVisible = ref(false)
const acceptError = ref('')
const submitting = ref(false)
const activeTarget = ref<Record<string, unknown> | null>(null)
const employeeChoiceOptions = ref<EnumOption[]>([])

const approveForm = reactive<Record<string, unknown>>({ approver_id: null, guardian_id: null, note: '' })
const rejectForm = reactive<Record<string, unknown>>({ reason: '', approver_id: null })
const finishForm = reactive<Record<string, unknown>>({ result: '', operator_id: null })
const acceptForm = reactive<Record<string, unknown>>({ result: '', accepted_by_id: null })

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
})

function openApprove(row: Record<string, unknown>): void {
  activeTarget.value = row
  approveError.value = ''
  approveForm.approver_id = null
  approveForm.guardian_id = row.guardian_id ?? null
  approveForm.note = ''
  approveVisible.value = true
}

function openReject(row: Record<string, unknown>): void {
  activeTarget.value = row
  rejectError.value = ''
  rejectForm.reason = ''
  rejectForm.approver_id = null
  rejectVisible.value = true
}

function openFinish(row: Record<string, unknown>): void {
  activeTarget.value = row
  finishError.value = ''
  finishForm.result = ''
  finishForm.operator_id = row.applicant_id ?? null
  finishVisible.value = true
}

function openAccept(row: Record<string, unknown>): void {
  activeTarget.value = row
  acceptError.value = ''
  acceptForm.result = ''
  acceptForm.accepted_by_id = null
  acceptVisible.value = true
}

async function runAction(
  name: string,
  payload: Record<string, unknown>,
  close: () => void,
  setError: (message: string) => void,
  successText: string,
): Promise<void> {
  const target = activeTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  try {
    await workPermitApi.action(Number(target.id), name, payload)
    ElMessage.success(successText)
    close()
    await pageRef.value?.reload()
  } catch (error) {
    setError(error instanceof ApiError ? error.message : '操作失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

function submitApprove(): void {
  if (guardianRequired.value && !approveForm.guardian_id) {
    approveError.value = '该类作业必须指定监护人。'
    return
  }
  void runAction(
    'approve',
    { approver_id: approveForm.approver_id, guardian_id: approveForm.guardian_id, note: approveForm.note },
    () => { approveVisible.value = false },
    (message) => { approveError.value = message },
    '作业许可已批准',
  )
}

function submitReject(): void {
  if (!String(rejectForm.reason ?? '').trim()) {
    rejectError.value = '驳回作业许可必须填写理由。'
    return
  }
  void runAction(
    'reject',
    { reason: rejectForm.reason, approver_id: rejectForm.approver_id },
    () => { rejectVisible.value = false },
    (message) => { rejectError.value = message },
    '作业许可已驳回',
  )
}

async function startWork(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await workPermitApi.action(Number(row.id), 'start', { operator_id: row.applicant_id ?? null })
    ElMessage.success('已开始作业')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function submitFinish(): void {
  void runAction(
    'finish',
    { result: finishForm.result, operator_id: finishForm.operator_id },
    () => { finishVisible.value = false },
    (message) => { finishError.value = message },
    '作业已完工',
  )
}

function submitAccept(): void {
  if (!String(acceptForm.result ?? '').trim()) {
    acceptError.value = '验收作业许可必须填写结论。'
    return
  }
  void runAction(
    'accept',
    { result: acceptForm.result, accepted_by_id: acceptForm.accepted_by_id },
    () => { acceptVisible.value = false },
    (message) => { acceptError.value = message },
    '作业许可已验收',
  )
}
</script>
