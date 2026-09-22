<template>
  <entity-list-page
    title="异常任务"
    entity-label="异常任务"
    description="异常任务承载现场异常的闭环：上报 → 分派 → 处理中 → 关闭。关闭时系统生成异常记录。需要停机检修的故障请走「故障保修 → 维修任务」，本条流程用于异常跟踪与整改留痕。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.abnormal_task.create', update: 'equipment.abnormal_task.update' }"
    search-placeholder="搜索任务编号、设备或异常描述"
    default-ordering="-reported_at"
    :toggleable="false"
    :page-size="20"
    :action-width="260"
    ref="pageRef"
  >
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level || 'medium'))" size="small" effect="light">
        {{ row.level_label || '一般' }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('abnormal_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canHandle && row.status !== 'closed' && row.status !== 'cancelled'"
        link
        type="primary"
        size="small"
        @click="openAssign(row)"
      >
        分派
      </el-button>
      <el-button
        v-if="canHandle && (row.status === 'assigned' || row.status === 'reported')"
        link
        type="warning"
        size="small"
        @click="startHandling(row)"
      >
        处理中
      </el-button>
      <el-button
        v-if="canHandle && row.status !== 'closed' && row.status !== 'cancelled'"
        link
        type="success"
        size="small"
        @click="openClose(row)"
      >
        关闭
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="assignVisible" title="分派异常任务" width="520px" :close-on-click-modal="false">
    <el-alert v-if="dialogError" type="error" :closable="false" show-icon :title="dialogError" class="ys-form-error" />
    <el-form label-width="110px">
      <el-form-item label="处理人">
        <el-select v-model="assignForm.handler_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in handlerOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="处理期限">
        <el-date-picker
          v-model="assignForm.deadline"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="assignVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitAssign">确认分派</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="closeVisible" title="关闭异常任务" width="620px" :close-on-click-modal="false">
    <el-alert v-if="dialogError" type="error" :closable="false" show-icon :title="dialogError" class="ys-form-error" />
    <el-form label-width="110px">
      <el-form-item label="处理人">
        <el-select v-model="closeForm.handler_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in handlerOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="处理日期">
        <el-date-picker
          v-model="closeForm.handle_date"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="处理动作">
        <el-input v-model="closeForm.action" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="处理结果">
        <el-input v-model="closeForm.result" type="textarea" :rows="3" />
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
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { abnormalTaskApi } from '@/api/endpoints'
import { abnormalTypeOptions, employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = abnormalTaskApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canHandle = computed(() => auth.hasPermission('equipment.abnormal_task.handle'))

function levelTagType(level: string): 'info' | 'warning' | 'danger' {
  if (level === 'critical' || level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'info'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'handling') return 'primary'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'task_no', label: '任务编号', width: 160, sortable: true },
  { prop: 'abnormal_type_name', label: '异常类型', width: 140 },
  { prop: 'level', label: '异常等级', width: 110 },
  { prop: 'equipment_name', label: '设备', minWidth: 150 },
  { prop: 'source', label: '来源', width: 110 },
  { prop: 'description', label: '异常描述', minWidth: 200 },
  { prop: 'reported_by_name', label: '上报人', width: 110 },
  { prop: 'handler_name', label: '处理人', width: 110 },
  { prop: 'deadline', label: '处理期限', width: 120 },
  { prop: 'status', label: '处理状态', width: 110 },
]

const filters = computed(() => [
  {
    prop: 'abnormal_type_id',
    label: '异常类型',
    type: 'select' as const,
    optionsLoader: abnormalTypeOptions,
  },
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'status',
    label: '处理状态',
    type: 'select' as const,
    options: meta.options('abnormal_statuses'),
  },
  {
    prop: 'source',
    label: '来源',
    type: 'select' as const,
    options: meta.options('abnormal_sources'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'reported_at', label: '上报时间' },
  { prop: 'handling', label: '处理措施' },
  { prop: 'closed_at', label: '关闭时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'abnormal_type_id',
    label: '异常类型',
    type: 'select',
    required: true,
    optionsLoader: abnormalTypeOptions,
  },
  { prop: 'equipment_id', label: '设备', type: 'select', optionsLoader: equipmentOptions },
  {
    prop: 'source',
    label: '来源',
    type: 'select',
    options: meta.options('abnormal_sources'),
    defaultValue: 'manual',
  },
  { prop: 'description', label: '异常描述', type: 'textarea', span: 24, required: true },
  { prop: 'reported_by_id', label: '上报人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'deadline', label: '处理期限', type: 'date' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const assignVisible = ref(false)
const closeVisible = ref(false)
const dialogError = ref('')
const submitting = ref(false)
const target = ref<Record<string, unknown> | null>(null)
const handlerOptions = ref<EnumOption[]>([])
const assignForm = reactive<Record<string, unknown>>({ handler_id: null, deadline: '' })
const closeForm = reactive<Record<string, unknown>>({
  handler_id: null,
  handle_date: '',
  action: '',
  result: '',
})

onMounted(async () => {
  handlerOptions.value = await employeeOptions().catch(() => [])
})

function openAssign(row: Record<string, unknown>): void {
  target.value = row
  dialogError.value = ''
  assignForm.handler_id = row.handler_id ?? null
  assignForm.deadline = String(row.deadline ?? '')
  assignVisible.value = true
}

async function submitAssign(): Promise<void> {
  const row = target.value
  if (!row) {
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await abnormalTaskApi.action(Number(row.id), 'assign', {
      handler_id: assignForm.handler_id || null,
      deadline: assignForm.deadline || null,
    })
    ElMessage.success('已分派')
    assignVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '分派失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function startHandling(row: Record<string, unknown>): Promise<void> {
  const result = await ElMessageBox.prompt('填写处理措施', '登记处理中', {
    confirmButtonText: '确认',
    cancelButtonText: '取消',
    inputValue: String(row.handling ?? ''),
  }).catch(() => null)
  if (!result) {
    return
  }
  try {
    await abnormalTaskApi.action(Number(row.id), 'handle', { action: result.value ?? '' })
    ElMessage.success('已进入处理中')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function openClose(row: Record<string, unknown>): void {
  target.value = row
  dialogError.value = ''
  closeForm.handler_id = row.handler_id ?? null
  closeForm.handle_date = new Date().toISOString().slice(0, 10)
  closeForm.action = String(row.handling ?? '')
  closeForm.result = ''
  closeVisible.value = true
}

async function submitClose(): Promise<void> {
  const row = target.value
  if (!row) {
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await abnormalTaskApi.action(Number(row.id), 'close', {
      handler_id: closeForm.handler_id || null,
      handle_date: closeForm.handle_date || null,
      action: closeForm.action,
      result: closeForm.result,
    })
    ElMessage.success('已关闭，异常记录已生成')
    closeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '关闭失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>