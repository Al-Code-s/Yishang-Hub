<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">{{ title }}</h2>
        <p v-if="description" class="ys-page__description">{{ description }}</p>
      </div>
      <div class="ys-page__header-actions">
        <slot name="header-actions" />
      </div>
    </div>

    <!-- 统计/概览区（可选）：放在筛选条之前，页面自己决定放什么 -->
    <slot name="summary" :reload="list.load" />

    <pro-table
      v-model:page="list.page.value"
      v-model:page-size="list.pageSize.value"
      :columns="columns"
      :rows="list.rows.value as unknown as Record<string, unknown>[]"
      :total="list.total.value"
      :loading="list.loading.value"
      :error-message="list.errorMessage.value"
      :empty-text="emptyText"
      :action-width="actionWidth"
      @refresh="refresh"
      @reset="list.resetFilters()"
      @sort-change="list.onSortChange"
    >
      <template #filters>
        <el-input
          v-if="searchable"
          v-model="list.filters.search as string"
          :placeholder="searchPlaceholder"
          clearable
          style="width: 220px"
          @keyup.enter="list.load()"
        />
        <template v-for="filter in filters" :key="filter.prop">
          <el-select
            v-if="filter.type === 'select'"
            v-model="list.filters[filter.prop]"
            :placeholder="filter.label"
            clearable
            style="width: 160px"
          >
            <el-option
              v-for="option in filterOptions[filter.prop] ?? filter.options ?? []"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-input
            v-else
            v-model="list.filters[filter.prop] as string"
            :placeholder="filter.label"
            clearable
            style="width: 160px"
            @keyup.enter="list.load()"
          />
        </template>
        <slot name="filters" :filters="list.filters" />
      </template>

      <template #toolbar>
        <el-button
          v-if="canCreate"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增{{ entityLabel }}
        </el-button>
        <slot name="toolbar" :reload="list.load" />
      </template>

      <template
        v-for="column in columns"
        #[`column-${column.prop}`]="scope"
        :key="`slot-${column.prop}`"
      >
        <slot :name="`column-${column.prop}`" :row="scope.row" :index="scope.index">
          <el-tag
            v-if="column.prop === 'is_active'"
            :type="scope.row.is_active ? 'success' : 'info'"
            size="small"
            effect="light"
          >
            {{ scope.row.is_active ? '启用' : '停用' }}
          </el-tag>
          <span v-else-if="column.formatter">{{ column.formatter(scope.row) }}</span>
          <span v-else>{{ renderCell(scope.row, column.prop) }}</span>
        </slot>
      </template>

      <template #actions="scope">
        <slot name="actions" :row="scope.row">
          <el-button link type="primary" size="small" @click="openDetail(scope.row)">详情</el-button>
          <el-button
            v-if="canUpdate"
            link
            type="primary"
            size="small"
            @click="openEdit(scope.row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="canDeactivate && list.canToggleActive.value"
            link
            :type="scope.row.is_active === false ? 'success' : 'warning'"
            size="small"
            @click="list.toggleActive(scope.row)"
          >
            {{ scope.row.is_active === false ? '启用' : '停用' }}
          </el-button>
          <!-- 追加动作（开始 / 完成 / 派工 …）：保留上面的默认按钮，不覆盖 -->
          <slot name="row-actions" :row="scope.row" :reload="list.load" />
        </slot>
      </template>
    </pro-table>

    <el-dialog
      v-model="formVisible"
      :title="formTitle"
      :width="formWidth"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert
        v-if="formError"
        type="error"
        :closable="false"
        show-icon
        :title="formError"
        class="ys-form-error"
      />
      <el-form ref="formRef" :model="formModel" :rules="formRules" label-width="120px">
        <el-row :gutter="16">
          <el-col v-for="field in visibleFormFields" :key="field.prop" :span="field.span ?? 12">
            <el-form-item :label="field.label" :prop="field.prop">
              <el-select
                v-if="field.type === 'select'"
                v-model="formModel[field.prop]"
                :placeholder="field.placeholder ?? `请选择${field.label}`"
                :multiple="field.multiple === true"
                :collapse-tags="field.multiple === true"
                :collapse-tags-tooltip="field.multiple === true"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="option in fieldOptions[field.prop] ?? field.options ?? []"
                  :key="String(option.value)"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-input
                v-else-if="field.type === 'textarea'"
                v-model="formModel[field.prop] as string"
                type="textarea"
                :rows="2"
                :placeholder="field.placeholder ?? `请输入${field.label}`"
              />
              <el-switch v-else-if="field.type === 'switch'" v-model="formModel[field.prop]" />
              <el-date-picker
                v-else-if="field.type === 'date'"
                v-model="formModel[field.prop]"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
              <el-date-picker
                v-else-if="field.type === 'datetime'"
                v-model="formModel[field.prop]"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                style="width: 100%"
              />
              <el-input-number
                v-else-if="field.type === 'number'"
                v-model="formModel[field.prop] as number"
                :min="0"
                style="width: 100%"
              />
              <el-input
                v-else-if="field.type === 'decimal'"
                v-model="formModel[field.prop] as string"
                placeholder="十进制数值，例如 12.50"
              />
              <el-input
                v-else
                v-model="formModel[field.prop] as string"
                :placeholder="field.placeholder ?? `请输入${field.label}`"
                :disabled="field.disabled === true"
              />
              <div v-if="field.help" class="ys-muted">{{ field.help }}</div>
            </el-form-item>
          </el-col>
        </el-row>
        <slot name="form-extra" :model="formModel" />
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="`${entityLabel}详情`" size="480px">
      <el-descriptions v-if="detailRow" :column="1" border size="small">
        <el-descriptions-item
          v-for="column in columns"
          :key="column.prop"
          :label="column.label"
        >
          {{ renderCell(detailRow, column.prop) }}
        </el-descriptions-item>
        <el-descriptions-item v-for="field in detailFields" :key="field.prop" :label="field.label">
          {{ renderCell(detailRow, field.prop) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatDateTime(String(detailRow.updated_at ?? '')) }}
        </el-descriptions-item>
        <el-descriptions-item label="版本号">
          {{ detailRow.version ?? '-' }}
        </el-descriptions-item>
      </el-descriptions>
      <slot name="detail" :row="detailRow" />
    </el-drawer>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import ProTable, { type ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import type { CrudApi, QueryParams } from '@/api/crud'
import type { EnumOption } from '@/types/models'
import { formatNumericText, toEditableText } from '@/utils/decimal'
import { formatDateTime, omitEmpty } from '@/utils/format'
import { useCrudList } from '@/composables/useCrudList'
import { useAuthStore } from '@/stores/auth'

export interface FilterDef {
  prop: string
  label: string
  type?: 'text' | 'select'
  options?: EnumOption[]
  optionsLoader?: () => Promise<EnumOption[]>
}

export interface FormFieldDef {
  prop: string
  label: string
  type?:
    | 'text'
    | 'textarea'
    | 'number'
    | 'decimal'
    | 'select'
    | 'switch'
    | 'date'
    | 'datetime'
  required?: boolean
  options?: EnumOption[]
  /** 远程选项加载器：父组件不必手写加载逻辑，页面会缓存结果 */
  optionsLoader?: () => Promise<EnumOption[]>
  placeholder?: string
  help?: string
  span?: number
  disabled?: boolean
  /** 仅新增时显示（例如初始密码） */
  onlyOnCreate?: boolean
  /** 仅编辑时显示（例如由系统按编码规则自动生成、新增时不需要人工输入的编码） */
  onlyOnUpdate?: boolean
  defaultValue?: unknown
  /** 数值字段允许清空时提交 null 而不是 0 */
  nullable?: boolean
  /** select 字段允许多选（例如一个保养计划挂多个保养项目） */
  multiple?: boolean
}

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    entityLabel: string
    api: CrudApi<{ id: number; version?: number } & Record<string, unknown>, never> | {
      list: (params?: QueryParams) => Promise<{ count: number; results: unknown[] }>
    }
    columns: ProTableColumn[]
    filters?: FilterDef[]
    /** 查询条件初值（例如从其他页面带 run_id 跳转过来），重置时会回到这些初值 */
    initialFilters?: Record<string, unknown>
    formFields?: FormFieldDef[]
    detailFields?: { prop: string; label: string }[]
    searchable?: boolean
    searchPlaceholder?: string
    permissions?: { create?: string; update?: string; deactivate?: string }
    removable?: boolean
    removeWarning?: string
    /**
     * 只读资源（例如库存余额、库存流水）：只提供查询与详情。
     * 这类页面的数据由业务服务写入，界面不允许直接新增或修改。
     */
    readonly?: boolean
    defaultOrdering?: string
    pageSize?: number
    emptyText?: string
    actionWidth?: number
    formWidth?: string
    /** 提交前把表单值转换为后端字段（例如 Decimal 字符串化、空串转 null） */
    transform?: (payload: Record<string, unknown>, mode: 'create' | 'update') => Record<string, unknown>
    /** 用于 select 字段的原始值转 ID（例如父级对象） */
    optionsKey?: string
    /**
     * 是否提供「启用 / 停用」动作。
     *
     * 任务、记录这类**只有状态没有启用标记**的资源必须传 false：
     * 否则界面会出现一个点下去必然报错的「停用」按钮。
     */
    toggleable?: boolean
  }>(),
  {
    description: '',
    searchable: true,
    readonly: false,
    searchPlaceholder: '搜索编码或名称',
    emptyText: '暂无数据',
    actionWidth: 200,
    formWidth: '720px',
    defaultOrdering: 'code',
    toggleable: true,
  },
)

const auth = useAuthStore()

const list = useCrudList<{ id: number; version?: number } & Record<string, unknown>>({
  api: props.api as never,
  defaultFilters: props.initialFilters,
  activeField: props.toggleable ? 'is_active' : '',
  removable: props.removable,
  removeWarning: props.removeWarning,
  defaultOrdering: props.defaultOrdering,
  pageSize: props.pageSize,
})

const formVisible = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const formMode = ref<'create' | 'update'>('create')
const formRef = ref<FormInstance>()
const detailRow = ref<Record<string, unknown> | null>(null)
const editingId = ref<number | null>(null)
const formModel = reactive<Record<string, unknown>>({})
const fieldOptions = reactive<Record<string, EnumOption[]>>({})
const filterOptions = reactive<Record<string, EnumOption[]>>({})

const canCreate = computed(() => {
  if (props.readonly) return false
  const code = props.permissions?.create
  return !code || hasPermission(code)
})
const canUpdate = computed(() => {
  if (props.readonly) return false
  const code = props.permissions?.update
  return !code || hasPermission(code)
})
const canDeactivate = computed(() => {
  if (props.readonly) return false
  const code = props.permissions?.deactivate
  return !code || hasPermission(code)
})

const formTitle = computed(() =>
  formMode.value === 'create' ? `新增${props.entityLabel}` : `编辑${props.entityLabel}`,
)

const visibleFormFields = computed(() =>
  (props.formFields ?? []).filter((field) => {
    if (field.onlyOnCreate && formMode.value === 'update') {
      return false
    }
    // 新增时不展示系统托管字段（值由后端生成），编辑时展示以便核对
    if (field.onlyOnUpdate && formMode.value === 'create') {
      return false
    }
    return true
  }),
)

const formRules = computed<FormRules>(() => {
  const rules: FormRules = {}
  for (const field of visibleFormFields.value) {
    if (field.required) {
      rules[field.prop] = [
        { required: true, message: `请填写${field.label}`, trigger: 'blur' },
      ]
    }
  }
  return rules
})

/** 前端权限只控制按钮可见性；真正的拦截在后端，越权请求仍会被拒绝。 */
function hasPermission(code: string): boolean {
  return auth.hasPermission(code)
}
function renderCell(row: Record<string, unknown> | null, prop: string): string {
  if (!row) {
    return '-'
  }
  // 与 ProTable 一致：枚举值优先展示后端返回的中文标签（`<field>_display`）
  const label = row[`${prop}_display`]
  if (label !== null && label !== undefined && label !== '') {
    return String(label)
  }
  const value = row[prop]
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? '-' : value.map((item) => String(item)).join('、')
  }
  // 与 ProTable 一致：数值列统一 2 位小数 + 千分位（后端 Decimal 以字符串返回）
  const numeric = formatNumericText(value)
  if (numeric !== null) {
    return numeric
  }
  return String(value)
}

async function loadOptionSources(): Promise<void> {
  for (const field of props.formFields ?? []) {
    if (field.optionsLoader && !fieldOptions[field.prop]) {
      fieldOptions[field.prop] = await field.optionsLoader()
    }
  }
  for (const filter of props.filters ?? []) {
    if (filter.optionsLoader && !filterOptions[filter.prop]) {
      filterOptions[filter.prop] = await filter.optionsLoader()
    }
  }
}

function resetForm(mode: 'create' | 'update', source?: Record<string, unknown>): void {
  formMode.value = mode
  formError.value = ''
  for (const key of Object.keys(formModel)) {
    delete formModel[key]
  }
  for (const field of props.formFields ?? []) {
    if (source && source[field.prop] !== undefined) {
      const raw = source[field.prop]
      // 数值字段回填时去掉无意义的末尾 0（**不做四舍五入**），避免输入框里出现 12.000000；
      // 提交精度仍由后端 DecimalField 决定，回填文本可被原样解析。
      formModel[field.prop] = field.type === 'decimal' ? toEditableText(raw as string | null) : raw
    } else if (field.defaultValue !== undefined) {
      formModel[field.prop] = field.defaultValue
    } else if (field.type === 'switch') {
      formModel[field.prop] = true
    } else if (field.type === 'select' && field.multiple === true) {
      formModel[field.prop] = []
    } else {
      formModel[field.prop] = ''
    }
  }
}

function openCreate(): void {
  editingId.value = null
  resetForm('create')
  formVisible.value = true
}

function openEdit(row: Record<string, unknown>): void {
  editingId.value = Number(row.id)
  resetForm('update', row)
  formVisible.value = true
}

function openDetail(row: Record<string, unknown>): void {
  detailRow.value = row
  detailVisible.value = true
}

function buildPayload(): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const field of visibleFormFields.value) {
    let value = formModel[field.prop]
    if (field.type === 'switch') {
      payload[field.prop] = Boolean(value)
      continue
    }
    if (Array.isArray(value) && field.multiple === true) {
      payload[field.prop] = value
      continue
    }
    if (value === '' || value === undefined || value === null) {
      if (field.type === 'select' || field.nullable) {
        payload[field.prop] = null
      }
      continue
    }
    if (field.type === 'number') {
      payload[field.prop] = Number(value)
      continue
    }
    payload[field.prop] = typeof value === 'string' ? value.trim() : value
  }
  return props.transform ? props.transform(payload, formMode.value) : payload
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  formError.value = ''
  const payload = omitEmpty(buildPayload())
  const api = props.api as unknown as CrudApi<{ id: number }, never>
  try {
    if (formMode.value === 'create') {
      await api.create(payload as never)
      ElMessage.success(`新增${props.entityLabel}成功`)
    } else if (editingId.value !== null) {
      await api.update(editingId.value, payload as never)
      ElMessage.success(`保存${props.entityLabel}成功`)
    }
    formVisible.value = false
    await list.load()
  } catch (error) {
    if (error instanceof ApiError) {
      formError.value = error.fieldErrorMessage || error.message
      if (error.code === 'VERSION_CONFLICT') {
        formError.value = '数据已被他人修改，请关闭窗口后重新打开再编辑。'
      }
    } else {
      formError.value = '保存失败，请稍后重试'
    }
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadOptionSources().catch(() => undefined)
  await list.load()
})

const emit = defineEmits<{ refresh: [] }>()

/**
 * 刷新列表并通知外部（例如页面上方的统计区要跟着一起刷新）。
 * 工具栏的「刷新」按钮、动作完成后的 `pageRef.reload()` 都走这里。
 */
async function refresh(): Promise<void> {
  await list.load()
  emit('refresh')
}

watch(formVisible, async (value) => {
  if (value) {
    await loadOptionSources().catch(() => undefined)
  }
})

defineExpose({ reload: refresh })</script>
