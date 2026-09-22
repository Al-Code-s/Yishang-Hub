<template>
  <entity-list-page
    title="事故处理"
    entity-label="事故记录"
    description="事故从上报到关闭的状态链条：已上报 → 调查中 → 已整改 → 已关闭。每一步都必须填内容——调查要指定调查负责人，整改要写措施，关闭要写调查结论，不允许跳过任何一步。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.accident.create', update: 'ehs.accident.update' }"
    search-placeholder="搜索事故编号、标题、描述或位置"
    default-ordering="-occurred_at"
    :toggleable="false"
    :page-size="20"
    :action-width="240"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('accident_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canHandle && row.status === 'reported'"
        link
        type="primary"
        size="small"
        @click="openInvestigate(row)"
      >
        开始调查
      </el-button>
      <el-button
        v-if="canHandle && row.status === 'investigating'"
        link
        type="primary"
        size="small"
        @click="openRectify(row)"
      >
        登记整改
      </el-button>
      <el-button
        v-if="canHandle && row.status === 'rectified'"
        link
        type="success"
        size="small"
        @click="openClose(row)"
      >
        关闭事故
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="investigateVisible" title="开始事故调查" width="560px" :close-on-click-modal="false">
    <el-alert v-if="investigateError" type="error" :closable="false" show-icon :title="investigateError" class="ys-form-error" />
    <el-form :model="investigateForm" label-width="130px">
      <el-form-item label="调查负责人">
        <el-select v-model="investigateForm.investigator_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="investigateVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitInvestigate">确认</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="rectifyVisible" title="登记整改与预防措施" width="600px" :close-on-click-modal="false">
    <el-alert v-if="rectifyError" type="error" :closable="false" show-icon :title="rectifyError" class="ys-form-error" />
    <el-form :model="rectifyForm" label-width="130px">
      <el-form-item label="原因分析">
        <el-input v-model="rectifyForm.causes as string" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="整改与预防措施" required>
        <el-input v-model="rectifyForm.measures as string" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="rectifyVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitRectify">确认</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="closeVisible" title="关闭事故" width="600px" :close-on-click-modal="false">
    <el-alert v-if="closeError" type="error" :closable="false" show-icon :title="closeError" class="ys-form-error" />
    <el-form :model="closeForm" label-width="130px">
      <el-form-item label="调查结论" required>
        <el-input v-model="closeForm.result as string" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="关闭日期">
        <el-date-picker v-model="closeForm.closed_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="closeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitClose">确认关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { accidentRecordApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = accidentRecordApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canHandle = computed(() => auth.hasPermission('ehs.accident.handle'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'investigating') return 'warning'
  if (status === 'rectified') return 'primary'
  return 'danger'
}

const columns: ProTableColumn[] = [
  { prop: 'accident_no', label: '事故编号', width: 150, sortable: true },
  { prop: 'title', label: '事故标题', minWidth: 180 },
  { prop: 'category', label: '事故类别', width: 110 },
  { prop: 'level', label: '事故级别', width: 100 },
  { prop: 'status', label: '状态', width: 100 },
  {
    prop: 'occurred_at',
    label: '发生时间',
    width: 170,
    sortable: true,
    formatter: (row) => formatDateTime(String(row.occurred_at ?? '')),
  },
  { prop: 'location', label: '发生地点', width: 150 },
  { prop: 'department_name', label: '责任部门', width: 140 },
  { prop: 'injured_count', label: '受伤人数', width: 110 },
  { prop: 'lost_days', label: '损失工日', width: 110 },
  {
    prop: 'loss_amount',
    label: '直接损失',
    width: 120,
    formatter: (row) => formatAmount(row.loss_amount as string),
  },
  { prop: 'investigator_name', label: '调查负责人', width: 130 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'category', label: '事故类别', type: 'select' as const, options: meta.options('accident_categories') },
  { prop: 'level', label: '事故级别', type: 'select' as const, options: meta.options('accident_levels') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('accident_statuses') },
  { prop: 'department_id', label: '责任部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'description', label: '事故经过' },
  { prop: 'causes', label: '原因分析' },
  { prop: 'measures', label: '整改与预防措施' },
  { prop: 'investigation_result', label: '调查结论' },
  { prop: 'reporter_name', label: '上报人' },
  { prop: 'closed_date', label: '关闭日期' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'accident_no', label: '事故编号', onlyOnUpdate: true, help: '留空时由系统按编号规则自动生成' },
  { prop: 'title', label: '事故标题', required: true, span: 24 },
  {
    prop: 'category',
    label: '事故类别',
    type: 'select',
    required: true,
    options: meta.options('accident_categories'),
    defaultValue: 'injury',
  },
  { prop: 'level', label: '事故级别', type: 'select', options: meta.options('accident_levels'), defaultValue: 'minor' },
  { prop: 'occurred_at', label: '发生时间', type: 'date', required: true },
  { prop: 'location', label: '发生地点' },
  { prop: 'department_id', label: '责任部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'injured_count', label: '受伤人数', type: 'number', defaultValue: 0 },
  { prop: 'lost_days', label: '损失工日', type: 'number', defaultValue: 0 },
  { prop: 'loss_amount', label: '直接经济损失', type: 'decimal', defaultValue: '0' },
  { prop: 'reporter_id', label: '上报人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'description', label: '事故经过', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const investigateVisible = ref(false)
const investigateError = ref('')
const rectifyVisible = ref(false)
const rectifyError = ref('')
const closeVisible = ref(false)
const closeError = ref('')
const submitting = ref(false)
const investigateTarget = ref<Record<string, unknown> | null>(null)
const rectifyTarget = ref<Record<string, unknown> | null>(null)
const closeTarget = ref<Record<string, unknown> | null>(null)
const employeeChoiceOptions = ref<EnumOption[]>([])

const investigateForm = reactive<Record<string, unknown>>({ investigator_id: null })
const rectifyForm = reactive<Record<string, unknown>>({ causes: '', measures: '' })
const closeForm = reactive<Record<string, unknown>>({ result: '', closed_date: '' })

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
})

function openInvestigate(row: Record<string, unknown>): void {
  investigateTarget.value = row
  investigateError.value = ''
  investigateForm.investigator_id = null
  investigateVisible.value = true
}

function openRectify(row: Record<string, unknown>): void {
  rectifyTarget.value = row
  rectifyError.value = ''
  rectifyForm.causes = String(row.causes ?? '')
  rectifyForm.measures = ''
  rectifyVisible.value = true
}

function openClose(row: Record<string, unknown>): void {
  closeTarget.value = row
  closeError.value = ''
  closeForm.result = String(row.investigation_result ?? '')
  closeForm.closed_date = ''
  closeVisible.value = true
}

async function submitInvestigate(): Promise<void> {
  const target = investigateTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  investigateError.value = ''
  try {
    await accidentRecordApi.action(Number(target.id), 'investigate', {
      investigator_id: investigateForm.investigator_id,
    })
    ElMessage.success('已进入调查中')
    investigateVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    investigateError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function submitRectify(): Promise<void> {
  const target = rectifyTarget.value
  if (!target) {
    return
  }
  if (!String(rectifyForm.measures ?? '').trim()) {
    rectifyError.value = '登记整改必须填写整改措施。'
    return
  }
  submitting.value = true
  rectifyError.value = ''
  try {
    await accidentRecordApi.action(Number(target.id), 'rectify', {
      causes: rectifyForm.causes,
      measures: rectifyForm.measures,
    })
    ElMessage.success('已登记整改')
    rectifyVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    rectifyError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function submitClose(): Promise<void> {
  const target = closeTarget.value
  if (!target) {
    return
  }
  if (!String(closeForm.result ?? '').trim()) {
    closeError.value = '关闭事故必须填写调查结论。'
    return
  }
  submitting.value = true
  closeError.value = ''
  try {
    await accidentRecordApi.action(Number(target.id), 'close', {
      result: closeForm.result,
      closed_date: closeForm.closed_date || null,
    })
    ElMessage.success('事故已关闭')
    closeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    closeError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
