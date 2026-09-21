<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">库存单据</h2>
        <p class="ys-page__description">
          收货、出库、移库、调整、质量转换都在这里办理：只有过账后才会真正改变库存，
          冲销必须填写原因；如果原单据增加的库存已经被后续业务用掉，系统会拒绝冲销，需要改走退货或更正流程。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">
          新增单据
        </el-button>
        <el-button v-if="canRelease" @click="openRelease">质量放行</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索单据编号、来源单号或备注"
        clearable
        style="width: 240px"
        @keyup.enter="reload"
      />
      <el-select v-model="filters.document_type" placeholder="单据类型" clearable style="width: 150px">
        <el-option
          v-for="item in meta.options('inventory_document_types')"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
        <el-option
          v-for="item in meta.options('inventory_document_statuses')"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select
        v-model="filters.warehouse_id"
        placeholder="仓库"
        clearable
        filterable
        style="width: 180px"
      >
        <el-option
          v-for="item in warehouseChoices"
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
      <el-table-column prop="document_no" label="单据编号" width="170" />
      <el-table-column label="单据类型" width="120">
        <template #default="{ row }">
          {{ row.document_type_display || row.document_type }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
            {{ row.status_display || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="warehouse_name" label="仓库" width="140" />
      <el-table-column prop="biz_no" label="来源单号" width="150" />
      <el-table-column label="行数" width="80">
        <template #default="{ row }">{{ (row.lines ?? []).length }}</template>
      </el-table-column>
      <el-table-column label="过账时间" width="170">
        <template #default="{ row }">{{ row.posted_at ? formatDateTime(row.posted_at) : '-' }}</template>
      </el-table-column>
      <el-table-column prop="posted_by_name" label="过账人" width="110" />
      <el-table-column prop="remark" label="备注" min-width="140" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="canPost && row.status === 'draft'"
            link
            type="success"
            size="small"
            @click="postDocument(row)"
          >
            过账
          </el-button>
          <el-button
            v-if="canReverse && row.status === 'posted'"
            link
            type="warning"
            size="small"
            @click="reverseDocument(row)"
          >
            冲销
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无库存单据" />
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

    <el-dialog v-model="createVisible" title="新增库存单据" width="900px">
      <el-alert
        v-if="formError"
        type="error"
        :closable="false"
        show-icon
        :title="formError"
        class="ys-form-error"
      />
      <el-form label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="单据类型" required>
              <el-select v-model="form.document_type" style="width: 100%">
                <el-option
                  v-for="item in meta.options('inventory_document_types')"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="仓库" required>
              <el-select v-model="form.warehouse_id" filterable style="width: 100%">
                <el-option
                  v-for="item in warehouseChoices"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源单号">
              <el-input v-model="form.biz_no" placeholder="采购收货单 / 工单等来源编号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注">
              <el-input v-model="form.remark" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <h4 class="ys-section-title">明细行</h4>
      <el-table :data="form.lines" border size="small">
        <el-table-column label="物料" width="200">
          <template #default="{ row }">
            <el-select v-model="row.material_id" filterable size="small" style="width: 100%">
              <el-option
                v-for="item in materialChoices"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="储位" width="180">
          <template #default="{ row }">
            <el-select
              v-model="row.location_id"
              filterable
              clearable
              size="small"
              style="width: 100%"
            >
              <el-option
                v-for="item in locationChoices"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column v-if="form.document_type === 'move'" label="目标储位" width="180">
          <template #default="{ row }">
            <el-select
              v-model="row.target_location_id"
              filterable
              clearable
              size="small"
              style="width: 100%"
            >
              <el-option
                v-for="item in locationChoices"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="批次号" width="130">
          <template #default="{ row }">
            <el-input v-model="row.batch_no" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="卷号" width="120">
          <template #default="{ row }">
            <el-input v-model="row.roll_no" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="质量状态" width="130">
          <template #default="{ row }">
            <el-select v-model="row.quality_status" size="small" style="width: 100%">
              <el-option
                v-for="item in meta.options('quality_statuses')"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column v-if="form.document_type === 'quality'" label="目标质量状态" width="150">
          <template #default="{ row }">
            <el-select v-model="row.target_quality_status" size="small" style="width: 100%">
              <el-option
                v-for="item in meta.options('quality_statuses')"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column v-if="form.document_type === 'adjustment'" label="方向" width="110">
          <template #default="{ row }">
            <el-select v-model="row.direction" size="small" style="width: 100%">
              <el-option
                v-for="item in meta.options('inventory_directions')"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="140">
          <template #default="{ row }">
            <el-input v-model="row.quantity" size="small" placeholder="如 12.50" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ $index }">
            <el-button
              link
              type="danger"
              size="small"
              :disabled="form.lines.length <= 1"
              @click="removeLine($index)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-button link type="primary" :icon="Plus" class="ys-form-add" @click="addLine">
        添加明细行
      </el-button>

      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">保存草稿</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="releaseVisible" title="库存质量放行" width="560px">
      <el-alert
        v-if="releaseError"
        type="error"
        :closable="false"
        show-icon
        :title="releaseError"
        class="ys-form-error"
      />
      <el-form label-width="120px">
        <el-form-item label="仓库" required>
          <el-select v-model="releaseForm.warehouse_id" filterable style="width: 100%">
            <el-option
              v-for="item in warehouseChoices"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="物料" required>
          <el-select v-model="releaseForm.material_id" filterable style="width: 100%">
            <el-option
              v-for="item in materialChoices"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="储位">
          <el-select v-model="releaseForm.location_id" filterable clearable style="width: 100%">
            <el-option
              v-for="item in locationChoices"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="releaseForm.batch_no" />
        </el-form-item>
        <el-form-item label="卷号">
          <el-input v-model="releaseForm.roll_no" />
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input v-model="releaseForm.quantity" placeholder="如 12.50" />
        </el-form-item>
        <el-form-item label="转出状态" required>
          <el-select v-model="releaseForm.from_status" style="width: 100%">
            <el-option
              v-for="item in meta.options('quality_statuses')"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="转入状态" required>
          <el-select v-model="releaseForm.to_status" style="width: 100%">
            <el-option
              v-for="item in meta.options('quality_statuses')"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="依据 / 原因">
          <el-input v-model="releaseForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="releaseVisible = false">取消</el-button>
        <el-button type="primary" :loading="releasing" @click="submitRelease">放行并过账</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="库存单据详情" size="720px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="单据编号">{{ detail.document_no }}</el-descriptions-item>
          <el-descriptions-item label="单据类型">
            {{ detail.document_type_display || detail.document_type }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status_display || detail.status }}</el-descriptions-item>
          <el-descriptions-item label="仓库">{{ detail.warehouse_name }}</el-descriptions-item>
          <el-descriptions-item label="来源单号">{{ detail.biz_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="过账时间">
            {{ detail.posted_at ? formatDateTime(detail.posted_at) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="过账人">{{ detail.posted_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="冲销时间">
            {{ detail.reversed_at ? formatDateTime(detail.reversed_at) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="冲销原因">{{ detail.reverse_reason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="ys-section-title">明细行</h4>
        <el-table :data="detail.lines" border size="small">
          <el-table-column prop="line_no" label="行号" width="70" />
          <el-table-column prop="material_code" label="物料编码" width="130" />
          <el-table-column prop="material_name" label="物料名称" min-width="120" />
          <el-table-column prop="location_code" label="储位" width="110" />
          <el-table-column prop="target_location_code" label="目标储位" width="110" />
          <el-table-column prop="batch_no" label="批次号" width="110" />
          <el-table-column prop="roll_no" label="卷号" width="100" />
          <el-table-column label="质量状态" width="110">
            <template #default="{ row }">
              {{ row.quality_status_display || row.quality_status }}
            </template>
          </el-table-column>
          <el-table-column label="数量" width="130">
            <template #default="{ row }">
              <span class="ys-mono">{{ formatAmount(row.quantity) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="未加载到单据详情" />
    </el-drawer>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { inventoryDocumentApi, locationApi } from '@/api/endpoints'
import { inventoryActionApi } from '@/api/modules'
import { materialOptions, warehouseOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type {
  EnumOption,
  InventoryDocument,
  InventoryDocumentLineInput,
  QualityReleaseInput,
} from '@/types/models'
import { formatAmount, toApiString } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()

interface LineDraft {
  material_id: number | null
  location_id: number | null
  target_location_id: number | null
  batch_no: string
  roll_no: string
  quality_status: string
  target_quality_status: string
  direction: string
  quantity: string
}

const rows = ref<InventoryDocument[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive<{
  search: string
  document_type: string
  status: string
  warehouse_id: number | null
}>({ search: '', document_type: '', status: '', warehouse_id: null })

const warehouseChoices = ref<EnumOption[]>([])
const materialChoices = ref<EnumOption[]>([])
const locationChoices = ref<EnumOption[]>([])

const canCreate = computed(() => auth.hasPermission('wms.document.create'))
const canPost = computed(() => auth.hasPermission('wms.document.post'))
const canReverse = computed(() => auth.hasPermission('wms.document.reverse'))
const canRelease = computed(() => auth.hasPermission('wms.quality.release'))

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

async function loadChoices(): Promise<void> {
  try {
    warehouseChoices.value = await warehouseOptions()
    materialChoices.value = await materialOptions()
    const locations = await locationApi.list({ page_size: 200, is_active: true, ordering: 'code' })
    locationChoices.value = locations.results.map((row) => ({
      value: row.id,
      label: `${row.warehouse_code} / ${row.code} ${row.name}`.trim(),
    }))
  } catch (error) {
    errorMessage.value = toMessage(error, '加载下拉选项失败')
  }
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await inventoryDocumentApi.list({
      page: page.value,
      page_size: pageSize.value,
      ordering: '-id',
      search: filters.search || undefined,
      document_type: filters.document_type || undefined,
      status: filters.status || undefined,
      warehouse_id: filters.warehouse_id ?? undefined,
    })
    rows.value = result.results as InventoryDocument[]
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = toMessage(error, '加载库存单据失败')
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
  filters.document_type = ''
  filters.status = ''
  filters.warehouse_id = null
  reload()
}

function emptyLine(): LineDraft {
  return {
    material_id: null,
    location_id: null,
    target_location_id: null,
    batch_no: '',
    roll_no: '',
    quality_status: 'qualified',
    target_quality_status: '',
    direction: 'in',
    quantity: '',
  }
}

const createVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const form = reactive<{
  document_type: string
  warehouse_id: number | null
  biz_no: string
  remark: string
  lines: LineDraft[]
}>({ document_type: 'receipt', warehouse_id: null, biz_no: '', remark: '', lines: [emptyLine()] })

function openCreate(): void {
  form.document_type = 'receipt'
  form.warehouse_id = warehouseChoices.value[0]?.value as number ?? null
  form.biz_no = ''
  form.remark = ''
  form.lines = [emptyLine()]
  formError.value = ''
  createVisible.value = true
}

function addLine(): void {
  form.lines.push(emptyLine())
}

function removeLine(index: number): void {
  if (form.lines.length <= 1) return
  form.lines.splice(index, 1)
}

function buildLines(): InventoryDocumentLineInput[] {
  return form.lines.map((line) => {
    if (!line.material_id) {
      throw new Error('每一行都必须选择物料')
    }
    if (!line.quantity.trim()) {
      throw new Error('每一行的数量都必须填写')
    }
    return {
      material_id: line.material_id,
      location_id: line.location_id,
      target_location_id: line.target_location_id,
      batch_no: line.batch_no.trim(),
      roll_no: line.roll_no.trim(),
      quality_status: line.quality_status,
      target_quality_status: line.target_quality_status,
      direction: line.direction,
      quantity: toApiString(line.quantity),
    }
  })
}

async function submitCreate(): Promise<void> {
  formError.value = ''
  if (!form.warehouse_id) {
    formError.value = '请选择仓库'
    return
  }
  let lines: InventoryDocumentLineInput[]
  try {
    lines = buildLines()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '明细行不完整'
    return
  }
  submitting.value = true
  try {
    const created = await inventoryDocumentApi.create({
      document_type: form.document_type,
      warehouse_id: form.warehouse_id,
      biz_no: form.biz_no,
      remark: form.remark,
      lines,
    })
    ElMessage.success(`已保存草稿 ${created.document_no}，请核对后过账`)
    createVisible.value = false
    await load()
  } catch (error) {
    formError.value = toMessage(error, '保存库存单据失败')
  } finally {
    submitting.value = false
  }
}

const detailVisible = ref(false)
const detail = ref<InventoryDocument | null>(null)

async function openDetail(row: InventoryDocument): Promise<void> {
  detailVisible.value = true
  detail.value = null
  try {
    detail.value = (await inventoryDocumentApi.retrieve(row.id)) as InventoryDocument
  } catch (error) {
    errorMessage.value = toMessage(error, '加载单据详情失败')
  }
}

async function postDocument(row: InventoryDocument): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `过账后库存立即生效，且不能直接修改。确认过账 ${row.document_no}？`,
      '过账确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    // 幂等键按单据生成：网络重试不会重复扣减库存
    const key = `wms-document-post-${row.id}-${row.version}`
    await inventoryActionApi.postDocument(row.id, '', key)
    ElMessage.success('过账成功')
    await load()
  } catch (error) {
    errorMessage.value = toMessage(error, '过账失败')
  }
}

async function reverseDocument(row: InventoryDocument): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '冲销会写反向补偿流水；若原单据增加的库存已被下游消耗，系统会拒绝冲销。',
      `冲销 ${row.document_no}`,
      { inputPlaceholder: '请填写冲销原因（必填）', inputValidator: (value) => (value ? true : '必须填写原因') },
    )
    reason = result.value
  } catch {
    return
  }
  try {
    await inventoryActionApi.reverseDocument(row.id, reason)
    ElMessage.success('已冲销')
    await load()
  } catch (error) {
    errorMessage.value = toMessage(error, '冲销失败')
  }
}

const releaseVisible = ref(false)
const releasing = ref(false)
const releaseError = ref('')
const releaseForm = reactive<{
  warehouse_id: number | null
  material_id: number | null
  location_id: number | null
  batch_no: string
  roll_no: string
  quantity: string
  from_status: string
  to_status: string
  reason: string
}>({
  warehouse_id: null,
  material_id: null,
  location_id: null,
  batch_no: '',
  roll_no: '',
  quantity: '',
  from_status: 'quarantine',
  to_status: 'qualified',
  reason: '',
})

function openRelease(): void {
  releaseForm.warehouse_id = warehouseChoices.value[0]?.value as number ?? null
  releaseForm.material_id = null
  releaseForm.location_id = null
  releaseForm.batch_no = ''
  releaseForm.roll_no = ''
  releaseForm.quantity = ''
  releaseForm.from_status = 'quarantine'
  releaseForm.to_status = 'qualified'
  releaseForm.reason = ''
  releaseError.value = ''
  releaseVisible.value = true
}

async function submitRelease(): Promise<void> {
  releaseError.value = ''
  if (!releaseForm.warehouse_id || !releaseForm.material_id) {
    releaseError.value = '请选择仓库与物料'
    return
  }
  if (!releaseForm.quantity.trim()) {
    releaseError.value = '请填写放行数量'
    return
  }
  if (releaseForm.from_status === releaseForm.to_status) {
    releaseError.value = '转出与转入的质量状态不能相同'
    return
  }
  releasing.value = true
  try {
    // 公司由后端按仓库归属推导，前端不自由填写组织标识
    const payload: QualityReleaseInput = {
      warehouse_id: releaseForm.warehouse_id,
      material_id: releaseForm.material_id,
      location_id: releaseForm.location_id,
      batch_no: releaseForm.batch_no.trim(),
      roll_no: releaseForm.roll_no.trim(),
      quantity: toApiString(releaseForm.quantity),
      from_status: releaseForm.from_status,
      to_status: releaseForm.to_status,
      reason: releaseForm.reason,
    }
    const document = await inventoryActionApi.releaseQuality(payload)
    ElMessage.success(`质量放行完成：${document.document_no}`)
    releaseVisible.value = false
    await load()
  } catch (error) {
    releaseError.value = toMessage(error, '质量放行失败')
  } finally {
    releasing.value = false
  }
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'posted') return 'success'
  if (status === 'reversed') return 'warning'
  if (status === 'cancelled') return 'danger'
  return 'info'
}

onMounted(async () => {
  await loadChoices()
  await load()
})
</script>