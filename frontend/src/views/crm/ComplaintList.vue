<template>
  <entity-list-page
    title="客户投诉"
    entity-label="投诉"
    description="客户投诉从登记到关闭要走完整闭环：待受理 → 处理中 → 已解决 → 已关闭；跳步会被后端拒绝，不会静默销账。满意度评分来自客户回访，未回访时保持 0（显示为「未评价」），系统不会代客户打分。投诉时间留空时按登记时间记录，也支持回填历史投诉日期。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'crm.complaint.create', update: 'crm.complaint.update' }"
    :transform="transformPayload"
    search-placeholder="搜索投诉编号、主题、内容或客户名称"
    default-ordering="-complained_at"
    :toggleable="false"
    :page-size="20"
    :action-width="240"
    @refresh="loadStatistics"
    ref="pageRef"
  >
    <template #summary>
      <div v-if="statistics" class="ys-stat-cards">
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">投诉总数</div>
          <div class="ys-stat__value">{{ statistics.total }}</div>
          <div class="ys-stat__hint">已关闭 {{ statistics.closed_total }}</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">未关闭</div>
          <div class="ys-stat__value">{{ statistics.open_total }}</div>
          <div class="ys-stat__hint">待受理与处理中合计</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">平均满意度</div>
          <div class="ys-stat__value">{{ statistics.avg_satisfaction ?? '未回访' }}</div>
          <div class="ys-stat__hint">未回访 {{ statistics.unrated_total }} 条，不参与平均分</div>
        </el-card>
      </div>
      <el-card v-if="statistics" shadow="never" class="ys-panel">
        <h3 class="ys-section-title">分布（当前数据范围）</h3>
        <el-table :data="distributionRows" border size="small">
          <el-table-column prop="dimension" label="维度" width="120" />
          <el-table-column label="明细">
            <template #default="{ row }">
              <span v-if="row.items.length === 0" class="ys-muted">暂无数据</span>
              <el-tag
                v-for="item in row.items"
                :key="String(item.value)"
                class="ys-ml-4"
                type="info"
                size="small"
                effect="light"
              >
                {{ item.label }} {{ item.total }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('complaint_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-level="{ row }">
      <el-tag :type="levelTagType(String(row.level))" size="small" effect="light">
        {{ row.level_display || meta.label('complaint_levels', String(row.level)) }}
      </el-tag>
    </template>
    <template #column-complained_at="{ row }">
      {{ formatDateTime(String(row.complained_at ?? '')) }}
    </template>
    <template #column-satisfaction="{ row }">
      <span v-if="Number(row.satisfaction) > 0">{{ row.satisfaction }} 分</span>
      <span v-else class="ys-muted">未评价</span>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canHandle && row.status === 'pending'"
        link
        type="primary"
        size="small"
        @click="openAccept(row)"
      >
        受理
      </el-button>
      <el-button
        v-if="canHandle && row.status === 'handling'"
        link
        type="primary"
        size="small"
        @click="openResolve(row)"
      >
        登记处理结果
      </el-button>
      <el-button
        v-if="canClose && row.status === 'resolved'"
        link
        type="success"
        size="small"
        @click="openClose(row)"
      >
        关闭
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="acceptVisible" title="受理投诉" width="600px" :close-on-click-modal="false">
    <el-alert
      v-if="acceptError"
      type="error"
      :closable="false"
      show-icon
      :title="acceptError"
      class="ys-form-error"
    />
    <el-form :model="acceptForm" label-width="120px">
      <el-form-item label="受理人">
        <el-select v-model="acceptForm.receiver_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="处理人">
        <el-select v-model="acceptForm.handler_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="初步处理措施">
        <el-input
          v-model="acceptForm.measure as string"
          type="textarea"
          :rows="3"
          placeholder="可选：写明已安排的核查动作"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="acceptVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitAccept">确认受理</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="resolveVisible"
    title="登记处理结果"
    width="600px"
    :close-on-click-modal="false"
  >
    <el-alert
      v-if="resolveError"
      type="error"
      :closable="false"
      show-icon
      :title="resolveError"
      class="ys-form-error"
    />
    <el-form :model="resolveForm" label-width="120px">
      <el-form-item label="处理措施" required>
        <el-input
          v-model="resolveForm.measure as string"
          type="textarea"
          :rows="3"
          placeholder="写明原因分析与实际采取的措施"
        />
      </el-form-item>
      <el-form-item label="处理人">
        <el-select v-model="resolveForm.handler_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="客户回访满意度">
        <el-select v-model="resolveForm.satisfaction" clearable style="width: 100%">
          <el-option label="未评价" :value="0" />
          <el-option v-for="score in 5" :key="score" :label="`${score} 分`" :value="score" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="resolveVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitResolve">确认登记</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="closeVisible" title="关闭投诉" width="600px" :close-on-click-modal="false">
    <el-alert
      v-if="closeError"
      type="error"
      :closable="false"
      show-icon
      :title="closeError"
      class="ys-form-error"
    />
    <el-form :model="closeForm" label-width="120px">
      <el-form-item label="关闭说明">
        <el-input
          v-model="closeForm.note as string"
          type="textarea"
          :rows="3"
          placeholder="可选：如客户已确认处理结果"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="closeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitClose">确认关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { complaintStatisticsApi } from '@/api/crm'
import { customerComplaintApi } from '@/api/endpoints'
import { companyOptions, customerOptions, employeeOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { ComplaintStatistics, EnumOption, StatisticsSlice } from '@/types/models'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()
const api = customerComplaintApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canHandle = computed(() => auth.hasPermission('crm.complaint.handle'))
const canClose = computed(() => auth.hasPermission('crm.complaint.close'))

const statistics = ref<ComplaintStatistics | null>(null)

/** 分布面板：把后端的四组统计拼成「维度 / 明细」两列。 */
const distributionRows = computed<{ dimension: string; items: StatisticsSlice[] }[]>(() => {
  const data = statistics.value
  if (!data) return []
  return [
    { dimension: '处理状态', items: data.by_status },
    { dimension: '投诉类型', items: data.by_type },
    { dimension: '投诉级别', items: data.by_level },
    { dimension: '投诉来源', items: data.by_source },
  ]
})

async function loadStatistics(): Promise<void> {
  // 统计只是概览，取不到时不打断列表：宁可少显示一块，也不弹错误窗挡住主流程
  statistics.value = await complaintStatisticsApi.load().catch(() => null)
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'resolved') return 'primary'
  if (status === 'handling') return 'warning'
  return 'danger'
}

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  if (level === 'severe') return 'danger'
  if (level === 'important') return 'warning'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'complaint_no', label: '投诉编号', width: 160, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 150 },
  { prop: 'title', label: '投诉主题', minWidth: 180 },
  { prop: 'complaint_type', label: '类型', width: 110 },
  { prop: 'level', label: '级别', width: 90 },
  { prop: 'status', label: '处理状态', width: 100 },
  { prop: 'source', label: '来源', width: 120 },
  { prop: 'complained_at', label: '投诉时间', width: 170, sortable: true },
  { prop: 'handler_name', label: '处理人', width: 110 },
  { prop: 'satisfaction', label: '回访满意度', width: 120 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'customer_id', label: '客户', type: 'select' as const, optionsLoader: customerOptions },
  {
    prop: 'complaint_type',
    label: '投诉类型',
    type: 'select' as const,
    options: meta.options('complaint_types'),
  },
  {
    prop: 'level',
    label: '投诉级别',
    type: 'select' as const,
    options: meta.options('complaint_levels'),
  },
  {
    prop: 'status',
    label: '处理状态',
    type: 'select' as const,
    options: meta.options('complaint_statuses'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'content', label: '投诉内容' },
  { prop: 'reporter', label: '投诉人' },
  { prop: 'reporter_phone', label: '投诉人电话' },
  { prop: 'related_no', label: '关联单据号' },
  { prop: 'receiver_name', label: '受理人' },
  { prop: 'accepted_at', label: '受理时间' },
  { prop: 'handle_measure', label: '处理措施' },
  { prop: 'resolved_at', label: '解决时间' },
  { prop: 'closed_at', label: '关闭时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'complaint_no',
    label: '投诉编号',
    onlyOnUpdate: true,
    help: '留空时由系统按编号规则（CMPL）自动生成',
  },
  { prop: 'customer_id', label: '客户', type: 'select', required: true, optionsLoader: customerOptions },
  {
    prop: 'complaint_type',
    label: '投诉类型',
    type: 'select',
    options: meta.options('complaint_types'),
    defaultValue: 'quality',
  },
  {
    prop: 'level',
    label: '投诉级别',
    type: 'select',
    options: meta.options('complaint_levels'),
    defaultValue: 'general',
  },
  {
    prop: 'source',
    label: '投诉来源',
    type: 'select',
    options: meta.options('complaint_sources'),
    defaultValue: 'phone',
  },
  { prop: 'title', label: '投诉主题', required: true, span: 24 },
  { prop: 'complained_at', label: '投诉时间', type: 'date', help: '留空时按登记时间记录' },
  { prop: 'reporter', label: '投诉人' },
  { prop: 'reporter_phone', label: '投诉人电话' },
  { prop: 'related_no', label: '关联单据号', help: '如销售订单号、发货单号' },
  { prop: 'receiver_id', label: '受理人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'content', label: '投诉内容', type: 'textarea', required: true, span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const acceptVisible = ref(false)
const acceptError = ref('')
const resolveVisible = ref(false)
const resolveError = ref('')
const closeVisible = ref(false)
const closeError = ref('')
const submitting = ref(false)
const target = ref<Record<string, unknown> | null>(null)
const employeeChoiceOptions = ref<EnumOption[]>([])

const acceptForm = reactive<Record<string, unknown>>({
  receiver_id: null,
  handler_id: null,
  measure: '',
})
const resolveForm = reactive<Record<string, unknown>>({
  measure: '',
  handler_id: null,
  satisfaction: null,
})
const closeForm = reactive<Record<string, unknown>>({ note: '' })

/** 日期型选择器只给到日期；`complained_at` 是时间戳字段，提交前补齐零点。 */
function transformPayload(
  payload: Record<string, unknown>,
  _mode: 'create' | 'update',
): Record<string, unknown> {
  const raw = payload.complained_at
  if (typeof raw === 'string' && raw !== '' && !raw.includes('T')) {
    payload.complained_at = `${raw}T00:00:00`
  }
  return payload
}

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
})

function openAccept(row: Record<string, unknown>): void {
  target.value = row
  acceptError.value = ''
  acceptForm.receiver_id = null
  acceptForm.handler_id = row.handler_id ?? null
  acceptForm.measure = ''
  acceptVisible.value = true
}

function openResolve(row: Record<string, unknown>): void {
  target.value = row
  resolveError.value = ''
  resolveForm.measure = ''
  resolveForm.handler_id = row.handler_id ?? null
  resolveForm.satisfaction = null
  resolveVisible.value = true
}

function openClose(row: Record<string, unknown>): void {
  target.value = row
  closeError.value = ''
  closeForm.note = ''
  closeVisible.value = true
}

async function submitAccept(): Promise<void> {
  const row = target.value
  if (!row) return
  submitting.value = true
  acceptError.value = ''
  try {
    await customerComplaintApi.action(Number(row.id), 'accept', {
      receiver_id: acceptForm.receiver_id,
      handler_id: acceptForm.handler_id,
      measure: acceptForm.measure,
    })
    ElMessage.success('已受理，投诉进入处理中')
    acceptVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    acceptError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function submitResolve(): Promise<void> {
  const row = target.value
  if (!row) return
  if (!String(resolveForm.measure ?? '').trim()) {
    resolveError.value = '登记处理结果必须填写处理措施。'
    return
  }
  submitting.value = true
  resolveError.value = ''
  try {
    await customerComplaintApi.action(Number(row.id), 'resolve', {
      measure: resolveForm.measure,
      handler_id: resolveForm.handler_id,
      satisfaction: resolveForm.satisfaction,
    })
    ElMessage.success('已登记处理结果，投诉进入已解决')
    resolveVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    resolveError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function submitClose(): Promise<void> {
  const row = target.value
  if (!row) return
  submitting.value = true
  closeError.value = ''
  try {
    await customerComplaintApi.action(Number(row.id), 'close', { note: closeForm.note })
    ElMessage.success('投诉已关闭')
    closeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    closeError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(loadStatistics)
</script>
