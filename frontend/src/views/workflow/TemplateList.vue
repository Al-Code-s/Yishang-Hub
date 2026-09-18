<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">审批模板</h2>
        <p class="ys-page__description">
          首版支持顺序多级审批，并用金额区间与部门范围做条件路由。
          节点一旦变更，模板版本号自增，已提交单据继续使用提交时的快照，历史不受影响。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">
          新增模板
        </el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索模板编码或名称"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
      />
      <el-input
        v-model="filters.biz_type"
        placeholder="业务类型，如 generic.request"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
      />
      <el-select v-model="filters.is_active" placeholder="状态" clearable style="width: 120px">
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="模板编码" width="180" />
      <el-table-column prop="name" label="模板名称" min-width="180" />
      <el-table-column prop="biz_type" label="业务类型" width="160" />
      <el-table-column prop="company_name" label="适用公司" width="140" />
      <el-table-column label="审批节点" width="90" align="center">
        <template #default="{ row }">{{ row.nodes.length }}</template>
      </el-table-column>
      <el-table-column prop="version_no" label="版本" width="80" align="center" />
      <el-table-column label="允许自审" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.allow_self_approval ? 'warning' : 'info'" size="small" effect="plain">
            {{ row.allow_self_approval ? '允许' : '禁止' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
          <el-button
            v-if="canUpdate"
            link
            type="primary"
            size="small"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="canUpdate"
            link
            :type="row.is_active ? 'warning' : 'success'"
            size="small"
            @click="toggleActive(row)"
          >
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="还没有审批模板" />
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

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增审批模板' : '编辑审批模板'"
      width="880px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert v-if="formError" type="error" :closable="false" show-icon :title="formError" />
      <el-form ref="formRef" :model="form" label-width="130px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="模板编码" required>
              <el-input
                v-model="form.code"
                :disabled="editingId !== null"
                placeholder="字母开头，字母数字下划线"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模板名称" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="业务类型" required>
              <el-input v-model="form.biz_type" placeholder="generic.request" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="适用公司">
              <el-select v-model="form.company_id" clearable style="width: 100%">
                <el-option
                  v-for="item in companySelectOptions"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="允许自审">
              <el-switch v-model="form.allow_self_approval" />
              <span class="ys-muted">开启属于例外授权，会在审批轨迹中留痕。</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="说明">
              <el-input v-model="form.description" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <h4 class="ys-section-title">审批节点（按顺序审批）</h4>
        <el-table :data="form.nodes" border size="small">
          <el-table-column label="顺序" width="80">
            <template #default="{ row }">
              <el-input-number v-model="row.seq" :min="1" :controls="false" size="small" style="width: 100%" />
            </template>
          </el-table-column>
          <el-table-column label="节点名称" width="140">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="审批人类型" width="130">
            <template #default="{ row }">
              <el-select v-model="row.approver_type" size="small" style="width: 100%">
                <el-option label="按角色" value="role" />
                <el-option label="指定人员" value="user" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="审批角色 / 人员" width="200">
            <template #default="{ row }">
              <el-select
                v-if="row.approver_type === 'role'"
                v-model="row.approver_role_id"
                size="small"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in roleSelectOptions"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
              <el-select
                v-else
                v-model="row.approver_user_id"
                size="small"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in userSelectOptions"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="金额下限" width="130">
            <template #default="{ row }">
              <el-input v-model="row.amount_min" size="small" placeholder="不限" />
            </template>
          </el-table-column>
          <el-table-column label="金额上限" width="130">
            <template #default="{ row }">
              <el-input v-model="row.amount_max" size="small" placeholder="不限" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="removeNode($index)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="未配置节点：提交后会返回 APPROVAL_NO_MATCHING_NODE" :image-size="60" />
          </template>
        </el-table>
        <el-button class="ys-node-add" plain @click="addNode">添加节点</el-button>
        <p class="ys-muted">
          金额区间为「不填即不限」；模板填写了金额区间但申请未填金额时，该节点不会命中。
          部门范围留空表示不限部门。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="审批模板详情" size="520px">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="模板编码">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="模板名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="业务类型">{{ detail.biz_type }}</el-descriptions-item>
          <el-descriptions-item label="适用公司">{{ detail.company_name || '不限' }}</el-descriptions-item>
          <el-descriptions-item label="模板版本">v{{ detail.version_no }}</el-descriptions-item>
          <el-descriptions-item label="允许自审">
            {{ detail.allow_self_approval ? '允许' : '禁止' }}
          </el-descriptions-item>
          <el-descriptions-item label="说明">{{ detail.description || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="ys-section-title">节点快照</h4>
        <el-table :data="detail.nodes" border size="small">
          <el-table-column prop="seq" label="顺序" width="70" />
          <el-table-column prop="name" label="节点" min-width="120" />
          <el-table-column label="审批人" min-width="150">
            <template #default="{ row }">
              {{ row.approver_role_name || row.approver_user_name || '未指定' }}
            </template>
          </el-table-column>
          <el-table-column label="金额区间" min-width="150">
            <template #default="{ row }">
              {{ row.amount_min || row.amount_max ? `${row.amount_min ?? '-∞'} ~ ${row.amount_max ?? '+∞'}` : '不限' }}
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="未加载到模板详情" />
    </el-drawer>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { userApi } from '@/api/identity'
import { workflowApi } from '@/api/modules'
import { companyOptions, roleOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import type { ApprovalTemplate, EnumOption } from '@/types/models'

interface NodeForm {
  seq: number
  name: string
  approver_type: 'role' | 'user'
  approver_role_id: number | null
  approver_user_id: number | null
  amount_min: string
  amount_max: string
}

const auth = useAuthStore()

const rows = ref<ApprovalTemplate[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')

const filters = reactive<{ search: string; biz_type: string; is_active: boolean | '' }>({
  search: '',
  biz_type: '',
  is_active: '',
})

const canCreate = computed(() => auth.hasPermission('workflow.template.create'))
const canUpdate = computed(() => auth.hasPermission('workflow.template.update'))

const formVisible = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const editingId = ref<number | null>(null)
const detail = ref<ApprovalTemplate | null>(null)
const formRef = ref<FormInstance>()

const companySelectOptions = ref<EnumOption[]>([])
const roleSelectOptions = ref<EnumOption[]>([])
const userSelectOptions = ref<EnumOption[]>([])

const form = reactive<{
  code: string
  name: string
  biz_type: string
  company_id: number | null
  allow_self_approval: boolean
  is_active: boolean
  description: string
  nodes: NodeForm[]
}>({
  code: '',
  name: '',
  biz_type: 'generic.request',
  company_id: null,
  allow_self_approval: false,
  is_active: true,
  description: '',
  nodes: [],
})

function newFilterParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
    search: filters.search || undefined,
    biz_type: filters.biz_type || undefined,
    is_active: filters.is_active === '' ? undefined : filters.is_active,
    ordering: 'code',
  }
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await workflowApi.template.list(newFilterParams())
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载审批模板失败'
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
  filters.biz_type = ''
  filters.is_active = ''
  reload()
}

async function ensureOptions(): Promise<void> {
  if (companySelectOptions.value.length === 0) {
    companySelectOptions.value = await companyOptions().catch(() => [])
  }
  if (roleSelectOptions.value.length === 0) {
    roleSelectOptions.value = await roleOptions().catch(() => [])
  }
  if (userSelectOptions.value.length === 0) {
    const pageData = await userApi
      .list({ page_size: 200, is_active: true, ordering: 'username' })
      .catch(() => null)
    userSelectOptions.value = pageData
      ? pageData.results.map((item) => ({
          value: item.id,
          label: `${item.username} ${item.display_name || ''}`.trim(),
        }))
      : []
  }
}

function addNode(): void {
  const nextSeq = form.nodes.reduce((max, node) => Math.max(max, node.seq), 0) + 1
  form.nodes.push({
    seq: nextSeq,
    name: `审批节点 ${nextSeq}`,
    approver_type: 'role',
    approver_role_id: null,
    approver_user_id: null,
    amount_min: '',
    amount_max: '',
  })
}

function removeNode(index: number): void {
  form.nodes.splice(index, 1)
}

function openCreate(): void {
  editingId.value = null
  formError.value = ''
  form.code = ''
  form.name = ''
  form.biz_type = 'generic.request'
  form.company_id = null
  form.allow_self_approval = false
  form.is_active = true
  form.description = ''
  form.nodes = []
  addNode()
  formVisible.value = true
  void ensureOptions()
}

function openEdit(row: ApprovalTemplate): void {
  editingId.value = row.id
  formError.value = ''
  form.code = row.code
  form.name = row.name
  form.biz_type = row.biz_type
  form.company_id = row.company_id
  form.allow_self_approval = row.allow_self_approval
  form.is_active = row.is_active
  form.description = row.description
  form.nodes = row.nodes.map((node) => ({
    seq: node.seq,
    name: node.name,
    approver_type: node.approver_type,
    approver_role_id: node.approver_role_id,
    approver_user_id: node.approver_user_id,
    amount_min: node.amount_min ?? '',
    amount_max: node.amount_max ?? '',
  }))
  formVisible.value = true
  void ensureOptions()
}

function openDetail(row: ApprovalTemplate): void {
  detail.value = row
  detailVisible.value = true
}

async function submit(): Promise<void> {
  if (!form.code.trim() || !form.name.trim() || !form.biz_type.trim()) {
    formError.value = '模板编码、模板名称、业务类型为必填项。'
    return
  }
  const seqs = form.nodes.map((node) => node.seq)
  if (new Set(seqs).size !== seqs.length) {
    formError.value = '审批节点顺序号不能重复。'
    return
  }
  submitting.value = true
  formError.value = ''
  try {
    const payload: Record<string, unknown> = {
      name: form.name,
      biz_type: form.biz_type,
      company_id: form.company_id,
      allow_self_approval: form.allow_self_approval,
      is_active: form.is_active,
      description: form.description,
      nodes: form.nodes.map((node) => ({
        seq: node.seq,
        name: node.name,
        approver_type: node.approver_type,
        approver_role_id: node.approver_type === 'role' ? node.approver_role_id : null,
        approver_user_id: node.approver_type === 'user' ? node.approver_user_id : null,
        amount_min: node.amount_min === '' ? null : node.amount_min,
        amount_max: node.amount_max === '' ? null : node.amount_max,
        department_ids: [],
        is_active: true,
      })),
    }
    if (editingId.value === null) {
      payload.code = form.code
      await workflowApi.template.create(payload as never)
      ElMessage.success('模板已创建')
    } else {
      await workflowApi.template.update(editingId.value, payload as never)
      ElMessage.success('模板已保存，版本号已自增')
    }
    formVisible.value = false
    await load()
  } catch (error) {
    formError.value =
      error instanceof ApiError ? error.fieldErrorMessage || error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

async function toggleActive(row: ApprovalTemplate): Promise<void> {
  const next = !row.is_active
  if (!next) {
    const confirmed = await ElMessageBox.confirm(
      '停用后该模板不能再用于新的审批单据，已提交单据不受影响。确认停用？',
      '停用确认',
      { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' },
    ).catch(() => false)
    if (!confirmed) {
      return
    }
  }
  try {
    await workflowApi.template.action(row.id, 'set-active', { is_active: next })
    ElMessage.success(next ? '已启用' : '已停用')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

onMounted(load)
</script>

<style scoped>
.ys-node-add {
  margin-top: 8px;
}
</style>