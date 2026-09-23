<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">{{ title }}</h2>
        <p class="ys-page__description">{{ description }}</p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="unpricedCount > 0"
      type="warning"
      :closable="false"
      show-icon
      :title="'有 ' + unpricedCount + ' 个统计对象没有维护对应介质的能源价格，这些行的费用按 0 计，请先到基础管理里补价格。'"
    />
    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <div class="ys-filter-bar">
      <el-select v-model="dimension" style="width: 190px">
        <el-option
          v-for="option in dimensionOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-select v-if="!medium" v-model="mediumFilter" clearable placeholder="全部介质" style="width: 140px">
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
        <div class="ys-stat__label">统计用量</div>
        <div class="ys-stat__value">{{ formatDecimal(totals.consumption) }}</div>
        <div class="ys-stat__hint">{{ rangeHint }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">折算费用</div>
        <div class="ys-stat__value">{{ formatAmount(totals.cost) }}</div>
        <div class="ys-stat__hint">按已维护单价折算</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">统计对象</div>
        <div class="ys-stat__value">{{ totals.row_count }}</div>
        <div class="ys-stat__hint">未维护单价 {{ totals.unpriced }} 个</div>
      </el-card>
    </div>

    <template v-if="isPeriodDimension">
      <h3 class="ys-section-title">用量趋势</h3>
      <el-card shadow="never" class="ys-panel">
        <energy-chart :option="trendOption" :height="320" />
      </el-card>
    </template>
    <template v-else>
      <h3 class="ys-section-title">用量占比</h3>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-card shadow="never" class="ys-panel">
            <energy-chart :option="shareOption" :height="320" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" class="ys-panel">
            <energy-chart :option="barOption" :height="320" />
          </el-card>
        </el-col>
      </el-row>
    </template>

    <h3 class="ys-section-title">统计明细</h3>
    <el-table :data="rows" border stripe empty-text="当前条件下没有用量数据">
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
import { computed, onMounted, ref, watch } from 'vue'
import EnergyChart from '@/components/EnergyChart.vue'
import { ApiError } from '@/api/http'
import { energyStatisticsApi } from '@/api/energy'
import { useMetaStore } from '@/stores/meta'
import { formatAmount, formatDecimal } from '@/utils/decimal'
import type { EnergyConsumptionRow, EnergyStatisticsPayload } from '@/types/models'

/** 图表提示里的数值口径与列表一致：保留 2 位小数（ECharts 默认会打印原始精度）。 */
function chartValue(value: unknown): string {
  return formatDecimal(value as number)
}

/**
 * 能耗统计面板：按维度（计量点/区域/部门/设备/日/月/年）聚合用量与费用。
 *
 * 「用水 / 用电 / 用气 / 用液统计」页面就是把 medium 固定为对应介质后复用本组件，
 * 不存在四套重复的聚合逻辑。维度取值来自后端 /ems/statistics/ 的 dimension 参数，
 * 不是后端枚举字典，因此这些中文标签在前端定义。
 */
const props = defineProps<{ title: string; description: string; medium?: string }>()

const meta = useMetaStore()

const dimensionOptions = [
  { value: 'meter', label: '计量点（电能分项）' },
  { value: 'area', label: '区域' },
  { value: 'department', label: '部门' },
  { value: 'equipment', label: '设备' },
  { value: 'day', label: '按日' },
  { value: 'month', label: '按月' },
  { value: 'year', label: '按年' },
]
const PERIOD_DIMENSIONS = ['day', 'month', 'year']

const dimension = ref('meter')
const mediumFilter = ref<string | null>(props.medium ?? null)
const start = ref('')
const end = ref('')
const rows = ref<EnergyConsumptionRow[]>([])
const totals = ref({ row_count: 0, unpriced: 0, consumption: '0', cost: '0' })
const loading = ref(false)
const errorMessage = ref('')

const mediaOptions = computed(() => meta.options('energy_media'))
const isPeriodDimension = computed(() => PERIOD_DIMENSIONS.includes(dimension.value))
const unpricedCount = computed(() => totals.value.unpriced)
const rangeHint = computed(() => (start.value || end.value ? start.value + ' ~ ' + end.value : '全部日期'))

function currentParams(): Record<string, unknown> {
  const params: Record<string, unknown> = { dimension: dimension.value }
  if (props.medium) {
    params.medium = props.medium
  } else if (mediumFilter.value) {
    params.medium = mediumFilter.value
  }
  if (start.value) params.start = start.value
  if (end.value) params.end = end.value
  return params
}

/** 图表坐标必须是 number，仅用于绘图；业务口径仍以 Decimal 字符串为准。 */
const shareOption = computed(() => ({
  tooltip: { trigger: 'item', valueFormatter: chartValue },
  legend: { bottom: 0, type: 'scroll' },
  series: [
    {
      name: '用量占比',
      type: 'pie',
      radius: ['42%', '70%'],
      data: rows.value.map((row) => ({ name: row.label, value: Number(row.consumption) })),
    },
  ],
}))

const barOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: chartValue },
  legend: { bottom: 0 },
  grid: { left: 60, right: 24, top: 24, bottom: 56 },
  xAxis: {
    type: 'category',
    data: rows.value.map((row) => row.label),
    axisLabel: { rotate: 24, interval: 0 },
  },
  yAxis: { type: 'value' },
  series: [
    { name: '用量', type: 'bar', data: rows.value.map((row) => Number(row.consumption)) },
    { name: '费用', type: 'bar', data: rows.value.map((row) => Number(row.cost)) },
  ],
}))

/**
 * 时间维度的趋势图：**每个介质一条线**。
 *
 * 「全部介质」时后端按 (时间, 介质, 单位) 分行，不能把这些行直接铺在 x 轴上
 * （同一个时间会重复出现多次），更不能把单位不同的用量（kWh / m³ / t）
 * 加成一条线 —— 那样画出来的曲线没有业务含义。介质名后带上单位，便于分别读数。
 */
const trendOption = computed(() => {
  const labels: string[] = []
  const series = new Map<string, { name: string; unit: string; values: (number | null)[] }>()
  for (const row of rows.value) {
    let index = labels.indexOf(row.label)
    if (index === -1) {
      index = labels.length
      labels.push(row.label)
      for (const item of series.values()) {
        item.values.push(null)
      }
    }
    const medium = row.medium_label || row.medium || '用量'
    let entry = series.get(medium)
    if (!entry) {
      entry = { name: medium, unit: row.unit || '', values: labels.map(() => null) }
      series.set(medium, entry)
    }
    entry.values[index] = Number(row.consumption)
  }
  const hasMany = series.size > 1
  return {
    tooltip: { trigger: 'axis', valueFormatter: chartValue },
    legend: hasMany ? { bottom: 0, type: 'scroll' } : undefined,
    grid: { left: 60, right: 24, top: 24, bottom: hasMany ? 56 : 40 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [...series.values()].map((item) => ({
      name: item.unit ? `${item.name}（${item.unit}）` : item.name,
      type: 'line',
      smooth: true,
      areaStyle: hasMany ? undefined : {},
      connectNulls: true,
      data: item.values,
    })),
  }
})

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload: EnergyStatisticsPayload = await energyStatisticsApi.load(currentParams())
    rows.value = payload.rows
    totals.value = payload.totals
  } catch (error) {
    rows.value = []
    totals.value = { row_count: 0, unpriced: 0, consumption: '0', cost: '0' }
    errorMessage.value = error instanceof ApiError ? error.message : '加载能耗统计失败'
  } finally {
    loading.value = false
  }
}

watch(dimension, load)
watch(() => props.medium, (value) => {
  mediumFilter.value = value ?? null
})
onMounted(load)
</script>
