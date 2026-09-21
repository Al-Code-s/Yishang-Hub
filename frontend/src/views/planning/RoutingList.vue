<template>
  <div>
    <entity-list-page
      title="工艺路线"
      entity-label="工艺路线"
      description="工艺路线（工序顺序）与用料清单使用同一套版本规则：草稿可改、提交冻结、审核通过后生效；同一「款式 + 颜色尺码范围」同时只有一个生效版本。工序上的质检点（例如「检验」）用于在生产现场生成检验记录。"
      :api="api"
      :columns="columns"
      :filters="filters"
      ref="pageRef"
      readonly
      default-ordering="-id"
      search-placeholder="搜索工艺编号、款式编码或备注"
      empty-text="暂无工艺路线"
      :page-size="20"
      :action-width="330"
    >
      <template #toolbar>
        <el-button
          v-if="can('planning.routing.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增工艺路线
        </el-button>
      </template>

      <template #column-style="{ row }">
        {{ row.style_code }} {{ row.style_name }}
      </template>
      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('routing_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-step_count="{ row }">
        {{ (row.steps ?? []).length }}
      </template>
      <template #column-quality_gate_count="{ row }">{{ qualityGateCount(row) }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('planning.routing.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('planning.routing.submit') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="submitRouting(row)"
        >
          提交审批
        </el-button>
        <el-button
          v-if="can('planning.routing.create') && row.status !== 'submitted' && row.status !== 'draft'"
          link
          type="warning"
          size="small"
          @click="deriveVersion(row)"
        >
          派生新版本
        </el-button>
        <el-button link type="info" size="small" @click="openSnapshot(row)">快照</el-button>
        <el-button
          v-if="
            can('planning.routing.obsolete') && row.status !== 'obsolete' && row.status !== 'submitted'
          "
          link
          type="danger"
          size="small"
          @click="obsoleteRouting(row)"
        >
          作废
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer
      v-model="detailVisible"
      :title="`工艺路线 ${detailRow?.code ?? ''} v${detailRow?.version_no ?? ''}`"
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
        <el-descriptions-item label="工序数">{{ detailRow.step_count }}</el-descriptions-item>
        <el-descriptions-item label="质检点">{{ detailRow.quality_gate_count }}</el-descriptions-item>
        <el-descriptions-item label="审核人">{{ detailRow.approved_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审核时间">{{ detailRow.approved_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">工序明细</el-divider>
      <el-table :data="(detailRow?.steps ?? []) as never[]" border size="small">
        <el-table-column prop="sequence" label="顺序" width="70" />
        <el-table-column prop="name" label="工序" width="110" />
        <el-table-column prop="workshop_name" label="车间" width="120" />
        <el-table-column prop="workcenter" label="工作中心" width="120" />
        <el-table-column
          prop="standard_hours"
          label="标准工时"
          width="110"
          :formatter="numberFormatter"
        />
        <el-table-column label="质检点" width="80">
          <template #default="{ row: step }">{{ step.is_quality_gate ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="外协" width="70">
          <template #default="{ row: step }">{{ step.is_outsourced ? '是' : '否' }}</template>
        </el-table-column>
      </el-table>
      <el-alert
        class="ys-detail-hint"
        type="info"
        :closable="false"
        show-icon
        title="标准工时为单件工时（小时），用于计算设备综合效率与工序效率；数据缺失时显示「无法计算」，不会给出无依据的数字。"
      />
    </el-drawer>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增工艺路线' : '编辑工艺路线草稿'"
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

        <el-divider content-position="left">工序（留空则套用默认工艺：裁剪 → 缝制 → 整烫 → 检验 → 包装）</el-divider>
        <el-table :data="form.steps" border size="small">
          <el-table-column label="顺序" width="90">
            <template #default="{ row }">
              <el-input v-model="row.sequence" placeholder="自动" />
            </template>
          </el-table-column>
          <el-table-column label="工序名称" min-width="130">
            <template #default="{ row }">
              <el-input v-model="row.name" />
            </template>
          </el-table-column>
          <el-table-column label="车间" width="170">
            <template #default="{ row }">
              <el-select v-model="row.workshop_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in workshopChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="工作中心" width="140">
            <template #default="{ row }">
              <el-input v-model="row.workcenter" />
            </template>
          </el-table-column>
          <el-table-column label="标准工时" width="120">
            <template #default="{ row }">
              <el-input v-model="row.standard_hours" placeholder="小时，如 0.50" />
            </template>
          </el-table-column>
          <el-table-column label="质检点" width="80">
            <template #default="{ row }">
              <el-switch v-model="row.is_quality_gate" />
            </template>
          </el-table-column>
          <el-table-column label="外协" width="70">
            <template #default="{ row }">
              <el-switch v-model="row.is_outsourced" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.steps.splice($index, 1)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button class="ys-line-add" @click="addStep">添加工序</el-button>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="snapshotVisible" title="工艺路线存档（不可修改）" size="640px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="ys-detail-hint"
        title="存档是生产工单下达时保存的内容。已审核版本不可修改，因此派生新版本不会改变已有存档。"
      />
      <el-table :data="(snapshot?.steps ?? []) as never[]" border size="small">
        <el-table-column prop="sequence" label="顺序" width="70" />
        <el-table-column prop="name" label="工序" width="110" />
        <el-table-column
          prop="standard_hours"
          label="标准工时"
          width="110"
          :formatter="numberFormatter"
        />
        <el-table-column label="质检点" width="80">
          <template #default="{ row: step }">{{ step.is_quality_gate ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="外协" width="70">
          <template #default="{ row: step }">{{ step.is_outsourced ? '是' : '否' }}</template>
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
import { routingApi, skuApi } from '@/api/endpoints'
import { routingActionApi } from '@/api/modules'
import { styleOptions, workshopOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, Routing, RoutingInput, RoutingSnapshot, RoutingStepInput } from '@/types/models'
import { numberFormatter, toApiString, toEditableText } from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = routingApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '工艺编号', width: 170, sortable: true },
  { prop: 'style', label: '款式', minWidth: 200 },
  { prop: 'scope_label', label: '适用范围', width: 110 },
  { prop: 'version_no', label: '版本', width: 80, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'step_count', label: '工序数', width: 90 },
  { prop: 'quality_gate_count', label: '质检点', width: 90 },
]

/** computed：/api/v1/meta/ 异步加载完成后筛选下拉自动更新。 */
const filters = computed(() => [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('routing_statuses'),
  },
])

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'approved') return 'success'
  if (status === 'submitted') return 'warning'
  if (status === 'rejected' || status === 'obsolete') return 'danger'
  return 'info'
}

/** 质检点数量：由工序的 is_quality_gate 汇总，不在前端写死工序名称。 */
function qualityGateCount(row: Record<string, unknown>): number {
  const steps = (row.steps ?? []) as Routing['steps']
  return steps.filter((step) => step.is_quality_gate).length
}

// --- 选择项 -----------------------------------------------------------------
const styleChoices = ref<EnumOption[]>([])
const workshopChoices = ref<EnumOption[]>([])
const skuChoices = ref<EnumOption[]>([])

async function loadChoices(): Promise<void> {
  const loaded = await Promise.all([styleOptions(), workshopOptions()]).catch(
    () => [[], []] as EnumOption[][],
  )
  styleChoices.value = loaded[0]
  workshopChoices.value = loaded[1]
}

async function loadSkuChoices(styleId: number | null): Promise<void> {
  skuChoices.value = []
  if (!styleId) {
    return
  }
  try {
    const page = await skuApi.list({ style_id: styleId, page_size: 200 })
    skuChoices.value = page.results.map((item) => ({ value: item.id, label: item.code }))
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

interface StepForm {
  sequence: string
  name: string
  workshop_id: number | null
  workcenter: string
  equipment_requirement: string
  standard_hours: string
  is_quality_gate: boolean
  is_outsourced: boolean
  remark: string
}

function emptyStep(): StepForm {
  return {
    sequence: '',
    name: '',
    workshop_id: null,
    workcenter: '',
    equipment_requirement: '',
    standard_hours: '0',
    is_quality_gate: false,
    is_outsourced: false,
    remark: '',
  }
}

const form = reactive({
  style_id: null as number | null,
  sku_id: null as number | null,
  effective_from: '',
  effective_to: '',
  remark: '',
  steps: [] as StepForm[],
})

function addStep(): void {
  form.steps.push(emptyStep())
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
  // 新建时不预置工序：留空由后端套用默认工艺，避免前端与后端默认值不一致
  form.steps = []
  formError.value = ''
  void loadSkuChoices(null)
  formVisible.value = true
}

function openEdit(row: Record<string, unknown>): void {
  const routing = row as unknown as Routing
  editingId.value = routing.id
  editingVersion.value = routing.version
  form.style_id = routing.style_id
  form.sku_id = routing.sku_id
  form.effective_from = routing.effective_from ?? ''
  form.effective_to = routing.effective_to ?? ''
  form.remark = routing.remark ?? ''
  form.steps = (routing.steps ?? []).map((step) => ({
    sequence: String(step.sequence),
    name: step.name,
    workshop_id: step.workshop_id,
    workcenter: step.workcenter,
    equipment_requirement: step.equipment_requirement,
    standard_hours: toEditableText(step.standard_hours),
    is_quality_gate: step.is_quality_gate,
    is_outsourced: step.is_outsourced,
    remark: step.remark,
  }))
  formError.value = ''
  void loadSkuChoices(routing.style_id)
  formVisible.value = true
}

function buildSteps(): RoutingStepInput[] | undefined {
  if (form.steps.length === 0) {
    return undefined
  }
  return form.steps.map((step, index) => {
    const position = index + 1
    if (!String(step.name ?? '').trim()) {
      throw new Error(`第 ${position} 道工序未填写名称`)
    }
    const payload: RoutingStepInput = {
      name: step.name.trim(),
      workcenter: step.workcenter,
      equipment_requirement: step.equipment_requirement,
      standard_hours: toApiString(step.standard_hours || '0'),
      is_quality_gate: step.is_quality_gate,
      is_outsourced: step.is_outsourced,
      remark: step.remark,
    }
    if (String(step.sequence ?? '').trim()) {
      payload.sequence = Number(step.sequence)
    }
    if (step.workshop_id) {
      payload.workshop_id = step.workshop_id
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
  let steps: RoutingStepInput[] | undefined
  try {
    steps = buildSteps()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '工序不完整'
    return
  }
  submitting.value = true
  try {
    if (editingId.value === null) {
      const payload: RoutingInput = {
        style_id: form.style_id,
        sku_id: form.sku_id,
        effective_from: form.effective_from || null,
        effective_to: form.effective_to || null,
        remark: form.remark,
      }
      if (steps) {
        payload.steps = steps
      }
      const created = await routingApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.code} v${created.version_no}，请提交审批`)
    } else {
      await routingApi.update(editingId.value, {
        effective_from: form.effective_from || null,
        effective_to: form.effective_to || null,
        remark: form.remark,
        steps,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存工艺路线失败')
  } finally {
    submitting.value = false
  }
}

// --- 提交 / 派生 / 作废 ------------------------------------------------------
async function submitRouting(row: Record<string, unknown>): Promise<void> {
  let comment = ''
  try {
    const result = await ElMessageBox.prompt(
      '提交后工序冻结，审核结果会自动回写版本状态。',
      `提交 ${String(row.code)}`,
      { inputPlaceholder: '提交说明（可选）', inputValue: '' },
    )
    comment = result.value ?? ''
  } catch {
    return
  }
  try {
    await routingActionApi.submit(Number(row.id), comment)
    ElMessage.success('已提交审批')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '提交审批失败'))
  }
}

async function deriveVersion(row: Record<string, unknown>): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '派生会复制当前工序生成新的草稿版本；新版本审核通过后旧版本自动转为「已作废」，内容与已有存档不会被改写。',
      `派生新版本：${String(row.code)}`,
      { type: 'warning', confirmButtonText: '派生', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    const created = await routingActionApi.newVersion(Number(row.id))
    ElMessage.success(`已派生 ${created.code} v${created.version_no}（草稿）`)
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '派生新版本失败'))
  }
}

async function obsoleteRouting(row: Record<string, unknown>): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '作废只改变版本状态与启用标记，不物理删除记录。',
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
    await routingActionApi.obsolete(Number(row.id), reason)
    ElMessage.success('已作废')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '作废失败'))
  }
}

// --- 详情与快照 --------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<Routing | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as Routing
  detailVisible.value = true
  try {
    detailRow.value = (await routingApi.retrieve(Number(row.id))) as Routing
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

const snapshotVisible = ref(false)
const snapshot = ref<RoutingSnapshot | null>(null)
const snapshotText = ref('')

async function openSnapshot(row: Record<string, unknown>): Promise<void> {
  snapshot.value = null
  snapshotText.value = ''
  snapshotVisible.value = true
  try {
    const data = await routingActionApi.snapshot(Number(row.id))
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
