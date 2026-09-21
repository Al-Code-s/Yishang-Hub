<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="SKU 档案"
      entity-label="SKU"
      description="SKU（款式 + 颜色 + 尺码）是可销售、可库存的最小单位。成品 SKU 与库存物料一一对应，库存、条码与发货都以 SKU 为准，不会出现两套编码。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :form-fields="formFields"
      :permissions="{ create: 'masterdata.sku.create', update: 'masterdata.sku.update' }"
      search-placeholder="搜索 SKU 编码、名称或条码"
    >
      <template #toolbar>
        <el-button
          v-if="canGenerate"
          type="success"
          plain
          :icon="MagicStick"
          @click="generateVisible = true"
        >
          按颜色 × 尺码批量生成
        </el-button>
      </template>
    </entity-list-page>

    <el-dialog v-model="generateVisible" title="批量生成 SKU" width="640px" :close-on-click-modal="false">
      <el-alert
        v-if="generateError"
        type="error"
        :closable="false"
        show-icon
        :title="generateError"
        class="ys-form-error"
      />
      <el-form ref="generateFormRef" :model="generateForm" :rules="generateRules" label-width="130px">
        <el-form-item label="款式" prop="style_id">
          <el-select v-model="generateForm.style_id" filterable placeholder="请选择款式" style="width: 100%">
            <el-option
              v-for="option in styleSelectOptions"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="颜色" prop="color_ids">
          <el-select
            v-model="generateForm.color_ids"
            multiple
            filterable
            placeholder="可多选"
            style="width: 100%"
          >
            <el-option
              v-for="option in colorSelectOptions"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="尺码" prop="size_ids">
          <el-select
            v-model="generateForm.size_ids"
            multiple
            filterable
            placeholder="可多选"
            style="width: 100%"
          >
            <el-option
              v-for="option in sizeSelectOptions"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="同时建成品物料">
          <el-switch v-model="generateForm.create_material" />
          <div class="ys-muted">
            开启后为每个 SKU 同步创建成品库存物料，保证 SKU 与物料一一对应。
          </div>
        </el-form-item>
        <template v-if="generateForm.create_material">
          <el-form-item label="成品分类" prop="category_id">
            <el-select v-model="generateForm.category_id" filterable style="width: 100%">
              <el-option
                v-for="option in categorySelectOptions"
                :key="String(option.value)"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="基本单位" prop="base_uom_id">
            <el-select v-model="generateForm.base_uom_id" filterable style="width: 100%">
              <el-option
                v-for="option in uomSelectOptions"
                :key="String(option.value)"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
        </template>
      </el-form>

      <el-alert
        v-if="generateResult"
        type="success"
        :closable="false"
        show-icon
        :title="`已生成 ${generateResult.created_count} 个，跳过已存在 ${generateResult.skipped_count} 个`"
      >
        <div class="ys-muted">已存在组合不会被覆盖，也不会产生重复条码。</div>
      </el-alert>

      <template #footer>
        <el-button @click="generateVisible = false">关闭</el-button>
        <el-button type="primary" :loading="generating" @click="submitGenerate">开始生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { skuApi as skuCrudApi } from '@/api/endpoints'
import { post } from '@/api/http'
import {
  colorOptions,
  companyOptions,
  materialCategoryOptions,
  materialOptions,
  sizeOptions,
  styleOptions,
  uomOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import type { EnumOption } from '@/types/models'
import { formatAmount } from '@/utils/decimal'

interface GenerateResult {
  created: string[]
  skipped: string[]
  barcodes: string[]
  created_count: number
  skipped_count: number
}

const auth = useAuthStore()
const pageRef = ref<InstanceType<typeof EntityListPage>>()
const api = skuCrudApi as never

const canGenerate = computed(() => auth.hasPermission('masterdata.sku.generate'))

const columns: ProTableColumn[] = [
  { prop: 'code', label: 'SKU 编码', width: 170, sortable: true },
  { prop: 'style_code', label: '款式', width: 130 },
  { prop: 'color_name', label: '颜色', width: 100 },
  { prop: 'size_name', label: '尺码', width: 90 },
  { prop: 'material_code', label: '对应物料', width: 150 },
  { prop: 'barcode', label: '条码', width: 170 },
  {
    prop: 'reference_cost',
    label: '参考成本',
    width: 120,
    formatter: (row) => formatAmount(row.reference_cost as string),
  },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = [
  { prop: 'style_id', label: '款式', type: 'select' as const, optionsLoader: styleOptions },
  { prop: 'color_id', label: '颜色', type: 'select' as const, optionsLoader: colorOptions },
  { prop: 'size_id', label: '尺码', type: 'select' as const, optionsLoader: sizeOptions },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'style_id', label: '款式', type: 'select', required: true, optionsLoader: styleOptions },
  { prop: 'color_id', label: '颜色', type: 'select', required: true, optionsLoader: colorOptions },
  { prop: 'size_id', label: '尺码', type: 'select', required: true, optionsLoader: sizeOptions },
  { prop: 'material_id', label: '对应物料', type: 'select', optionsLoader: materialOptions },
  { prop: 'code', label: 'SKU 编码', required: true, help: '留空时系统按编号规则自动生成' },
  { prop: 'name', label: 'SKU 名称' },
  { prop: 'barcode', label: '条码', help: '留空则与 SKU 编码相同' },
  { prop: 'safe_stock', label: '安全库存', type: 'decimal', defaultValue: '0' },
  { prop: 'reference_cost', label: '参考成本', type: 'decimal' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const generateVisible = ref(false)
const generating = ref(false)
const generateError = ref('')
const generateResult = ref<GenerateResult | null>(null)
const generateFormRef = ref<FormInstance>()
const generateForm = reactive({
  style_id: null as number | null,
  color_ids: [] as number[],
  size_ids: [] as number[],
  create_material: false,
  category_id: null as number | null,
  base_uom_id: null as number | null,
})

const generateRules: FormRules = {
  style_id: [{ required: true, message: '请选择款式', trigger: 'change' }],
  color_ids: [{ required: true, type: 'array', min: 1, message: '至少选择一个颜色', trigger: 'change' }],
  size_ids: [{ required: true, type: 'array', min: 1, message: '至少选择一个尺码', trigger: 'change' }],
}

const styleSelectOptions = ref<EnumOption[]>([])
const colorSelectOptions = ref<EnumOption[]>([])
const sizeSelectOptions = ref<EnumOption[]>([])
const categorySelectOptions = ref<EnumOption[]>([])
const uomSelectOptions = ref<EnumOption[]>([])

onMounted(async () => {
  const [styles, colors, sizes, categories, uoms] = await Promise.all([
    styleOptions().catch(() => []),
    colorOptions().catch(() => []),
    sizeOptions().catch(() => []),
    materialCategoryOptions().catch(() => []),
    uomOptions().catch(() => []),
  ])
  styleSelectOptions.value = styles
  colorSelectOptions.value = colors
  sizeSelectOptions.value = sizes
  categorySelectOptions.value = categories
  uomSelectOptions.value = uoms
})

async function submitGenerate(): Promise<void> {
  const valid = await generateFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  generating.value = true
  generateError.value = ''
  generateResult.value = null
  try {
    const payload: Record<string, unknown> = {
      style_id: generateForm.style_id,
      color_ids: generateForm.color_ids,
      size_ids: generateForm.size_ids,
      create_material: generateForm.create_material,
    }
    if (generateForm.create_material) {
      payload.category_id = generateForm.category_id
      payload.base_uom_id = generateForm.base_uom_id
    }
    const result = await post<GenerateResult>('/masterdata/skus/generate/', payload)
    generateResult.value = result
    if (result.created_count > 0) {
      ElMessage.success(`已生成 ${result.created_count} 个 SKU`)
    } else {
      ElMessage.info('所选组合已全部存在，未新增 SKU')
    }
    await pageRef.value?.reload()
  } catch (error) {
    generateError.value =
      error instanceof ApiError ? error.fieldErrorMessage || error.message : '生成失败'
  } finally {
    generating.value = false
  }
}
</script>