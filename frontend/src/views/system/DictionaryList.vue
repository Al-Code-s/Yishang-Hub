<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">数据字典</h2>
        <p class="ys-page__description">
          字典用于维护可配置的下拉取值。业务枚举（部门类型、仓库类型等）由后端
          `/api/v1/meta/` 统一返回，新增取值后前端无需改动即可出现，不在这里硬编码中文标签。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">新增字典</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索字典编码或名称"
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
      <el-table-column prop="code" label="字典编码" width="200" />
      <el-table-column prop="name" label="字典名称" min-width="180" />
      <el-table-column label="字典项" width="90" align="center">
        <template #default="{ row }">{{ row.items.length }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="160" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openItems(row)">字典项</el-button>
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
        <el-empty description="暂无字典" />
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
      :title="editingId === null ? '新增字典' : '编辑字典'"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert v-if="formError" type="error" :closable="false" show-icon :title="formError" />
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="字典编码" prop="code">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="如 shift_type" />
        </el-form-item>
        <el-form-item label="字典名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="itemsVisible" :title="`字典项：${currentDictionary?.name ?? ''}`" size="720px">
      <div class="ys-toolbar">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openItemCreate">
          新增字典项
        </el-button>
        <el-button :loading="itemsLoading" @click="loadItems">刷新</el-button>
        <span class="ys-muted">共 {{ items.length }} 项</span>
      </div>

      <el-alert v-if="itemsError" type="error" :closable="false" show-icon :title="itemsError" />

      <el-table v-loading="itemsLoading" :data="items" border stripe size="small">
        <el-table-column prop="code" label="项编码" width="160" />
        <el-table-column prop="label" label="显示文本" min-width="180" />
        <el-table-column prop="sort_order" label="排序" width="90" align="center" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canUpdate" link type="primary" size="small" @click="openItemEdit(row)">
              编辑
            </el-button>
            <el-button
              v-if="canUpdate"
              link
              :type="row.is_active ? 'warning' : 'success'"
              size="small"
              @click="toggleItemActive(row)"
            >
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="该字典还没有字典项" />
        </template>
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="itemFormVisible"
      :title="itemEditingId === null ? '新增字典项' : '编辑字典项'"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert v-if="itemFormError" type="error" :closable="false" show-icon :title="itemFormError" />
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemFormRules" label-width="100px">
        <el-form-item label="项编码" prop="code">
          <el-input v-model="itemForm.code" :disabled="itemEditingId !== null" />
        </el-form-item>
        <el-form-item label="显示文本" prop="label">
          <el-input v-model="itemForm.label" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="itemForm.sort_order" :min="0" :controls="false" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="itemForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { dictionaryApi, dictionaryItemApi } from '@/api/endpoints'
import { useAuthStore } from '@/stores/auth'
import type { Dictionary, DictionaryItem } from '@/types/models'

const auth = useAuthStore()

const rows = ref<Dictionary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')

const filters = reactive<{ search: string; is_active: boolean | '' }>({ search: '', is_active: '' })

const canCreate = computed(() => auth.hasPermission('core.dictionary.create'))
const canUpdate = computed(() => auth.hasPermission('core.dictionary.update'))

const formVisible = ref(false)
const formError = ref('')
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ code: '', name: '', is_active: true, remark: '' })

const formRules: FormRules = {
  code: [{ required: true, message: '请填写字典编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填写字典名称', trigger: 'blur' }],
}

const itemsVisible = ref(false)
const itemsLoading = ref(false)
const itemsError = ref('')
const items = ref<DictionaryItem[]>([])
const currentDictionary = ref<Dictionary | null>(null)

const itemFormVisible = ref(false)
const itemFormError = ref('')
const itemEditingId = ref<number | null>(null)
const itemFormRef = ref<FormInstance>()
const itemForm = reactive({ code: '', label: '', sort_order: 0, is_active: true })

const itemFormRules: FormRules = {
  code: [{ required: true, message: '请填写项编码', trigger: 'blur' }],
  label: [{ required: true, message: '请填写显示文本', trigger: 'blur' }],
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await dictionaryApi.list({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      is_active: filters.is_active === '' ? undefined : filters.is_active,
      ordering: 'code',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载字典失败'
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
  filters.is_active = ''
  reload()
}

function openCreate(): void {
  editingId.value = null
  formError.value = ''
  form.code = ''
  form.name = ''
  form.is_active = true
  form.remark = ''
  formVisible.value = true
}

function openEdit(row: Dictionary): void {
  editingId.value = row.id
  formError.value = ''
  form.code = row.code
  form.name = row.name
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
      await dictionaryApi.create({ code: form.code.trim(), name: form.name.trim(), remark: form.remark } as never)
      ElMessage.success('字典已创建')
    } else {
      await dictionaryApi.update(editingId.value, {
        name: form.name.trim(),
        is_active: form.is_active,
        remark: form.remark,
      } as never)
      ElMessage.success('字典已保存')
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

async function toggleActive(row: Dictionary): Promise<void> {
  const next = !row.is_active
  if (!next) {
    const confirmed = await ElMessageBox.confirm(
      '停用后该字典不再出现在下拉选项中，已保存的历史数据不受影响。确认停用？',
      '停用确认',
      { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' },
    ).catch(() => false)
    if (!confirmed) {
      return
    }
  }
  try {
    await dictionaryApi.setActive(row.id, next)
    ElMessage.success(next ? '已启用' : '已停用')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function loadItems(): Promise<void> {
  if (!currentDictionary.value) {
    return
  }
  itemsLoading.value = true
  itemsError.value = ''
  try {
    const result = await dictionaryItemApi.list({
      page: 1,
      page_size: 200,
      dictionary_id: currentDictionary.value.id,
      ordering: 'sort_order',
    })
    items.value = result.results
  } catch (error) {
    items.value = []
    itemsError.value = error instanceof ApiError ? error.message : '加载字典项失败'
  } finally {
    itemsLoading.value = false
  }
}

async function openItems(row: Dictionary): Promise<void> {
  currentDictionary.value = row
  itemsVisible.value = true
  await loadItems()
}

function openItemCreate(): void {
  itemEditingId.value = null
  itemFormError.value = ''
  itemForm.code = ''
  itemForm.label = ''
  itemForm.sort_order = items.value.length * 10
  itemForm.is_active = true
  itemFormVisible.value = true
}

function openItemEdit(row: DictionaryItem): void {
  itemEditingId.value = row.id
  itemFormError.value = ''
  itemForm.code = row.code
  itemForm.label = row.label
  itemForm.sort_order = row.sort_order
  itemForm.is_active = row.is_active
  itemFormVisible.value = true
}

async function submitItem(): Promise<void> {
  if (!currentDictionary.value) {
    return
  }
  const valid = await itemFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  itemFormError.value = ''
  try {
    if (itemEditingId.value === null) {
      await dictionaryItemApi.create({
        dictionary_id: currentDictionary.value.id,
        code: itemForm.code.trim(),
        label: itemForm.label.trim(),
        sort_order: itemForm.sort_order,
      } as never)
      ElMessage.success('字典项已创建')
    } else {
      await dictionaryItemApi.update(itemEditingId.value, {
        label: itemForm.label.trim(),
        sort_order: itemForm.sort_order,
        is_active: itemForm.is_active,
      } as never)
      ElMessage.success('字典项已保存')
    }
    itemFormVisible.value = false
    await loadItems()
    await load()
  } catch (error) {
    itemFormError.value =
      error instanceof ApiError ? error.fieldErrorMessage || error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

async function toggleItemActive(row: DictionaryItem): Promise<void> {
  try {
    await dictionaryItemApi.setActive(row.id, !row.is_active)
    ElMessage.success(!row.is_active ? '已启用' : '已停用')
    await loadItems()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

onMounted(load)
</script>