<template>
  <entity-list-page
    title="质量报警"
    entity-label="质量报警"
    description="质量报警由检验单判定不合格时自动生成，不允许手工伪造来源；处理闭环是：待处理 → 处理中 → 已关闭。关闭时必须写清处理说明，避免「点一下就算处理完」。报警可以在处理过程中沉淀成知识库条目，把这次的原因与措施留成下次的依据。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'qms.alert.handle', update: 'qms.alert.handle' }"
    search-placeholder="搜索报警编号、主题、批次号或检验单号"
    default-ordering="-id"
    :toggleable="false"
    :page-size="20"
    :action-width="320"
    ref="pageRef"
  >
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ meta.label('quality_alert_levels', String(row.level)) }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('quality_alert_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canHandle && row.status === 'open'"
        link
        type="primary"
        size="small"
        @click="openHandle(row)"
      >
        开始处理
      </el-button>
      <el-button
        v-if="canClose && row.status !== 'closed'"
        link
        type="success"
        size="small"
        @click="openClose(row)"
      >
        关闭
      </el-button>
      <el-button
        v-if="canCreateIssue"
        link
        type="warning"
        size="small"
        @click="openIssue(row)"
      >
        沉淀知识库
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="handleVisible" title="开始处理质量报警" width="520px" :close-on-click-modal="false">
    <el-alert
      v-if="dialogError"
      type="error"
      :closable="false"
      show-icon
      :title="dialogError"
      class="ys-form-error"
    />
    <el-form label-width="110px">
      <el-form-item label="处理人">
        <el-select v-model="handleForm.handler_id" clearable filterable style="width: 100%">
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
      <el-button @click="handleVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitHandle">确认</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="closeVisible" title="关闭质量报警" width="620px" :close-on-click-modal="false">
    <el-alert
      v-if="dialogError"
      type="error"
      :closable="false"
      show-icon
      :title="dialogError"
      class="ys-form-error"
    />
    <el-form label-width="110px">
      <el-form-item label="处理说明" required>
        <el-input
          v-model="closeForm.remark as string"
          type="textarea"
          :rows="4"
          placeholder="写明查到的原因、采取的措施与验证结果"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="closeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitClose">确认关闭</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="issueVisible"
    title="沉淀成质量问题知识库"
    width="680px"
    :close-on-click-modal="false"
  >
    <el-alert
      v-if="dialogError"
      type="error"
      :closable="false"
      show-icon
      :title="dialogError"
      class="ys-form-error"
    />
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="保存后会生成一条「草稿」状态的知识库条目，并保留到本报警的来源链路。"
      class="ys-form-error"
    />
    <el-form label-width="110px">
      <el-form-item label="问题标题" required>
        <el-input v-model="issueForm.title as string" placeholder="一句话说明问题" />
      </el-form-item>
      <el-form-item label="问题分类">
        <el-select v-model="issueForm.category" clearable style="width: 100%">
          <el-option
            v-for="option in meta.options('quality_issue_categories')"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="严重程度">
        <el-select v-model="issueForm.severity" clearable placeholder="默认沿用报警级别" style="width: 100%">
          <el-option
            v-for="option in meta.options('quality_alert_levels')"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="原因分析">
        <el-input v-model="issueForm.cause as string" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="纠正措施">
        <el-input v-model="issueForm.corrective_action as string" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="预防措施">
        <el-input v-model="issueForm.preventive_action as string" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="issueVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitIssue">保存草稿</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { qualityAlertApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = qualityAlertApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canHandle = computed(() => auth.hasPermission('qms.alert.handle'))
const canClose = computed(() => auth.hasPermission('qms.alert.close'))
const canCreateIssue = computed(() => auth.hasPermission('qms.issue.create'))

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (level === 'critical') return 'danger'
  if (level === 'major') return 'warning'
  return 'info'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'handling') return 'warning'
  return 'danger'
}

const columns: ProTableColumn[] = [
  { prop: 'alert_no', label: '报警编号', width: 160, sortable: true },
  { prop: 'level', label: '报警级别', width: 100 },
  { prop: 'status', label: '处理状态', width: 100 },
  { prop: 'title', label: '报警主题', minWidth: 220 },
  { prop: 'order_no', label: '来源检验单', width: 160 },
  { prop: 'material_name', label: '物料', minWidth: 140 },
  { prop: 'batch_no', label: '批次号', width: 130 },
  { prop: 'handler_name', label: '处理人', width: 110 },
  { prop: 'created_at', label: '生成时间', width: 170, sortable: true },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'level',
    label: '报警级别',
    type: 'select' as const,
    options: meta.options('quality_alert_levels'),
  },
  {
    prop: 'status',
    label: '处理状态',
    type: 'select' as const,
    options: meta.options('quality_alert_statuses'),
  },
  { prop: 'batch_no', label: '批次号', type: 'text' as const },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'description', label: '报警说明' },
  { prop: 'handled_at', label: '开始处理时间' },
  { prop: 'close_remark', label: '关闭说明' },
  { prop: 'closed_at', label: '关闭时间' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'alert_no', label: '报警编号', onlyOnUpdate: true, help: '留空时由系统按编号规则自动生成' },
  { prop: 'title', label: '报警主题', required: true, span: 24 },
  {
    prop: 'level',
    label: '报警级别',
    type: 'select',
    required: true,
    options: meta.options('quality_alert_levels'),
    defaultValue: 'major',
  },
  { prop: 'batch_no', label: '批次号' },
  { prop: 'description', label: '报警说明', type: 'textarea', span: 24 },
])

const handleVisible = ref(false)
const closeVisible = ref(false)
const issueVisible = ref(false)
const dialogError = ref('')
const submitting = ref(false)
const handleTarget = ref<Record<string, unknown> | null>(null)
const closeTarget = ref<Record<string, unknown> | null>(null)
const issueTarget = ref<Record<string, unknown> | null>(null)
const employeeChoiceOptions = ref<EnumOption[]>([])

const handleForm = reactive<Record<string, unknown>>({ handler_id: null })
const closeForm = reactive<Record<string, unknown>>({ remark: '' })
const issueForm = reactive<Record<string, unknown>>({
  title: '',
  category: 'material',
  severity: '',
  cause: '',
  corrective_action: '',
  preventive_action: '',
})

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
})

function openHandle(row: Record<string, unknown>): void {
  handleTarget.value = row
  dialogError.value = ''
  handleForm.handler_id = null
  handleVisible.value = true
}

async function submitHandle(): Promise<void> {
  const target = handleTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await qualityAlertApi.action(Number(target.id), 'handle', {
      handler_id: handleForm.handler_id,
    })
    ElMessage.success('已进入处理中')
    handleVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function openClose(row: Record<string, unknown>): void {
  closeTarget.value = row
  dialogError.value = ''
  closeForm.remark = ''
  closeVisible.value = true
}

async function submitClose(): Promise<void> {
  const target = closeTarget.value
  if (!target) {
    return
  }
  if (!String(closeForm.remark ?? '').trim()) {
    dialogError.value = '关闭质量报警必须填写处理说明。'
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await qualityAlertApi.action(Number(target.id), 'close', { remark: closeForm.remark })
    ElMessage.success('质量报警已关闭')
    closeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function openIssue(row: Record<string, unknown>): void {
  issueTarget.value = row
  dialogError.value = ''
  issueForm.title = String(row.title ?? '')
  issueForm.category = 'material'
  issueForm.severity = ''
  issueForm.cause = ''
  issueForm.corrective_action = ''
  issueForm.preventive_action = ''
  issueVisible.value = true
}

async function submitIssue(): Promise<void> {
  const target = issueTarget.value
  if (!target) {
    return
  }
  if (!String(issueForm.title ?? '').trim()) {
    dialogError.value = '问题标题不能为空。'
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await qualityAlertApi.action(Number(target.id), 'create-issue', {
      title: issueForm.title,
      category: issueForm.category,
      severity: issueForm.severity,
      cause: issueForm.cause,
      corrective_action: issueForm.corrective_action,
      preventive_action: issueForm.preventive_action,
      tags: [],
    })
    ElMessage.success('已生成知识库草稿，请到「质量问题知识库」补充后发布')
    issueVisible.value = false
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
