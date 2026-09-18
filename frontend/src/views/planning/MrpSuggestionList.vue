<template>
  <div>
    <entity-list-page
      title="缺料与建议"
      entity-label="MRP 建议"
      description="建议来自 MRP 净算结果：采购建议可转成草稿采购申请（仍走采购审批，不产生直接采购承诺）；生产建议需要 MES 工单，属于下一增量，当前明确拒绝转单而不是伪造单据。已转单、已取消的建议不能重复处理。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :initial-filters="initialFilters"
      ref="pageRef"
      readonly
      default-ordering="-id"
      search-placeholder="搜索物料编码、名称或依据"
      empty-text="暂无 MRP 建议"
      :page-size="20"
      :action-width="260"
    >
      <template #column-material="{ row }">
        {{ row.material_code }} {{ row.material_name }}
      </template>
      <template #column-run="{ row }">{{ row.run_no }}#{{ row.line_no }}</template>
      <template #column-suggestion_type="{ row }">
        <el-tag
          :type="row.suggestion_type === 'production' ? 'warning' : 'primary'"
          size="small"
          effect="light"
        >
          {{ row.suggestion_type_display || meta.label('mrp_suggestion_types', String(row.suggestion_type)) }}
        </el-tag>
      </template>
      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('mrp_suggestion_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-quantity="{ row }">{{ row.quantity }} {{ row.uom_name }}</template>
      <template #column-converted="{ row }">
        <span v-if="row.converted_document_no">{{ row.converted_document_no }}</span>
        <span v-else-if="row.cancel_reason">{{ row.cancel_reason }}</span>
        <span v-else>-</span>
      </template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('planning.mrp.convert') && row.convertible"
          link
          type="success"
          size="small"
          @click="convert(row)"
        >
          转采购申请
        </el-button>
        <el-button
          v-if="can('planning.mrp.cancel') && row.status === 'open'"
          link
          type="danger"
          size="small"
          @click="cancel(row)"
        >
          取消
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer v-model="detailVisible" title="MRP 建议详情" size="720px">
      <template v-if="detailRow">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="运行">
            {{ detailRow.run_no }} 第 {{ detailRow.line_no }} 行
          </el-descriptions-item>
          <el-descriptions-item label="类型">{{ detailRow.suggestion_type_display }}</el-descriptions-item>
          <el-descriptions-item label="物料">
            {{ detailRow.material_code }} {{ detailRow.material_name }}
          </el-descriptions-item>
          <el-descriptions-item label="数量">
            {{ detailRow.quantity }} {{ detailRow.uom_name }}
          </el-descriptions-item>
          <el-descriptions-item label="需求日期">{{ detailRow.due_date }}</el-descriptions-item>
          <el-descriptions-item label="分段">{{ detailRow.bucket_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
          <el-descriptions-item label="目标单据">
            {{ detailRow.converted_document_no || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="BOM">
            {{ detailRow.detail?.bom_code ? `${detailRow.detail?.bom_code} v${detailRow.detail?.bom_version_no}` : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="层级">{{ detailRow.detail?.level ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="计算依据" :span="2">{{ detailRow.reason }}</el-descriptions-item>
          <el-descriptions-item label="需求来源" :span="2">
            {{ (detailRow.detail?.demand_sources ?? []).join('、') || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">分段净算过程</el-divider>
        <el-table :data="(detailRow.detail?.trace ?? []) as never[]" border size="small">
          <el-table-column prop="bucket_date" label="分段" width="120" />
          <el-table-column prop="opening" label="期初可用" width="120" />
          <el-table-column prop="supply" label="本段供给" width="120" />
          <el-table-column prop="demand" label="本段需求" width="120" />
          <el-table-column prop="net_requirement" label="本段净需求" width="130" />
          <el-table-column prop="closing" label="期末可用" width="120" />
        </el-table>
        <el-alert
          class="ys-detail-hint"
          type="info"
          :closable="false"
          show-icon
          title="供给只包含合格库存可用量（实存量 − 冻结 − 占用）与已批准采购未收量；冻结与占用不会被当作自由供给重复使用。"
        />
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { mrpSuggestionApi } from '@/api/endpoints'
import { mrpSuggestionActionApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { MrpSuggestion } from '@/types/models'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const route = useRoute()
const api = mrpSuggestionApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

/** 从「MRP 运算」页跳转时按运行过滤，方便直接处理该次运算的缺料清单。 */
const initialFilters = computed<Record<string, unknown>>(() => {
  const runId = route.query.run_id
  return runId ? { run_id: String(runId) } : {}
})

const columns: ProTableColumn[] = [
  { prop: 'run', label: '运行 / 行号', width: 190 },
  { prop: 'material', label: '物料', minWidth: 200 },
  { prop: 'suggestion_type', label: '建议类型', width: 110 },
  { prop: 'quantity', label: '建议数量', width: 150 },
  { prop: 'due_date', label: '需求日期', width: 120 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'converted', label: '转单 / 取消', minWidth: 170 },
  { prop: 'reason', label: '计算依据', minWidth: 260 },
]

const filters = computed(() => [
  {
    prop: 'suggestion_type',
    label: '建议类型',
    type: 'select' as const,
    options: meta.options('mrp_suggestion_types'),
  },
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('mrp_suggestion_statuses'),
  },
])

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'converted') return 'success'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)
const detailVisible = ref(false)
const detailRow = ref<MrpSuggestion | null>(null)

function openDetail(row: MrpSuggestion): void {
  detailRow.value = row
  detailVisible.value = true
}

async function convert(row: MrpSuggestion): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      '将生成一张草稿采购申请（仍需采购审批），不会直接产生采购承诺。',
      `转采购申请：${row.material_code} ${row.quantity}`,
      {
        inputValue: row.due_date,
        inputPlaceholder: '需求日期 YYYY-MM-DD',
        confirmButtonText: '生成草稿申请',
        cancelButtonText: '取消',
      },
    )
    const suggestion = await mrpSuggestionActionApi.convert(row.id, {
      needed_date: value || undefined,
      remark: `MRP ${row.run_no} 第 ${row.line_no} 行建议转单`,
    })
    ElMessage.success(`已生成草稿采购申请 ${suggestion.converted_document_no}`)
    pageRef.value?.reload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(toMessage(error, '转单失败。'))
  }
}

async function cancel(row: MrpSuggestion): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      '取消必须填写原因，原因会写入审计日志。',
      `取消建议：${row.material_code} ${row.quantity}`,
      {
        inputPlaceholder: '取消原因（必填）',
        inputValidator: (text: string) => (text && text.trim() ? true : '请填写取消原因'),
        confirmButtonText: '取消建议',
        cancelButtonText: '返回',
      },
    )
    await mrpSuggestionActionApi.cancel(row.id, value)
    ElMessage.success('建议已取消')
    pageRef.value?.reload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(toMessage(error, '取消失败。'))
  }
}

onMounted(() => {
  void meta.ensureLoaded()
})
</script>