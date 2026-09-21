<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">编码规则</h2>
        <p class="ys-page__description">
          编号格式必须包含流水号占位符（{SEQ} 或 {SEQ:n}），否则编号会重复，保存时会被拒绝。
          「预演」只展示下一个编号的样子，不会占用流水号，可以放心反复点击。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">新增规则</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索规则编码、名称或格式"
        clearable
        style="width: 240px"
        @keyup.enter="reload"
      />
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <span class="ys-muted">
        支持占位符：{YYYYMMDD}、{YYYYMM}、{YYYY}、{YY}、{MM}、{DD}、{SEQ}、{SEQ:4}
      </span>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="规则编码" width="170" />
      <el-table-column prop="name" label="规则名称" min-width="150" />
      <el-table-column prop="pattern" label="编号格式" min-width="200">
        <template #default="{ row }">
          <span class="ys-mono">{{ row.pattern }}</span>
        </template>
      </el-table-column>
      <el-table-column label="流水重置" width="110">
        <template #default="{ row }">{{ resetPeriodLabel(row.reset_period) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="preview(row)">预演</el-button>
          <el-button v-if="canUpdate" link type="primary" size="small" @click="openEdit(row)">
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
        <el-empty description="暂无编码规则" />
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
      :title="editingId === null ? '新增编码规则' : '编辑编码规则'"
      width="600px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert v-if="formError" type="error" :closable="false" show-icon :title="formError" />
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="规则编码" prop="code">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="如 sales_order" />
        </el-form-item>
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编号格式" prop="pattern">
          <el-input v-model="form.pattern" placeholder="SO{YYYYMMDD}{SEQ:4}" />
        </el-form-item>
        <el-form-item label="流水重置">
          <el-select v-model="form.reset_period" style="width: 100%">
            <el-option label="不重置" value="none" />
            <el-option label="按日" value="daily" />
            <el-option label="按月" value="monthly" />
            <el-option label="按年" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>

      <div class="ys-coderule__preview">
        <el-button size="small" :loading="previewing" @click="previewPattern">按当前格式预演</el-button>
        <span v-if="previewResult" class="ys-mono">{{ previewResult }}</span>
        <span v-else class="ys-muted">未预演（预演不消耗流水号）</span>
      </div>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { codeRuleApi } from '@/api/endpoints'
import { codeApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import type { CodeRule } from '@/types/models'

const auth = useAuthStore()

const rows = ref<CodeRule[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive({ search: '' })

const canCreate = computed(() => auth.hasPermission('core.code_rule.create'))
const canUpdate = computed(() => auth.hasPermission('core.code_rule.update'))

const formVisible = ref(false)
const formError = ref('')
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  pattern: '',
  reset_period: 'never',
  is_active: true,
  remark: '',
})

const formRules: FormRules = {
  code: [{ required: true, message: '请填写规则编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填写规则名称', trigger: 'blur' }],
  pattern: [{ required: true, message: '请填写编号格式', trigger: 'blur' }],
}

const previewing = ref(false)
const previewResult = ref('')

const RESET_LABELS: Record<string, string> = {
  never: '不重置',
  daily: '每日',
  monthly: '每月',
  yearly: '每年',
}

function resetPeriodLabel(value: string): string {
  return RESET_LABELS[value] ?? value
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await codeRuleApi.list({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      ordering: 'code',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载编码规则失败'
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
  reload()
}

function openCreate(): void {
  editingId.value = null
  formError.value = ''
  previewResult.value = ''
  form.code = ''
  form.name = ''
  form.pattern = ''
  form.reset_period = 'never'
  form.is_active = true
  form.remark = ''
  formVisible.value = true
}

function openEdit(row: CodeRule): void {
  editingId.value = row.id
  formError.value = ''
  previewResult.value = ''
  form.code = row.code
  form.name = row.name
  form.pattern = row.pattern
  form.reset_period = row.reset_period
  form.is_active = row.is_active
  form.remark = row.remark
  formVisible.value = true
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  formError.value = ''
  try {
    if (editingId.value === null) {
      await codeRuleApi.create({
        code: form.code.trim(),
        name: form.name.trim(),
        pattern: form.pattern.trim(),
        reset_period: form.reset_period,
        remark: form.remark,
      } as never)
      ElMessage.success('编码规则已创建')
    } else {
      await codeRuleApi.update(editingId.value, {
        name: form.name.trim(),
        pattern: form.pattern.trim(),
        reset_period: form.reset_period,
        remark: form.remark,
      } as never)
      ElMessage.success('编码规则已保存')
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

async function toggleActive(row: CodeRule): Promise<void> {
  const next = !row.is_active
  if (!next) {
    const confirmed = await ElMessageBox.confirm(
      '停用后业务单据无法再按该规则取号，可能导致单据无法保存。确认停用？',
      '停用确认',
      { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' },
    ).catch(() => false)
    if (!confirmed) {
      return
    }
  }
  try {
    await codeRuleApi.setActive(row.id, next)
    ElMessage.success(next ? '已启用' : '已停用')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function preview(row: CodeRule): void {
  previewResult.value = ''
  void codeApi
    .preview(row.code)
    .then((result) => {
      ElMessage.success(`规则 ${row.code} 的下一个编号：${result.preview}`)
    })
    .catch((error: unknown) => {
      ElMessage.error(error instanceof ApiError ? error.message : '预演失败')
    })
}

/** 未保存的格式只能做本地占位符校验，真正取值必须由后端计算。 */
async function previewPattern(): Promise<void> {
  previewing.value = true
  previewResult.value = ''
  try {
    if (editingId.value !== null && form.pattern === rows.value.find((row) => row.id === editingId.value)?.pattern) {
      const result = await codeApi.preview(form.code)
      previewResult.value = result.preview
      return
    }
    ElMessage.info('请先保存规则，再用真实流水号预演编号。')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '预演失败')
  } finally {
    previewing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ys-coderule__preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--ys-gray-50);
  border-radius: 4px;
}
</style>