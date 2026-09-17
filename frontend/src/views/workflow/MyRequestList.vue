<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">我的申请</h2>
        <p class="ys-page__description">
          这里只显示本人提交的审批单据。审批通过与后续业务动作（例如库存过账）是两个独立动作，
          审批结果不会自动改动库存或单据状态。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canSubmit" type="primary" :icon="Plus" @click="openCreate">
          新建申请
        </el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索单号或标题"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
      />
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
        <el-option
          v-for="item in statusOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="biz_no" label="单号" width="150" />
      <el-table-column prop="title" label="申请事项" min-width="200" />
      <el-table-column prop="template_name" label="审批模板" width="150" />
      <el-table-column prop="current_step_name" label="当前节点" width="130" />
      <el-table-column label="金额" width="120" align="right">
        <template #default="{ row }">{{ formatAmount(row.amount, 4) }}</template>
      </el-table-column>
      <el-table-column prop="status_display" label="状态" width="100" />
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.submitted_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
          <el-button
            v-if="row.status === 'draft' && canSubmit"
            link
            type="success"
            size="small"
            @click="submit(row)"
          >
            提交
          </el-button>
          <el-button
            v-if="row.can_withdraw"
            link
            type="warning"
            size="small"
            @click="withdraw(row)"
          >
            撤回
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="还没有提交过审批申请" />
      </template>
    </el-table>

    <div class="ys-pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="load"
      />
    </div>

    <approval-detail-drawer v-model="detailVisible" :instance-id="currentId" @changed="load" />

    <el-dialog
      v-model="createVisible"
      title="新建审批申请"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-alert v-if="createError" type="error" :closable="false" show-icon :title="createError" />
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-form-item label="申请事项" prop="title">
          <el-input v-model="createForm.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="审批模板">
          <el-select v-model="createForm.template_code" clearable style="width: 100%">
            <el-option
              v-for="item in templateOptions"
              :key="item.code"
              :label="item.label"
              :value="item.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="业务类型" prop="biz_type">
          <el-input v-model="createForm.biz_type" placeholder="generic.request" />
        </el-form-item>
        <el-form-item label="关联单号">
          <el-input v-model="createForm.biz_no" placeholder="可留空；后续阶段由业务单据带入" />
        </el-form-item>
        <el-form-item label="涉及金额">
          <el-input v-model="createForm.amount" placeholder="可留空；留空且模板限定金额区间时不会命中节点" />
        </el-form-item>
        <el-form-item label="申请部门">
          <el-select v-model="createForm.department_id" clearable style="width: 100%">
            <el-option
              v-for="item in departmentSelectOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="申请说明">
          <el-input v-model="createForm.summary" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button :loading="submitting" @click="createAndSubmit(false)">保存草稿</el-button>
        <el-button type="primary" :loading="submitting" @click="createAndSubmit(true)">
          保存并提交
        </el-button>
      </template>
    </el-dialog>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import ApprovalDetailDrawer from '@/components/ApprovalDetailDrawer.vue'
import { ApiError } from '@/api/http'
import { workflowApi } from '@/api/modules'
import { departmentOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { ApprovalInstance, EnumOption } from '@/types/models'
import { formatAmount } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()

const rows = ref<ApprovalInstance[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')

const filters = reactive({ search: '', status: '' })

const statusOptions = computed(() => meta.approvalStatusOptions())
const canSubmit = computed(() => auth.hasPermission('workflow.instance.submit'))

const detailVisible = ref(false)
const currentId = ref<number | null>(null)

const createVisible = ref(false)
const submitting = ref(false)
const createError = ref('')
const createFormRef = ref<FormInstance>()
const templateOptions = ref<{ code: string; label: string }[]>([])
const departmentSelectOptions = ref<EnumOption[]>([])
const createForm = reactive({
  title: '',
  template_code: '',
  biz_type: 'generic.request',
  biz_no: '',
  amount: '',
  department_id: null as number | null,
  summary: '',
})

const createRules: FormRules = {
  title: [{ required: true, message: '请填写申请事项', trigger: 'blur' }],
  biz_type: [{ required: true, message: '请填写业务类型', trigger: 'blur' }],
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await workflowApi.mine({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      status: filters.status || undefined,
      ordering: '-id',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载我的申请失败'
  } finally {
    loading.value = false
  }
}

function reload(): void {
  page.value = 1
  void load()
}

function resetFilters(): void {
  filters.search = ''
  filters.status = ''
  reload()
}

function openDetail(row: ApprovalInstance): void {
  currentId.value = row.id
  detailVisible.value = true
}

async function submit(row: ApprovalInstance): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    `确认提交「${row.title}」进入审批流程？提交后申请人不能直接修改单据内容。`,
    '提交确认',
    { type: 'warning', confirmButtonText: '确认提交', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await workflowApi.submit(row.id)
    ElMessage.success('已提交')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '提交失败')
  }
}

async function withdraw(row: ApprovalInstance): Promise<void> {
  try {
    const result = await ElMessageBox.prompt('请填写撤回说明', '撤回申请', {
      inputType: 'textarea',
      confirmButtonText: '确认撤回',
      cancelButtonText: '取消',
    })
    await workflowApi.withdraw(row.id, result.value || '申请人撤回')
    ElMessage.success('已撤回')
    await load()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error instanceof ApiError ? error.message : '撤回失败')
  }
}

async function openCreate(): Promise<void> {
  createError.value = ''
  createForm.title = ''
  createForm.template_code = ''
  createForm.biz_type = 'generic.request'
  createForm.biz_no = ''
  createForm.amount = ''
  createForm.department_id = auth.user?.department_id ?? null
  createForm.summary = ''
  createVisible.value = true
  try {
    const [templates, departments] = await Promise.all([
      workflowApi.template.list({ page_size: 200, is_active: true, ordering: 'code' }),
      departmentOptions().catch(() => [] as EnumOption[]),
    ])
    templateOptions.value = templates.results.map((item) => ({
      code: item.code,
      label: `${item.code} ${item.name}`,
    }))
    departmentSelectOptions.value = departments
  } catch {
    templateOptions.value = []
  }
}

async function createAndSubmit(alsoSubmit: boolean): Promise<void> {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  createError.value = ''
  try {
    const payload: Parameters<typeof workflowApi.create>[0] = {
      title: createForm.title,
      biz_type: createForm.biz_type,
      summary: createForm.summary,
    }
    if (createForm.template_code) {
      payload.template_code = createForm.template_code
    }
    if (createForm.biz_no) {
      payload.biz_no = createForm.biz_no
    }
    if (createForm.amount) {
      payload.amount = createForm.amount
    }
    if (createForm.department_id) {
      payload.department_id = createForm.department_id
    }
    const created = await workflowApi.create(payload)
    if (alsoSubmit) {
      await workflowApi.submit(created.id)
      ElMessage.success('已创建并提交')
    } else {
      ElMessage.success('已保存为草稿')
    }
    createVisible.value = false
    reload()
  } catch (error) {
    createError.value =
      error instanceof ApiError ? error.fieldErrorMessage || error.message : '创建失败'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await meta.ensureLoaded().catch(() => undefined)
  await load()
})
</script>