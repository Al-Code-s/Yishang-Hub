<template>
  <entity-list-page
    title="产品评价"
    entity-label="评价"
    description="客户对已交付产品的评分与反馈：评分 1~5 分由客户给出，不允许留空造分。流程为「待回复 → 已回复 → 已关闭」，回复与关闭都通过动作接口推进，跳步会被后端拒绝。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'crm.product_review.create', update: 'crm.product_review.update' }"
    search-placeholder="搜索评价编号、产品描述、评价内容或客户名称"
    default-ordering="-reviewed_at"
    :toggleable="false"
    :page-size="20"
    :action-width="200"
    @refresh="loadStatistics"
    ref="pageRef"
  >
    <template #summary>
      <div v-if="statistics" class="ys-stat-cards">
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">评价总数</div>
          <div class="ys-stat__value">{{ statistics.total }}</div>
          <div class="ys-stat__hint">已关闭 {{ statistics.closed_total }}</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">待回复</div>
          <div class="ys-stat__value">{{ statistics.pending_total }}</div>
          <div class="ys-stat__hint">回复后进入已回复</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">平均评分</div>
          <div class="ys-stat__value">{{ statistics.avg_score ?? '-' }}</div>
          <div class="ys-stat__hint">满分 5 分，由客户给出</div>
        </el-card>
        <el-card shadow="never" class="ys-stat-card">
          <div class="ys-stat__label">好评率</div>
          <div class="ys-stat__value">{{ statistics.good_rate }}%</div>
          <div class="ys-stat__hint">4 分及以上 {{ statistics.good_total }} 条</div>
        </el-card>
      </div>
      <el-card v-if="statistics" shadow="never" class="ys-panel">
        <h3 class="ys-section-title">评分分布（当前数据范围）</h3>
        <el-table :data="statistics.by_score" border size="small">
          <el-table-column prop="label" label="评分" width="120" />
          <el-table-column prop="total" label="条数" width="120" />
          <el-table-column label="占比">
            <template #default="{ row }">{{ scoreShare(row.total) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('product_review_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-score="{ row }">
      <el-rate :model-value="Number(row.score)" disabled size="small" />
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canReply && row.status === 'pending'"
        link
        type="primary"
        size="small"
        @click="openReply(row)"
      >
        回复
      </el-button>
      <el-button
        v-if="canClose && row.status === 'replied'"
        link
        type="success"
        size="small"
        @click="openClose(row)"
      >
        关闭
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="replyVisible" title="回复评价" width="600px" :close-on-click-modal="false">
    <el-alert
      v-if="replyError"
      type="error"
      :closable="false"
      show-icon
      :title="replyError"
      class="ys-form-error"
    />
    <el-form :model="replyForm" label-width="120px">
      <el-form-item label="回复内容" required>
        <el-input
          v-model="replyForm.reply as string"
          type="textarea"
          :rows="4"
          placeholder="写明对客户反馈的答复与改进说明"
        />
      </el-form-item>
      <el-form-item label="回复人">
        <el-select v-model="replyForm.replier_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="replyVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitReply">确认回复</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="closeVisible" title="关闭评价" width="600px" :close-on-click-modal="false">
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
          placeholder="可选：如客户已确认回复"
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
import { productReviewStatisticsApi } from '@/api/crm'
import { productReviewApi } from '@/api/endpoints'
import {
  companyOptions,
  customerOptions,
  employeeOptions,
  skuOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, ProductReviewStatistics } from '@/types/models'
import { formatDate } from '@/utils/format'

const auth = useAuthStore()
const meta = useMetaStore()
const api = productReviewApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canReply = computed(() => auth.hasPermission('crm.product_review.reply'))
const canClose = computed(() => auth.hasPermission('crm.product_review.close'))

const statistics = ref<ProductReviewStatistics | null>(null)

/** 某一档评分占全部评价的比例（保留 1 位小数）。 */
function scoreShare(total: number): string {
  const all = statistics.value?.total ?? 0
  if (!all) return '-'
  return `${((total / all) * 100).toFixed(1)}%`
}

async function loadStatistics(): Promise<void> {
  // 统计只是概览，取不到时不打断列表
  statistics.value = await productReviewStatisticsApi.load().catch(() => null)
}

function statusTagType(status: string): 'success' | 'warning' | 'info' {
  if (status === 'closed') return 'success'
  if (status === 'replied') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'review_no', label: '评价编号', width: 160, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 150 },
  { prop: 'sku_code', label: 'SKU', width: 140 },
  { prop: 'product_desc', label: '产品/款式', minWidth: 150 },
  { prop: 'score', label: '评分', width: 140 },
  {
    prop: 'reviewed_at',
    label: '评价日期',
    width: 130,
    sortable: true,
    formatter: (row) => formatDate(String(row.reviewed_at ?? '')),
  },
  { prop: 'status', label: '处理状态', width: 110 },
  { prop: 'replier_name', label: '回复人', width: 110 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'customer_id', label: '客户', type: 'select' as const, optionsLoader: customerOptions },
  {
    prop: 'status',
    label: '处理状态',
    type: 'select' as const,
    options: meta.options('product_review_statuses'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'content', label: '评价内容' },
  { prop: 'reviewer_name', label: '评价人' },
  { prop: 'reply', label: '回复内容' },
  { prop: 'replied_at', label: '回复时间' },
  { prop: 'closed_at', label: '关闭时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'review_no',
    label: '评价编号',
    onlyOnUpdate: true,
    help: '留空时由系统按编号规则（PRV）自动生成',
  },
  { prop: 'customer_id', label: '客户', type: 'select', required: true, optionsLoader: customerOptions },
  { prop: 'sku_id', label: '关联 SKU', type: 'select', optionsLoader: skuOptions },
  { prop: 'product_desc', label: '产品/款式描述' },
  {
    prop: 'score',
    label: '评分',
    type: 'select',
    required: true,
    defaultValue: 5,
    options: [1, 2, 3, 4, 5].map((value) => ({ value, label: `${value} 分` })),
  },
  { prop: 'reviewed_at', label: '评价日期', type: 'date', required: true },
  { prop: 'reviewer_name', label: '评价人' },
  { prop: 'content', label: '评价内容', type: 'textarea', required: true, span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const replyVisible = ref(false)
const replyError = ref('')
const closeVisible = ref(false)
const closeError = ref('')
const submitting = ref(false)
const target = ref<Record<string, unknown> | null>(null)
const employeeChoiceOptions = ref<EnumOption[]>([])

const replyForm = reactive<Record<string, unknown>>({ reply: '', replier_id: null })
const closeForm = reactive<Record<string, unknown>>({ note: '' })

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
})

function openReply(row: Record<string, unknown>): void {
  target.value = row
  replyError.value = ''
  replyForm.reply = ''
  replyForm.replier_id = row.replier_id ?? null
  replyVisible.value = true
}

function openClose(row: Record<string, unknown>): void {
  target.value = row
  closeError.value = ''
  closeForm.note = ''
  closeVisible.value = true
}

async function submitReply(): Promise<void> {
  const row = target.value
  if (!row) return
  if (!String(replyForm.reply ?? '').trim()) {
    replyError.value = '回复内容不能为空。'
    return
  }
  submitting.value = true
  replyError.value = ''
  try {
    await productReviewApi.action(Number(row.id), 'reply', {
      reply: replyForm.reply,
      replier_id: replyForm.replier_id,
    })
    ElMessage.success('已回复，评价进入已回复')
    replyVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    replyError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
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
    await productReviewApi.action(Number(row.id), 'close', { note: closeForm.note })
    ElMessage.success('评价已关闭')
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
