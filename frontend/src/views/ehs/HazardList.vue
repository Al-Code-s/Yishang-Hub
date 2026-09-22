<template>
  <entity-list-page
    title="隐患排查"
    entity-label="隐患"
    description="隐患从上报到关闭要走完整闭环：待整改 → 开始整改 → 提交验收 → 验收。验收不通过会退回「整改中」，不合格隐患不会被静默销账；超过整改期限的隐患会在列表上标记「已超期」。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.hazard.create', update: 'ehs.hazard.update' }"
    search-placeholder="搜索隐患编号、标题、描述或位置"
    default-ordering="-found_date"
    :toggleable="false"
    :page-size="20"
    :action-width="300"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('hazard_statuses', String(row.status)) }}
      </el-tag>
      <el-tag v-if="row.is_overdue" type="danger" size="small" effect="dark" class="ys-ml-4">已超期</el-tag>
    </template>
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ row.level_display || meta.label('hazard_levels', String(row.level)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canRectify && (row.status === 'reported' || row.status === 'verifying')"
        link
        type="primary"
        size="small"
        @click="openRectify(row)"
      >
        开始整改
      </el-button>
      <el-button
        v-if="canRectify && row.status === 'rectifying'"
        link
        type="primary"
        size="small"
        @click="submitVerify(row, reload)"
      >
        提交验收
      </el-button>
      <el-button
        v-if="canVerify && row.status === 'verifying'"
        link
        type="success"
        size="small"
        @click="openVerify(row)"
      >
        验收
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="rectifyVisible" title="开始整改" width="600px" :close-on-click-modal="false">
    <el-alert v-if="rectifyError" type="error" :closable="false" show-icon :title="rectifyError" class="ys-form-error" />
    <el-form :model="rectifyForm" label-width="120px">
      <el-form-item label="整改措施" required>
        <el-input v-model="rectifyForm.measure as string" type="textarea" :rows="3" placeholder="写明具体整改动作与完成标准" />
      </el-form-item>
      <el-form-item label="整改人">
        <el-select v-model="rectifyForm.rectified_by_id" clearable filterable style="width: 100%">
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
      <el-button @click="rectifyVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitRectify">确认</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="verifyVisible" title="隐患验收" width="600px" :close-on-click-modal="false">
    <el-alert v-if="verifyError" type="error" :closable="false" show-icon :title="verifyError" class="ys-form-error" />
    <el-form :model="verifyForm" label-width="120px">
      <el-form-item label="验收结论" required>
        <el-input v-model="verifyForm.result as string" type="textarea" :rows="3" placeholder="写明现场复核情况" />
      </el-form-item>
      <el-form-item label="验收结果">
        <el-radio-group v-model="verifyForm.passed as boolean">
          <el-radio :value="true">通过并关闭</el-radio>
          <el-radio :value="false">不通过，退回整改</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="验收人">
        <el-select v-model="verifyForm.verified_by_id" clearable filterable style="width: 100%">
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
      <el-button @click="verifyVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitVerifyForm">确认验收</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { hazardRecordApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = hazardRecordApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canRectify = computed(() => auth.hasPermission('ehs.hazard.rectify'))
const canVerify = computed(() => auth.hasPermission('ehs.hazard.verify'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'rectifying') return 'primary'
  if (status === 'verifying') return 'warning'
  return 'danger'
}

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (level === 'major') return 'danger'
  if (level === 'high') return 'warning'
  if (level === 'medium') return 'primary'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'hazard_no', label: '隐患编号', width: 150, sortable: true },
  { prop: 'title', label: '隐患标题', minWidth: 180 },
  { prop: 'level', label: '隐患级别', width: 100 },
  { prop: 'status', label: '状态', width: 160 },
  { prop: 'source', label: '来源', width: 110 },
  { prop: 'location', label: '位置', width: 150 },
  { prop: 'department_name', label: '责任部门', width: 140 },
  { prop: 'reported_by_name', label: '上报人', width: 110 },
  { prop: 'found_date', label: '发现日期', width: 120, sortable: true },
  { prop: 'due_date', label: '整改期限', width: 120, sortable: true },
  { prop: 'rectified_date', label: '整改完成日期', width: 140 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'level', label: '隐患级别', type: 'select' as const, options: meta.options('hazard_levels') },
  { prop: 'source', label: '隐患来源', type: 'select' as const, options: meta.options('hazard_sources') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('hazard_statuses') },
  { prop: 'department_id', label: '责任部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'description', label: '隐患描述' },
  { prop: 'rectify_measure', label: '整改措施' },
  { prop: 'rectified_by_name', label: '整改人' },
  { prop: 'verify_result', label: '验收结论' },
  { prop: 'verified_by_name', label: '验收人' },
  { prop: 'verified_date', label: '验收日期' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'hazard_no', label: '隐患编号', onlyOnUpdate: true, help: '留空时由系统按编号规则自动生成' },
  { prop: 'title', label: '隐患标题', required: true, span: 24 },
  { prop: 'level', label: '隐患级别', type: 'select', required: true, options: meta.options('hazard_levels'), defaultValue: 'low' },
  { prop: 'source', label: '隐患来源', type: 'select', options: meta.options('hazard_sources'), defaultValue: 'inspection' },
  { prop: 'location', label: '隐患位置' },
  { prop: 'department_id', label: '责任部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'reported_by_id', label: '上报人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'found_date', label: '发现日期', type: 'date' },
  { prop: 'due_date', label: '整改期限', type: 'date' },
  { prop: 'description', label: '隐患描述', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const rectifyVisible = ref(false)
const rectifyError = ref('')
const verifyVisible = ref(false)
const verifyError = ref('')
const submitting = ref(false)
const rectifyTarget = ref<Record<string, unknown> | null>(null)
const verifyTarget = ref<Record<string, unknown> | null>(null)
const employeeChoiceOptions = ref<EnumOption[]>([])

const rectifyForm = reactive<Record<string, unknown>>({ measure: '', rectified_by_id: null })
const verifyForm = reactive<Record<string, unknown>>({ result: '', passed: true, verified_by_id: null })

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
})

function openRectify(row: Record<string, unknown>): void {
  rectifyTarget.value = row
  rectifyError.value = ''
  rectifyForm.measure = ''
  rectifyForm.rectified_by_id = null
  rectifyVisible.value = true
}

async function submitRectify(): Promise<void> {
  const target = rectifyTarget.value
  if (!target) {
    return
  }
  if (!String(rectifyForm.measure ?? '').trim()) {
    rectifyError.value = '开始整改必须填写整改措施。'
    return
  }
  submitting.value = true
  rectifyError.value = ''
  try {
    await hazardRecordApi.action(Number(target.id), 'rectify', {
      measure: rectifyForm.measure,
      rectified_by_id: rectifyForm.rectified_by_id,
    })
    ElMessage.success('已进入整改中')
    rectifyVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    rectifyError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function submitVerify(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await hazardRecordApi.action(Number(row.id), 'submit-verify', {})
    ElMessage.success('已提交验收')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function openVerify(row: Record<string, unknown>): void {
  verifyTarget.value = row
  verifyError.value = ''
  verifyForm.result = ''
  verifyForm.passed = true
  verifyForm.verified_by_id = null
  verifyVisible.value = true
}

async function submitVerifyForm(): Promise<void> {
  const target = verifyTarget.value
  if (!target) {
    return
  }
  if (!String(verifyForm.result ?? '').trim()) {
    verifyError.value = '验收必须填写验收结论。'
    return
  }
  submitting.value = true
  verifyError.value = ''
  try {
    await hazardRecordApi.action(Number(target.id), 'verify', {
      result: verifyForm.result,
      passed: Boolean(verifyForm.passed),
      verified_by_id: verifyForm.verified_by_id,
    })
    ElMessage.success(verifyForm.passed ? '验收通过，隐患已关闭' : '验收不通过，已退回整改')
    verifyVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    verifyError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
