<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">能耗报表</h2>
        <p class="ys-page__description">
          按日、月、年输出接入计量点的用能统计；选择单一介质时还会给出尖峰平谷分时段用量。
          点「导出 Excel」下载的是后端用 openpyxl 生成的真实 xlsx 文件，不是改后缀的 CSV，导出动作会写入审计日志。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :loading="exporting" @click="exportXlsx">导出 Excel</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />
    <el-alert
      v-if="totals.unpriced > 0"
      type="warning"
      :closable="false"
      show-icon
      :title="'有 ' + totals.unpriced + ' 个统计对象未维护单价，费用按 0 计；请先到基础管理的水价/电价/气价/液价页面补齐。'"
    />

    <div class="ys-filter-bar">
      <el-select v-model="period" style="width: 130px">
        <el-option v-for="option in periodOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-select v-model="medium" clearable placeholder="全部介质" style="width: 140px">
        <el-option
          v-for="option in mediaOptions"
          :key="String(option.value)"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-date-picker v-model="start" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width: 150px" />
      <el-date-picker v-model="end" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width: 150px" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <div class="ys-stat-cards">
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">统计口径</div>
        <div class="ys-stat__value">{{ periodLabel }}</div>
        <div class="ys-stat__hint">{{ medium ? mediumLabel : '全部介质' }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">区间用量</div>
        <div class="ys-stat__value">{{ formatDecimal(totals.consumption) }}</div>
        <div class="ys-stat__hint">{{ rangeHint }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">折算费用</div>
        <div class="ys-stat__value">{{ formatAmount(totals.cost) }}</div>
        <div class="ys-stat__hint">按已维护单价折算</div>
      </el-card>
    </div>

    <template v-if="peakValley.length > 0">
      <h3 class="ys-section-title">尖峰平谷分时段用量</h3>
      <el-row :gutter="12">
        <el-col :span="14">
          <el-card shadow="never" class="ys-panel">
            <energy-chart :option="peakValleyOption" :height="300" />
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-table :data="peakValley" border stripe>
            <el-table-column prop="period_label" label="时段" width="100" />
            <el-table-column prop="label" label="区间" min-width="120" />
            <el-table-column label="用量" min-width="120">
              <template #default="{ row }">{{ formatDecimal(row.consumption) }}</template>
            </el-table-column>
          </el-table>
        </el-col>
      </el-row>
    </template>

    <h3 class="ys-section-title">报表明细</h3>
    <el-table :data="rows" border stripe empty-text="当前条件下没有用能数据">
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="label" label="名称" min-width="180" />
      <el-table-column prop="medium_label" label="介质" width="90" />
      <el-table-column label="用量" min-width="130">
        <template #default="{ row }">{{ formatDecimal(row.consumption) }}</template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="90" />
      <el-table-column label="费用" min-width="130">
        <template #default="{ row }">{{ formatAmount(row.cost) }}</template>
      </el-table-column>
      <el-table-column label="单价" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.priced" type="success" size="small" effect="light">已维护</el-tag>
          <el-tag v-else type="warning" size="small" effect="light">未维护单价</el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EnergyChart from '@/components/EnergyChart.vue'
import { ApiError } from '@/api/http'
import { energyReportApi, saveBlob } from '@/api/energy'
import { useMetaStore } from '@/stores/meta'
import { formatAmount, formatDecimal } from '@/utils/decimal'
import type { EnergyConsumptionRow, EnergyReportPayload } from '@/types/models'

/** 图表提示里的数值口径与列表一致：保留 2 位小数（ECharts 默认会打印原始精度）。 */
function chartValue(value: unknown): string {
  return formatDecimal(value as number)
}

const meta = useMetaStore()

const periodOptions = [
  { value: 'day', label: '按日' },
  { value: 'month', label: '按月' },
  { value: 'year', label: '按年' },
]

const period = ref('month')
const medium = ref<string | null>(null)
const start = ref('')
const end = ref('')
const rows = ref<EnergyConsumptionRow[]>([])
const peakValley = ref<EnergyReportPayload['peak_valley']>([])
const totals = ref({ consumption: '0', cost: '0', unpriced: 0 })
const loading = ref(false)
const exporting = ref(false)
const errorMessage = ref('')

const mediaOptions = computed(() => meta.options('energy_media'))
const periodLabel = computed(
  () => periodOptions.find((item) => item.value === period.value)?.label ?? '-',
)
const mediumLabel = computed(() => meta.label('energy_media', medium.value))
const rangeHint = computed(() => (start.value || end.value ? start.value + ' ~ ' + end.value : '全部日期'))

function currentParams(): Record<string, unknown> {
  const params: Record<string, unknown> = { period: period.value }
  if (medium.value) params.medium = medium.value
  if (start.value) params.start = start.value
  if (end.value) params.end = end.value
  return params
}

/** 图表坐标必须是 number，仅用于绘图；业务口径仍以 Decimal 字符串为准。 */
const peakValleyOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: chartValue },
  grid: { left: 60, right: 24, top: 24, bottom: 40 },
  xAxis: { type: 'category', data: peakValley.value.map((item) => item.label) },
  yAxis: { type: 'value' },
  series: [
    {
      name: '用量',
      type: 'bar',
      data: peakValley.value.map((item) => Number(item.consumption)),
    },
  ],
}))

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await energyReportApi.load(currentParams())
    rows.value = payload.rows
    peakValley.value = payload.peak_valley
    totals.value = payload.totals
  } catch (error) {
    rows.value = []
    peakValley.value = []
    totals.value = { consumption: '0', cost: '0', unpriced: 0 }
    errorMessage.value = error instanceof ApiError ? error.message : '加载能耗报表失败'
  } finally {
    loading.value = false
  }
}

async function exportXlsx(): Promise<void> {
  exporting.value = true
  try {
    const blob = await energyReportApi.exportXlsx(currentParams())
    saveBlob(blob, 'energy-report-' + period.value + '.xlsx')
    ElMessage.success('报表已导出')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>
