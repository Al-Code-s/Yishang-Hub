<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">能源看板</h2>
        <p class="ys-page__description">
          按电能分项（计量点）、区域、部门三种口径统计能耗，并用饼图看占比、柱状图看用量与费用对比、曲线图看时间趋势。
          切换维度或日期后图表立即重新汇总，不需要人工做表。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <div class="ys-filter-bar">
      <el-select v-model="medium" style="width: 140px">
        <el-option
          v-for="option in mediaOptions"
          :key="String(option.value)"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-select v-model="dimension" style="width: 190px">
        <el-option
          v-for="option in dimensionOptions"
          :key="option.value"
          :label="option.label"
          :value="option.value"
        />
      </el-select>
      <el-date-picker v-model="start" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" style="width: 150px" />
      <el-date-picker v-model="end" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" style="width: 150px" />
      <el-button type="primary" @click="load">重新统计</el-button>
    </div>

    <div class="ys-stat-cards">
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">区间用量</div>
        <div class="ys-stat__value">{{ formatDecimal(totals.consumption) }}</div>
        <div class="ys-stat__hint">{{ mediumLabel }}</div>
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
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">最大单项占比</div>
        <div class="ys-stat__value">{{ topShare }}</div>
        <div class="ys-stat__hint">{{ topLabel }}</div>
      </el-card>
    </div>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card shadow="never" class="ys-panel">
          <template #header>用量占比</template>
          <energy-chart :option="shareOption" :height="320" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="ys-panel">
          <template #header>用量与费用对比</template>
          <energy-chart :option="barOption" :height="320" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="ys-panel">
      <template #header>用量趋势</template>
      <energy-chart :option="trendOption" :height="300" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import EnergyChart from '@/components/EnergyChart.vue'
import { ApiError } from '@/api/http'
import { energyStatisticsApi } from '@/api/energy'
import { useMetaStore } from '@/stores/meta'
import { formatAmount, formatDecimal } from '@/utils/decimal'
import type { EnergyConsumptionRow } from '@/types/models'

const meta = useMetaStore()

const dimensionOptions = [
  { value: 'meter', label: '电能分项（计量点）' },
  { value: 'area', label: '区域' },
  { value: 'department', label: '部门' },
  { value: 'equipment', label: '设备' },
]

const medium = ref('electricity')
const dimension = ref('meter')
const start = ref('')
const end = ref('')
const rows = ref<EnergyConsumptionRow[]>([])
const trend = ref<EnergyConsumptionRow[]>([])
const totals = ref({ row_count: 0, unpriced: 0, consumption: '0', cost: '0' })
const loading = ref(false)
const errorMessage = ref('')

const mediaOptions = computed(() => meta.options('energy_media'))
const mediumLabel = computed(() => meta.label('energy_media', medium.value))
const topRow = computed(() => rows.value[0])
const topLabel = computed(() => topRow.value?.label ?? '-')
const topShare = computed(() => {
  const total = Number(totals.value.consumption)
  if (!total || !topRow.value) {
    return '-'
  }
  return ((Number(topRow.value.consumption) / total) * 100).toFixed(1) + '%'
})

function rangeParams(): Record<string, unknown> {
  const params: Record<string, unknown> = { medium: medium.value }
  if (start.value) params.start = start.value
  if (end.value) params.end = end.value
  return params
}

/** 图表坐标必须是 number，仅用于绘图；业务口径仍以 Decimal 字符串为准。 */
const shareOption = computed(() => ({
  tooltip: { trigger: 'item' },
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
  tooltip: { trigger: 'axis' },
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

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 60, right: 24, top: 24, bottom: 40 },
  xAxis: { type: 'category', data: trend.value.map((row) => row.label) },
  yAxis: { type: 'value' },
  series: [
    {
      name: '每日用量',
      type: 'line',
      smooth: true,
      areaStyle: {},
      data: trend.value.map((row) => Number(row.consumption)),
    },
  ],
}))

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await energyStatisticsApi.load({ ...rangeParams(), dimension: dimension.value })
    rows.value = payload.rows
    totals.value = payload.totals
    const trendPayload = await energyStatisticsApi.load({ ...rangeParams(), dimension: 'day' })
    trend.value = trendPayload.rows
  } catch (error) {
    rows.value = []
    trend.value = []
    totals.value = { row_count: 0, unpriced: 0, consumption: '0', cost: '0' }
    errorMessage.value = error instanceof ApiError ? error.message : '加载能源看板失败'
  } finally {
    loading.value = false
  }
}

watch([dimension, medium], load)
onMounted(load)
</script>
