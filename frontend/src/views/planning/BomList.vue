<template>
  <div>
    <entity-list-page
      title="物料清单（BOM）"
      entity-label="BOM"
      description="BOM（用料清单）是版本化资料：草稿可修改，提交后明细冻结，审核通过后生效。同一「款式 + 颜色尺码范围」同时只有一个生效版本，需要变更时派生新版本——已审核版本的内容不会被改写，已下达的生产工单仍按当时的用料清单执行。"
      :api="api"
      :columns="columns"
      :filters="filters"
      ref="pageRef"
      readonly
      default-ordering="-id"
      search-placeholder="搜索 BOM 编号、款式编码或备注"
      empty-text="暂无 BOM"
      :page-size="20"
      :action-width="330"
    >
      <template #toolbar>
        <el-button
          v-if="can('planning.bom.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增 BOM
        </el-button>
      </template>

      <template #column-style="{ row }">
        {{ row.style_code }} {{ row.style_name }}
      </template>
      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('bom_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('planning.bom.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('planning.bom.submit') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="submitBom(row)"
        >
          提交审批
        </el-button>
        <el-button
          v-if="can('planning.bom.create') && row.status !== 'submitted' && row.status !== 'draft'"
          link
          type="warning"
          size="small"
          @click="deriveVersion(row)"
        >
          派生新版本
        </el-button>
        <el-button link type="info" size="small" @click="openSnapshot(row)">快照</el-button>
        <el-button
          v-if="can('planning.bom.obsolete') && row.status !== 'obsolete' && row.status !== 'submitted'"
          link
          type="danger"
          size="small"
          @click="obsoleteBom(row)"
        >
          作废
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer
      v-model="detailVisible"
      :title="`BOM ${detailRow?.code ?? ''} v${detailRow?.version_no ?? ''}`"
      size="640px"
    >
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="款式">
          {{ detailRow.style_code }} {{ detailRow.style_name }}
        </el-descriptions-item>
        <el-descriptions-item label="范围">{{ detailRow.scope_label }}</el-descriptions-item>
        <el-descriptions-item label="版本号">v{{ detailRow.version_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="生效日期">{{ detailRow.effective_from || '-' }}</el-descriptions-item>
        <el-descriptions-item label="失效日期">{{ detailRow.effective_to || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审核人">{{ detailRow.approved_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审核时间">{{ detailRow.approved_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">用料明细</el-divider>
      <el-table :data="(detailRow?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="用料" min-width="170">
          <template #default="{ row: line }">{{ line.material_code }} {{ line.material_name }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="标准用量" width="110" :formatter="numberFormatter" />
        <el-table-column prop="loss_rate" label="损耗率" width="110" :formatter="numberFormatter" />
        <el-table-column prop="gross_quantity" label="含损耗" width="110" :formatter="numberFormatter" />
        <el-table-column label="类型" width="90">
          <template #default="{ row: line }">
            {{ meta.label('bom_line_types', String(line.line_type)) }}
          </template>
        </el-table-column>
        <el-table-column label="替代行" width="80">
          <template #default="{ row: line }">{{ line.substitute_for_line_no ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="position" label="使用部位" width="100" />
        <el-table-column label="关键用料" width="90">
          <template #default="{ row: line }">{{ line.is_key_material ? '是' : '否' }}</template>
        </el-table-column>
      </el-table>
      <el-alert
        class="ys-detail-hint"
        type="info"
        :closable="false"
        show-icon
        title="含损耗用量由系统按「标准用量 × (1 + 损耗率)」自动计算，不需要手工填写。"
      />
    </el-drawer>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增 BOM' : '编辑 BOM 草稿'"
      width="1000px"
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
      <el-form label-width="110px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="款式" required>
              <el-select
                v-model="form.style_id"
                filterable
                placeholder="选择款式"
                style="width: 100%"
                @change="onStyleChange"
              >
                <el-option
                  v-for="item in styleChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="差异 SKU">
              <el-select v-model="form.sku_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in skuChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="生效日期">
              <el-date-picker
                v-model="form.effective_from"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="失效日期">
              <el-date-picker
                v-model="form.effective_to"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="备注">
              <el-input v-model="form.remark" maxlength="255" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">用料明细（单位成品净用量，至少 0 行）</el-divider>
        <el-table :data="form.lines" border size="small">
          <el-table-column label="用料" min-width="190">
            <template #default="{ row }">
              <el-select v-model="row.material_id" filterable placeholder="选择物料" style="width: 100%">
                <el-option
                  v-for="item in materialChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="标准用量" width="130">
            <template #default="{ row }">
              <el-input v-model="row.quantity" placeholder="0.00" />
            </template>
          </el-table-column>
          <el-table-column label="损耗率" width="120">
            <template #default="{ row }">
              <el-input v-model="row.loss_rate" placeholder="0.05 表示 5%" />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="120">
            <template #default="{ row }">
              <el-select v-model="row.uom_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in uomChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <el-select v-model="row.line_type" style="width: 100%">
                <el-option
                  v-for="item in meta.options('bom_line_types')"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="替代行号" width="110">
            <template #default="{ row }">
              <el-input
                v-model="row.substitute_for_line_no"
                :disabled="row.line_type !== 'substitute'"
                placeholder="行号"
              />
            </template>
          </el-table-column>
          <el-table-column label="使用部位" width="120">
            <template #default="{ row }">
              <el-input v-model="row.position" />
            </template>
          </el-table-column>
          <el-table-column label="关键" width="70">
            <template #default="{ row }">
              <el-switch v-model="row.is_key_material" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.lines.splice($index, 1)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button class="ys-line-add" @click="addLine">添加明细行</el-button>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="snapshotVisible" title="用料清单存档（不可修改）" size="640px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="ys-detail-hint"
        title="存档是生产工单下达时保存的内容。已审核版本不可修改，因此派生新版本不会改变已有存档。"
      />
      <el-table :data="(snapshot?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column prop="material_code" label="物料编码" width="140" />
        <el-table-column prop="quantity" label="净用量" width="110" :formatter="numberFormatter" />
        <el-table-column prop="loss_rate" label="损耗率" width="110" :formatter="numberFormatter" />
        <el-table-column prop="gross_quantity" label="含损耗" width="110" :formatter="numberFormatter" />
        <el-table-column label="关键" width="70">
          <template #default="{ row: line }">{{ line.is_key_material ? '是' : '否' }}</template>
        </el-table-column>
      </el-table>
      <el-divider content-position="left">原始内容</el-divider>
      <pre class="ys-code-block">{{ snapshotText }}</pre>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { bomApi, skuApi } from '@/api/endpoints'
import { bomActionApi } from '@/api/modules'
import { materialOptions, styleOptions, uomOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { Bom, BomInput, BomLineInput, BomSnapshot, EnumOption } from '@/types/models'
import { numberFormatter, toApiString, toEditableText } from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = bomApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: 'BOM 编号', width: 170, sortable: true },
  { prop: 'style', label: '款式', minWidth: 200 },
  { prop: 'scope_label', label: '适用范围', width: 110 },
  { prop: 'version_no', label: '版本', width: 80, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'effective_from', label: '生效日期', width: 120 },
  { prop: 'line_count', label: '明细行', width: 90 },
]

/** 用 computed 而不是快照数组：/api/v1/meta/ 是异步加载的，筛选下拉必须跟着更新。 */
const filters = computed(() => [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('bom_statuses'),
  },
])

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'approved') return 'success'
  if (status === 'submitted') return 'warning'
  if (status === 'rejected' || status === 'obsolete') return 'danger'
  return 'info'
}

// --- 选择项 -----------------------------------------------------------------
const styleChoices = ref<EnumOption[]>([])
const materialChoices = ref<EnumOption[]>([])
const uomChoices = ref<EnumOption[]>([])
const skuChoices = ref<EnumOption[]>([])

async function loadChoices(): Promise<void> {
  const loaded = await Promise.all([styleOptions(), materialOptions(), uomOptions()]).catch(
    () => [[], [], []] as EnumOption[][],
  )
  styleChoices.value = loaded[0]
  materialChoices.value = loaded[1]
  uomChoices.value = loaded[2]
}

async function loadSkuChoices(styleId: number | null): Promise<void> {
  skuChoices.value = []
  if (!styleId) {
    return
  }
  try {
    const page = await skuApi.list({ style_id: styleId, page_size: 200 })
    skuChoices.value = page.results.map((item) => ({
      value: item.id,
      label: `${item.code}`,
    }))
  } catch {
    skuChoices.value = []
  }
}

function onStyleChange(value: number | null): void {
  form.sku_id = null
  void loadSkuChoices(value)
}

// --- 表单 -------------------------------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)
const formVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const editingId = ref<number | null>(null)
const editingVersion = ref(0)

interface BomLineForm {
  material_id: number | null
  quantity: string
  loss_rate: string
  uom_id: number | null
  line_type: string
  substitute_for_line_no: number | null
  position: string
  is_key_material: boolean
  remark: string
}

function emptyLine(): BomLineForm {
  return {
    material_id: null,
    quantity: '',
    loss_rate: '0',
    uom_id: null,
    line_type: 'normal',
    substitute_for_line_no: null,
    position: '',
    is_key_material: false,
    remark: '',
  }
}

const form = reactive({
  style_id: null as number | null,
  sku_id: null as number | null,
  effective_from: '',
  effective_to: '',
  remark: '',
  lines: [emptyLine()] as BomLineForm[],
})

function addLine(): void {
  form.lines.push(emptyLine())
}

function reloadList(): void {
  void pageRef.value?.reload()
}

function openCreate(): void {
  editingId.value = null
  editingVersion.value = 0
  form.style_id = null
  form.sku_id = null
  form.effective_from = ''
  form.effective_to = ''
  form.remark = ''
  form.lines = [emptyLine()]
  formError.value = ''
  void loadSkuChoices(null)
  formVisible.value = true
}

function openEdit(row: Record<string, unknown>): void {
  const bom = row as unknown as Bom
  editingId.value = bom.id
  editingVersion.value = bom.version
  form.style_id = bom.style_id
  form.sku_id = bom.sku_id
  form.effective_from = bom.effective_from ?? ''
  form.effective_to = bom.effective_to ?? ''
  form.remark = bom.remark ?? ''
  form.lines = (bom.lines ?? []).map((line) => ({
    material_id: line.material_id,
    quantity: toEditableText(line.quantity),
    loss_rate: toEditableText(line.loss_rate),
    uom_id: line.uom_id,
    line_type: line.line_type,
    substitute_for_line_no: line.substitute_for_line_no,
    position: line.position,
    is_key_material: line.is_key_material,
    remark: line.remark,
  }))
  if (form.lines.length === 0) {
    form.lines = [emptyLine()]
  }
  formError.value = ''
  void loadSkuChoices(bom.style_id)
  formVisible.value = true
}

/** 明细校验在提交前完成；金额 / 数量最终仍由后端校验。 */
function buildLines(): BomLineInput[] {
  return form.lines.map((line, index) => {
    const position = index + 1
    if (!line.material_id) {
      throw new Error(`第 ${position} 行未选择物料`)
    }
    if (!String(line.quantity ?? '').trim()) {
      throw new Error(`第 ${position} 行未填写标准用量`)
    }
    const payload: BomLineInput = {
      material_id: line.material_id,
      quantity: toApiString(line.quantity),
      loss_rate: toApiString(line.loss_rate || '0', 10),
      line_type: line.line_type,
      position: line.position,
      is_key_material: line.is_key_material,
      remark: line.remark,
    }
    if (line.uom_id) {
      payload.uom_id = line.uom_id
    }
    if (line.line_type === 'substitute') {
      if (!line.substitute_for_line_no) {
        throw new Error(`第 ${position} 行是替代料，必须填写被替代的行号`)
      }
      payload.substitute_for_line_no = Number(line.substitute_for_line_no)
    }
    return payload
  })
}

async function submitForm(): Promise<void> {
  formError.value = ''
  if (!form.style_id) {
    formError.value = '请选择款式'
    return
  }
  if (form.effective_from && form.effective_to && form.effective_to < form.effective_from) {
    formError.value = '失效日期不能早于生效日期'
    return
  }
  let lines: BomLineInput[]
  try {
    lines = buildLines()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '明细不完整'
    return
  }
  submitting.value = true
  try {
    if (editingId.value === null) {
      const payload: BomInput = {
        style_id: form.style_id,
        sku_id: form.sku_id,
        effective_from: form.effective_from || null,
        effective_to: form.effective_to || null,
        remark: form.remark,
        lines,
      }
      const created = await bomApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.code} v${created.version_no}，请提交审批`)
    } else {
      await bomApi.update(editingId.value, {
        effective_from: form.effective_from || null,
        effective_to: form.effective_to || null,
        remark: form.remark,
        lines,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存 BOM 失败')
  } finally {
    submitting.value = false
  }
}

// --- 提交 / 派生 / 作废 ------------------------------------------------------
async function submitBom(row: Record<string, unknown>): Promise<void> {
  let comment = ''
  try {
    const result = await ElMessageBox.prompt(
      '提交后明细冻结，审核结果会自动回写版本状态。',
      `提交 ${String(row.code)}`,
      { inputPlaceholder: '提交说明（可选）', inputValue: '' },
    )
    comment = result.value ?? ''
  } catch {
    return
  }
  try {
    await bomActionApi.submit(Number(row.id), comment)
    ElMessage.success('已提交审批')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '提交审批失败'))
  }
}

async function deriveVersion(row: Record<string, unknown>): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '已审核版本不可直接修改，派生会复制当前明细生成新的草稿版本；审核通过后旧版本自动转为「已作废」，但内容不会被改写。',
      `派生新版本：${String(row.code)}`,
      { type: 'warning', confirmButtonText: '派生', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    const created = await bomActionApi.newVersion(Number(row.id))
    ElMessage.success(`已派生 ${created.code} v${created.version_no}（草稿）`)
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '派生新版本失败'))
  }
}

async function obsoleteBom(row: Record<string, unknown>): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '作废只改变版本状态与启用标记，不物理删除记录；已过账单据不会被回滚。',
      `作废 ${String(row.code)}`,
      {
        inputPlaceholder: '请填写作废原因（必填）',
        inputValidator: (value) => (value ? true : '必须填写原因'),
      },
    )
    reason = result.value
  } catch {
    return
  }
  try {
    await bomActionApi.obsolete(Number(row.id), reason)
    ElMessage.success('已作废')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '作废失败'))
  }
}

// --- 详情与快照 --------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<Bom | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as Bom
  detailVisible.value = true
  try {
    detailRow.value = (await bomApi.retrieve(Number(row.id))) as Bom
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

const snapshotVisible = ref(false)
const snapshot = ref<BomSnapshot | null>(null)
const snapshotText = ref('')

async function openSnapshot(row: Record<string, unknown>): Promise<void> {
  snapshot.value = null
  snapshotText.value = ''
  snapshotVisible.value = true
  try {
    const data = await bomActionApi.snapshot(Number(row.id))
    snapshot.value = data
    snapshotText.value = JSON.stringify(data, null, 2)
  } catch (error) {
    ElMessage.error(toMessage(error, '加载存档失败'))
    snapshotVisible.value = false
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>
