<template>
  <div>
    <entity-list-page
      title="MRP 运算"
      entity-label="MRP 运行"
      description="物料需求运算按「销售需求 → 净需求计算 → 用料清单展开 → 缺料建议」一次算完：可用的供给只认合格库存的可用量（实存量 − 冻结 − 占用）与已批准未到货的采购量。每次运算都保留完整结果，重新运算不会覆盖或改写历史记录。"
      :api="api"
      :columns="columns"
      :filters="filters"
      ref="pageRef"
      readonly
      default-ordering="-id"
      search-placeholder="搜索运行编号或备注"
      empty-text="暂无 MRP 运行记录"
      :page-size="20"
      :action-width="260"
    >
      <template #toolbar>
        <el-button
          v-if="can('planning.mrp.run')"
          type="primary"
          :icon="Plus"
          @click="openRunForm"
        >
          运行 MRP
        </el-button>
      </template>

      <template #column-horizon="{ row }">
        {{ row.horizon_start }} ~ {{ row.horizon_end }}
      </template>
      <template #column-bucket="{ row }">
        {{ row.bucket_display || meta.label('mrp_buckets', String(row.bucket)) }}
      </template>
      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('mrp_run_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-counts="{ row }">
        <span class="ys-count-hint">
          需求 {{ row.demand_count }} · 供给 {{ row.supply_count }} · 建议 {{ row.suggestion_count }}
        </span>
      </template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button link type="success" size="small" @click="openSuggestions(row)">缺料建议</el-button>
        <el-button
          v-if="can('planning.mrp.archive') && row.status === 'completed'"
          link
          type="warning"
          size="small"
          @click="archiveRun(row)"
        >
          归档
        </el-button>
      </template>
    </entity-list-page>

    <el-dialog v-model="formVisible" title="运行 MRP" width="620px" :close-on-click-modal="false">
      <el-alert
        v-if="formError"
        type="error"
        :closable="false"
        show-icon
        :title="formError"
        class="ys-form-error"
      />
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="ys-detail-hint"
        title="需求区间缺省为今天起 90 天；需求日期早于区间起点的销售订单会计入第一个分段，不会被丢弃。"
      />
      <el-form label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="公司" required>
              <el-select v-model="form.company_id" filterable placeholder="选择公司" style="width: 100%">
                <el-option
                  v-for="item in companyChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="需求开始">
              <el-date-picker
                v-model="form.horizon_start"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="缺省为今天"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="需求结束">
              <el-date-picker
                v-model="form.horizon_end"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="缺省为开始 + 90 天"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时间分段">
              <el-select v-model="form.bucket" style="width: 100%">
                <el-option
                  v-for="item in meta.options('mrp_buckets')"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="限定仓库">
              <el-select v-model="form.warehouse_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in warehouseChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" maxlength="255" placeholder="例如：9 月第一次运算" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRun">开始运算</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="`MRP 运行 ${detailRow?.run_no ?? ''}`" size="900px">
      <template v-if="detailRow">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
          <el-descriptions-item label="分段">{{ detailRow.bucket_display }}</el-descriptions-item>
          <el-descriptions-item label="仓库">{{ detailRow.warehouse_name || '全部' }}</el-descriptions-item>
          <el-descriptions-item label="需求区间" :span="2">
            {{ detailRow.horizon_start }} ~ {{ detailRow.horizon_end }}
          </el-descriptions-item>
          <el-descriptions-item label="运算用时">
            {{ detailRow.finished_at || detailRow.started_at || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="3">{{ detailRow.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">运算摘要</el-divider>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="参与物料">{{ summary.item_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="展开层级">{{ summary.level_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="需求行数">{{ summary.demand_line_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="需求合计">{{ formatNumber(summary.demand_quantity ?? '0') }}</el-descriptions-item>
          <el-descriptions-item label="供给行数">{{ summary.supply_line_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="供给合计">{{ formatNumber(summary.supply_quantity ?? '0') }}</el-descriptions-item>
          <el-descriptions-item label="建议行数">{{ summary.suggestion_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="采购建议">
            {{ summary.purchase_suggestion_count ?? 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="生产建议">
            {{ summary.production_suggestion_count ?? 0 }}
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="(summary.unexploded_materials ?? []).length > 0"
          class="ys-detail-hint"
          type="warning"
          :closable="false"
          show-icon
          :title="`以下成品 / 半成品没有生效 BOM，无法展开下级：${(summary.unexploded_materials ?? []).join('、')}`"
        />

        <el-tabs v-model="detailTab" class="ys-detail-tabs">
          <el-tab-pane label="需求行" name="demands">
            <el-table v-loading="detailLoading" :data="demands as never[]" border size="small">
              <el-table-column prop="line_no" label="#" width="50" />
              <el-table-column label="物料" min-width="170">
                <template #default="{ row }">{{ row.material_code }} {{ row.material_name }}</template>
              </el-table-column>
              <el-table-column prop="level" label="层级" width="70" />
              <el-table-column label="来源" width="110">
                <template #default="{ row }">
                  {{ meta.label('mrp_demand_sources', String(row.source_type)) }}
                </template>
              </el-table-column>
              <el-table-column label="来源单号" min-width="150">
                <template #default="{ row }">{{ row.source_no }}#{{ row.source_line_no ?? '-' }}</template>
              </el-table-column>
              <el-table-column prop="quantity" label="数量" width="120" :formatter="numberFormatter" />
              <el-table-column prop="bucket_date" label="分段" width="110" />
              <el-table-column prop="path" label="来源路径" min-width="200" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="供给行" name="supplies">
            <el-table v-loading="detailLoading" :data="supplies as never[]" border size="small">
              <el-table-column prop="line_no" label="#" width="50" />
              <el-table-column label="物料" min-width="170">
                <template #default="{ row }">{{ row.material_code }} {{ row.material_name }}</template>
              </el-table-column>
              <el-table-column label="来源" width="120">
                <template #default="{ row }">
                  {{ meta.label('mrp_supply_sources', String(row.source_type)) }}
                </template>
              </el-table-column>
              <el-table-column prop="quantity" label="数量" width="120" :formatter="numberFormatter" />
              <el-table-column prop="available_date" label="可用日期" width="120" />
              <el-table-column prop="reference_no" label="来源单据" width="150" />
              <el-table-column prop="remark" label="说明" min-width="200" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="缺料建议" name="suggestions">
            <el-table v-loading="detailLoading" :data="suggestions as never[]" border size="small">
              <el-table-column prop="line_no" label="#" width="50" />
              <el-table-column label="物料" min-width="170">
                <template #default="{ row }">{{ row.material_code }} {{ row.material_name }}</template>
              </el-table-column>
              <el-table-column label="类型" width="110">
                <template #default="{ row }">
                  {{ meta.label('mrp_suggestion_types', String(row.suggestion_type)) }}
                </template>
              </el-table-column>
              <el-table-column prop="quantity" label="建议数量" width="120" :formatter="numberFormatter" />
              <el-table-column prop="due_date" label="需求日期" width="120" />
              <el-table-column prop="reason" label="依据" min-width="260" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { mrpRunApi, warehouseApi } from '@/api/endpoints'
import { mrpActionApi } from '@/api/modules'
import { companyOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatNumber, numberFormatter } from '@/utils/decimal'
import type { EnumOption, MrpDemandLine, MrpRun, MrpSupplyLine, MrpSuggestion } from '@/types/models'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const router = useRouter()
const api = mrpRunApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'run_no', label: '运行编号', width: 170, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'bucket', label: '分段', width: 90 },
  { prop: 'horizon', label: '需求区间', minWidth: 200 },
  { prop: 'warehouse_name', label: '仓库', width: 120 },
  { prop: 'counts', label: '明细', width: 230 },
  { prop: 'finished_at', label: '完成时间', width: 170 },
]

const filters = computed(() => [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('mrp_run_statuses'),
  },
  {
    prop: 'bucket',
    label: '分段',
    type: 'select' as const,
    options: meta.options('mrp_buckets'),
  },
])

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)
const warehouseChoices = ref<EnumOption[]>([])
const companyChoices = ref<EnumOption[]>([])
const formVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const form = reactive({
  company_id: null as number | null,
  horizon_start: '',
  horizon_end: '',
  bucket: 'day',
  warehouse_id: null as number | null,
  remark: '',
})

async function loadWarehouses(): Promise<void> {
  try {
    const page = await warehouseApi.list({ page_size: 200, ordering: 'code' })
    warehouseChoices.value = page.results.map((item) => ({
      value: item.id,
      label: `${item.code} ${item.name}`,
    }))
  } catch {
    warehouseChoices.value = []
  }
}

async function loadCompanies(): Promise<void> {
  try {
    companyChoices.value = await companyOptions()
  } catch {
    companyChoices.value = []
  }
}

function openRunForm(): void {
  formError.value = ''
  // 超级管理员账号可能没有归属公司，必须显式选择；普通用户缺省取本人公司。
  form.company_id = auth.user?.company_id ?? null
  form.horizon_start = ''
  form.horizon_end = ''
  form.bucket = meta.options('mrp_buckets')[0]?.value?.toString() ?? 'day'
  form.warehouse_id = null
  form.remark = ''
  formVisible.value = true
}

async function submitRun(): Promise<void> {
  submitting.value = true
  formError.value = ''
  if (!form.company_id) {
    formError.value = '请先选择公司。'
    return
  }
  try {
    const payload: Record<string, unknown> = { bucket: form.bucket, company_id: form.company_id }
    if (form.horizon_start) payload.horizon_start = form.horizon_start
    if (form.horizon_end) payload.horizon_end = form.horizon_end
    if (form.warehouse_id) payload.warehouse_id = form.warehouse_id
    if (form.remark) payload.remark = form.remark
    const run = await mrpActionApi.run(payload)
    formVisible.value = false
    ElMessage.success(`MRP 运行完成：${run.run_no}`)
    pageRef.value?.reload()
    void openDetail(run)
  } catch (error) {
    formError.value = toMessage(error, 'MRP 运行失败，请检查需求区间与 BOM 配置。')
  } finally {
    submitting.value = false
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailTab = ref('demands')
const detailRow = ref<MrpRun | null>(null)
const detailLoading = ref(false)
const demands = ref<MrpDemandLine[]>([])
const supplies = ref<MrpSupplyLine[]>([])
const suggestions = ref<MrpSuggestion[]>([])
const summary = computed(() => detailRow.value?.summary ?? {})

async function openDetail(row: MrpRun): Promise<void> {
  detailRow.value = row
  detailVisible.value = true
  detailLoading.value = true
  demands.value = []
  supplies.value = []
  suggestions.value = []
  try {
    const [demandPage, supplyPage, suggestionPage] = await Promise.all([
      mrpActionApi.demands(row.id, { page_size: 200, ordering: 'line_no' }),
      mrpActionApi.supplies(row.id, { page_size: 200, ordering: 'line_no' }),
      mrpActionApi.suggestions(row.id, { page_size: 200, ordering: 'line_no' }),
    ])
    demands.value = demandPage.results
    supplies.value = supplyPage.results
    suggestions.value = suggestionPage.results
  } catch (error) {
    ElMessage.error(toMessage(error, '加载 MRP 明细失败。'))
  } finally {
    detailLoading.value = false
  }
}

function openSuggestions(row: MrpRun): void {
  void router.push({ path: '/planning/mrp-suggestions', query: { run_id: String(row.id) } })
}

async function archiveRun(row: MrpRun): Promise<void> {
  try {
    const { value } = await ElMessageBox.prompt(
      '归档只改变运行状态，不会删除需求 / 供给 / 建议明细，历史结果仍可追溯。',
      `归档 MRP 运行 ${row.run_no}`,
      { inputPlaceholder: '归档原因（可选）', confirmButtonText: '归档', cancelButtonText: '取消' },
    )
    await mrpActionApi.archive(row.id, value ?? '')
    ElMessage.success('已归档')
    pageRef.value?.reload()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(toMessage(error, '归档失败。'))
  }
}

onMounted(() => {
  void meta.ensureLoaded()
  void loadWarehouses()
  void loadCompanies()
})
</script>

<style scoped>
.ys-count-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>