<template>
  <entity-list-page
    title="供应商评价"
    entity-label="评价单"
    description="按质量、技术、响应、交付、成本五个维度给供应商打分。总分由系统按权重快照计算，界面填不了总分：五个维度必须各给一行，没有数据的维度把「原始得分」留空（系统标记为缺失，不会当成 0 分）。缺数据时按所选口径处理——「标注缺失」总分口径不完整因此不给等级，「重新分配有效权重」会把缺数据维度的权重按比例摊给有数据的维度。评价只在草稿状态可改，生效后只能归档。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'srm.evaluation.create', update: 'srm.evaluation.update' }"
    search-placeholder="搜索评价单号或供应商"
    default-ordering="-id"
    :toggleable="false"
    :page-size="20"
    :action-width="300"
    @refresh="loadStatistics"
    ref="pageRef"
  >
    <template #summary>
      <div v-if="statistics" class="ys-stat-cards">
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">评价单</div>
          <div class="ys-stat__value">{{ statistics.total }}</div>
          <div class="ys-stat__hint">
            草稿 {{ statistics.draft_total }} / 已生效 {{ statistics.effective_total }}
          </div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">平均得分</div>
          <div class="ys-stat__value">{{ statistics.avg_total_score ?? '-' }}</div>
          <div class="ys-stat__hint">只统计口径完整的评价（满分 100）</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">未评级</div>
          <div class="ys-stat__value">{{ statistics.ungraded_total }}</div>
          <div class="ys-stat__hint">缺数据且未重分配权重，不贴等级</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">缺失维度</div>
          <div class="ys-stat__value">{{ statistics.line_missing_total }}</div>
          <div class="ys-stat__hint">
            占全部维度行的 {{ statistics.missing_rate }}%（{{ statistics.line_total }} 行）
          </div>
        </el-card>
      </div>
      <el-card v-if="statistics" shadow="never" class="ys-panel">
        <h3 class="ys-section-title">各维度平均分与缺数据（当前数据范围）</h3>
        <el-table :data="statistics.by_dimension" border size="small">
          <el-table-column prop="label" label="维度" width="120" />
          <el-table-column prop="avg_score" label="平均原始得分" width="160" />
          <el-table-column prop="scored_total" label="有数据" width="120" />
          <el-table-column prop="missing_total" label="缺数据" width="120" />
        </el-table>
      </el-card>
      <el-card v-if="statistics" shadow="never" class="ys-panel">
        <h3 class="ys-section-title">等级分布</h3>
        <el-table :data="statistics.by_grade" border size="small">
          <el-table-column prop="label" label="等级" width="160" />
          <el-table-column prop="total" label="条数" width="120" />
        </el-table>
      </el-card>
    </template>

    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('supplier_evaluation_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-total_score="{ row }">
      <span class="ys-mono">{{ row.total_score ?? '未计算' }}</span>
      <el-tag
        v-if="String(row.effective_weight_total) !== '100.00'"
        type="warning"
        size="small"
        effect="light"
        class="ys-ml-4"
      >
        有效权重 {{ row.effective_weight_total }}%
      </el-tag>
    </template>
    <template #column-grade="{ row }">
      <el-tag v-if="row.grade" :type="gradeTagType(String(row.grade))" size="small" effect="dark">
        {{ row.grade }} 级
      </el-tag>
      <span v-else class="ys-muted">未评级</span>
    </template>
    <template #column-missing_dimensions="{ row }">
      <template v-if="missingLabels(row).length">
        <el-tag
          v-for="label in missingLabels(row)"
          :key="label"
          type="danger"
          size="small"
          effect="light"
          class="ys-ml-4"
        >
          {{ label }}缺数据
        </el-tag>
      </template>
      <span v-else class="ys-muted">无</span>
    </template>
    <template #column-weight_config_version="{ row }">
      <span class="ys-muted">v{{ row.weight_config_version }}</span>
    </template>

    <template #row-actions="{ row, reload }">
      <el-button link type="primary" size="small" @click="openDetail(row)">
        {{ row.is_editable ? '录入评分' : '查看依据' }}
      </el-button>
      <el-button
        v-if="canPublish && row.status === 'draft'"
        link
        type="success"
        size="small"
        @click="publish(row, reload)"
      >
        生效
      </el-button>
      <el-button
        v-if="canArchive && row.status !== 'archived'"
        link
        type="warning"
        size="small"
        @click="archive(row, reload)"
      >
        归档
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog
    v-model="scoreVisible"
    :title="scoreReadonly ? '评价依据（只读）' : '录入评分'"
    width="960px"
    :close-on-click-modal="false"
  >
    <el-alert
      v-if="dialogError"
      type="error"
      :closable="false"
      show-icon
      :title="dialogError"
      class="ys-form-error"
    />
    <el-alert
      type="info"
      :closable="false"
      show-icon
      :title="scoreHint"
      class="ys-form-error"
    />
    <el-table :data="scoreRows" size="small" border>
      <el-table-column label="维度" width="100">
        <template #default="{ row }">
          {{ meta.label('supplier_evaluation_dimensions', String(row.dimension)) }}
        </template>
      </el-table-column>
      <el-table-column label="配置权重" width="100">
        <template #default="{ row }">
          <span class="ys-mono">{{ row.weight }}%</span>
        </template>
      </el-table-column>
      <el-table-column label="原始得分" width="150">
        <template #default="{ row }">
          <el-input
            v-if="!scoreReadonly"
            v-model="row.raw_score"
            placeholder="留空 = 没有数据"
          />
          <span v-else class="ys-mono">{{ row.raw_score === null ? '未评分' : row.raw_score }}</span>
        </template>
      </el-table-column>
      <el-table-column label="评分依据（原始观测值）" min-width="200">
        <template #default="{ row }">
          <el-input v-if="!scoreReadonly" v-model="row.note" placeholder="如：到货准时 12 批" />
          <span v-else>{{ row.note || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="有效权重" width="100">
        <template #default="{ row }">
          <span class="ys-mono">{{ row.effective_weight }}%</span>
        </template>
      </el-table-column>
      <el-table-column label="加权得分" width="110">
        <template #default="{ row }">
          <span v-if="row.is_missing" class="ys-muted">缺数据</span>
          <span v-else class="ys-mono">{{ row.weighted_score }}</span>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="!scoreReadonly" class="ys-muted" style="margin-top: 8px">
      保存后由系统按权重快照重算总分、有效权重与等级；没有数据的维度不会被记成 0 分。
    </div>
    <template #footer>
      <el-button @click="scoreVisible = false">关闭</el-button>
      <el-button
        v-if="!scoreReadonly"
        type="primary"
        :loading="submitting"
        @click="submitScores"
      >
        保存评分
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { supplierEvaluationStatisticsApi } from '@/api/srm'
import { supplierEvaluationApi } from '@/api/endpoints'
import { companyOptions, employeeOptions, supplierOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { SupplierEvaluation, SupplierEvaluationStatistics } from '@/types/models'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()
const api = supplierEvaluationApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canUpdate = computed(() => auth.hasPermission('srm.evaluation.update'))
const canPublish = computed(() => auth.hasPermission('srm.evaluation.publish'))
const canArchive = computed(() => auth.hasPermission('srm.evaluation.archive'))

const statistics = ref<SupplierEvaluationStatistics | null>(null)

const scoreVisible = ref(false)
const scoreReadonly = ref(true)
const submitting = ref(false)
const dialogError = ref('')
const target = ref<SupplierEvaluation | null>(null)
const scoreRows = ref<ScoreRow[]>([])

interface ScoreRow {
  dimension: string
  weight: string
  effective_weight: string
  weighted_score: string | null
  is_missing: boolean
  raw_score: string
  note: string
}

const scoreHint = computed(() =>
  scoreReadonly.value
    ? '这是该评价单已保存的评分依据：配置权重、有效权重与加权得分都由系统按权重快照计算。'
    : '五个维度都要给一行；没有数据的维度把「原始得分」留空，系统会标记为缺失（不会当成 0 分）。原始得分范围 0~100。',
)

async function loadStatistics(): Promise<void> {
  // 统计只是概览，取不到时不打断列表
  statistics.value = await supplierEvaluationStatisticsApi.load().catch(() => null)
}

function statusTagType(status: string): 'success' | 'warning' | 'info' {
  if (status === 'effective') return 'success'
  if (status === 'archived') return 'info'
  return 'warning'
}

function gradeTagType(grade: string): 'success' | 'primary' | 'warning' | 'danger' {
  if (grade === 'A') return 'success'
  if (grade === 'B') return 'primary'
  if (grade === 'C') return 'warning'
  return 'danger'
}

function missingLabels(row: Record<string, unknown>): string[] {
  const list = (row.missing_dimensions ?? []) as string[]
  return list.map((dimension) => meta.label('supplier_evaluation_dimensions', dimension))
}

const columns: ProTableColumn[] = [
  { prop: 'evaluation_no', label: '评价单号', width: 170, sortable: true },
  { prop: 'supplier_name', label: '供应商', minWidth: 160 },
  { prop: 'weight_config_version', label: '权重版本', width: 110 },
  { prop: 'total_score', label: '得分', width: 200, sortable: true },
  { prop: 'grade', label: '等级', width: 100 },
  { prop: 'missing_dimensions', label: '缺失维度', minWidth: 160 },
  { prop: 'status', label: '状态', width: 100 },
  {
    prop: 'evaluated_at',
    label: '评价时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.evaluated_at ?? '')) || '-',
  },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'supplier_id', label: '供应商', type: 'select' as const, optionsLoader: supplierOptions },
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('supplier_evaluation_statuses'),
  },
  {
    prop: 'missing_dimension_policy',
    label: '缺数据口径',
    type: 'select' as const,
    options: meta.options('missing_dimension_policies'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'supplier_name', label: '供应商' },
  { prop: 'missing_dimension_policy_display', label: '缺数据口径' },
  { prop: 'effective_weight_total', label: '有效权重合计%' },
  { prop: 'period_start', label: '评价期间起' },
  { prop: 'period_end', label: '评价期间止' },
  { prop: 'evaluated_by_name', label: '评价人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'company_id',
    label: '所属公司',
    type: 'select',
    required: true,
    optionsLoader: companyOptions,
    onlyOnCreate: true,
  },
  {
    prop: 'evaluation_no',
    label: '评价单号',
    onlyOnUpdate: true,
    help: '留空时由系统按编号规则（SEV）自动生成',
  },
  {
    prop: 'supplier_id',
    label: '供应商',
    type: 'select',
    required: true,
    optionsLoader: supplierOptions,
    onlyOnCreate: true,
  },
  {
    prop: 'missing_dimension_policy',
    label: '缺数据口径',
    type: 'select',
    options: meta.options('missing_dimension_policies'),
    help: '标注缺失不重分配权重；重新分配会把缺数据维度的权重摊给有数据的维度',
  },
  { prop: 'period_start', label: '评价期间起', type: 'date' },
  { prop: 'period_end', label: '评价期间止', type: 'date' },
  {
    prop: 'evaluated_by_id',
    label: '评价人',
    type: 'select',
    optionsLoader: employeeOptions,
    onlyOnCreate: true,
  },
  { prop: 'evaluated_at', label: '评价时间', type: 'datetime', onlyOnCreate: true },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

function openDetail(row: Record<string, unknown>): void {
  void loadDetail(row)
}

async function loadDetail(row: Record<string, unknown>): Promise<void> {
  dialogError.value = ''
  scoreRows.value = []
  try {
    const detail = await supplierEvaluationApi.retrieve(Number(row.id))
    target.value = detail
    scoreReadonly.value = !(detail.is_editable && canUpdate.value)
    const existing = new Map<string, { raw_score: string; note: string }>()
    for (const line of detail.lines ?? []) {
      const observation = (line.raw_observation ?? {}) as Record<string, unknown>
      existing.set(String(line.dimension), {
        raw_score: line.raw_score === null || line.raw_score === undefined ? '' : String(line.raw_score),
        note: observation.note === undefined ? '' : String(observation.note),
      })
    }
    scoreRows.value = dimensionKeys().map((dimension) => {
      const saved = existing.get(dimension)
      const weight = String((detail.weight_snapshot ?? {})[dimension] ?? '0.00')
      const line = (detail.lines ?? []).find((item) => item.dimension === dimension)
      return {
        dimension,
        weight,
        effective_weight: line ? String(line.effective_weight) : '0.00',
        weighted_score: line && line.weighted_score !== null ? String(line.weighted_score) : null,
        is_missing: line ? Boolean(line.is_missing) : false,
        raw_score: saved?.raw_score ?? '',
        note: saved?.note ?? '',
      }
    })
    scoreVisible.value = true
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '加载评价明细失败')
  }
}

/** 维度顺序以后端字典为准，避免前端写死一套顺序。 */
function dimensionKeys(): string[] {
  return meta.options('supplier_evaluation_dimensions').map((option) => String(option.value))
}

function buildLines(): { lines: Record<string, unknown>[] } | { error: string } {
  const rows: Record<string, unknown>[] = []
  for (const row of scoreRows.value) {
    const text = String(row.raw_score ?? '').trim()
    let score: string | null = null
    if (text) {
      const value = Number(text)
      if (Number.isNaN(value) || value < 0 || value > 100) {
        const label = meta.label('supplier_evaluation_dimensions', row.dimension)
        return { error: `${label}的原始得分必须在 0~100 之间（留空表示没有数据）。` }
      }
      score = text
    }
    const observation: Record<string, unknown> = {}
    const note = String(row.note ?? '').trim()
    if (note) {
      observation.note = note
    }
    rows.push({ dimension: row.dimension, raw_score: score, raw_observation: observation })
  }
  return { lines: rows }
}

async function submitScores(): Promise<void> {
  const current = target.value
  if (!current) {
    return
  }
  const payload = buildLines()
  if ('error' in payload) {
    dialogError.value = payload.error
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await supplierEvaluationApi.action(Number(current.id), 'lines', { lines: payload.lines })
    ElMessage.success('评分已保存，总分由系统重算')
    await loadDetail(current as unknown as Record<string, unknown>)
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function publish(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await supplierEvaluationApi.action(Number(row.id), 'publish', {})
    ElMessage.success('评价已生效')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '生效失败')
  }
}

async function archive(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await supplierEvaluationApi.action(Number(row.id), 'archive', {})
    ElMessage.success('评价已归档')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '归档失败')
  }
}

onMounted(loadStatistics)
</script>
