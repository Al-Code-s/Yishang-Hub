<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">能源首页</h2>
        <p class="ys-page__description">
          今日与本月的水、电、气、液用量与费用，仪表在线情况、未处理报警，以及近 14 天用量趋势。
          费用按已维护的能源价格折算；未维护单价的介质费用计 0，并在能耗统计页明确标注「未维护单价」，
          不会用默认价凑出一份看起来完整的成本表。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button v-if="canViewMonitor" @click="goto('/ems/monitor')">设备监控</el-button>
        <el-button v-if="canViewReport" @click="goto('/ems/report')">能耗报表</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <div class="ys-stat-cards">
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">今日用量（全部介质）</div>
        <div class="ys-stat__value">{{ formatDecimal(summary?.today.total_consumption) }}</div>
        <div class="ys-stat__hint">{{ summary ? summary.today.start : '-' }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">今日费用</div>
        <div class="ys-stat__value">{{ formatAmount(summary?.today.total_cost) }}</div>
        <div class="ys-stat__hint">按已维护单价折算</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">本月用量</div>
        <div class="ys-stat__value">{{ formatDecimal(summary?.month.total_consumption) }}</div>
        <div class="ys-stat__hint">{{ monthRange }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">本月费用</div>
        <div class="ys-stat__value">{{ formatAmount(summary?.month.total_cost) }}</div>
        <div class="ys-stat__hint">按已维护单价折算</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">监控仪表</div>
        <div class="ys-stat__value">{{ meters.monitored }}</div>
        <div class="ys-stat__hint">在线 {{ meters.online }} ／ 离线 {{ meters.offline }} ／ 停用 {{ meters.stopped }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">未关闭报警</div>
        <div class="ys-stat__value">{{ alarms.open }}</div>
        <div class="ys-stat__hint">待处理 {{ alarms.pending }} ／ 今日新增 {{ alarms.today }}</div>
      </el-card>
    </div>

    <h3 class="ys-section-title">近 14 天用量趋势</h3>
    <el-card shadow="never" class="ys-panel">
      <energy-chart :option="trendOption" :height="300" />
    </el-card>

    <h3 class="ys-section-title">本月各介质用量与费用</h3>
    <el-table :data="mediumRows" border stripe>
      <el-table-column prop="label" label="介质" width="100" />
      <el-table-column prop="consumption" label="用量" min-width="140" />
      <el-table-column prop="cost" label="费用" min-width="140" />
      <el-table-column prop="alarm" label="未关闭报警" width="130" />
    </el-table>

    <h3 class="ys-section-title">本月用量前 5 计量点</h3>
    <el-table :data="summary?.ranking ?? []" border stripe>
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="label" label="计量点" min-width="180" />
      <el-table-column prop="medium_label" label="介质" width="90" />
      <el-table-column label="用量" min-width="130">
        <template #default="{ row }">{{ formatDecimal(row.consumption) }}</template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="90" />
      <el-table-column label="费用" min-width="130">
        <template #default="{ row }">{{ formatAmount(row.cost) }}</template>
      </el-table-column>
      <el-table-column label="单价" width="110">
        <template #default="{ row }">
          <el-tag v-if="row.priced" type="success" size="small" effect="light">已维护</el-tag>
          <el-tag v-else type="warning" size="small" effect="light">未维护单价</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="summary" class="ys-muted">统计时间：{{ formatDateTime(summary.generated_at) }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import EnergyChart from '@/components/EnergyChart.vue'
import { ApiError } from '@/api/http'
import { energyHomeApi } from '@/api/energy'
import { useAuthStore } from '@/stores/auth'
import { formatAmount, formatDecimal } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'
import type { EnergyHomeSummary } from '@/types/models'

/** 图表提示里的数值口径与列表一致：保留 2 位小数（ECharts 默认会打印原始精度）。 */
function chartValue(value: unknown): string {
  return formatDecimal(value as number)
}

const auth = useAuthStore()
const router = useRouter()

const summary = ref<EnergyHomeSummary | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const canViewMonitor = computed(() => auth.hasPermission('ems.monitor.view'))
const canViewReport = computed(() => auth.hasPermission('ems.report.view'))

const meters = computed(
  () => summary.value?.meters ?? { total: 0, online: 0, offline: 0, stopped: 0, monitored: 0 },
)
const alarms = computed(() => summary.value?.alarms ?? { open: 0, pending: 0, today: 0, by_type: {} })
const monthRange = computed(() =>
  summary.value ? summary.value.month.start + ' ~ ' + summary.value.month.end : '-',
)

const mediumRows = computed(() =>
  Object.entries(summary.value?.month.by_medium ?? {}).map(([medium, item]) => ({
    medium,
    label: item.label,
    consumption: formatDecimal(item.consumption),
    cost: formatAmount(item.cost),
    alarm: alarms.value.by_type[medium] ?? 0,
  })),
)

/** 图表坐标必须是 number，仅用于绘图；业务口径仍以 Decimal 字符串为准。 */
const trendOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: chartValue },
  grid: { left: 60, right: 24, top: 24, bottom: 36 },
  xAxis: {
    type: 'category',
    data: (summary.value?.trend ?? []).map((item) => item.date.slice(5)),
  },
  yAxis: { type: 'value' },
  series: [
    {
      name: '用量',
      type: 'line',
      smooth: true,
      areaStyle: {},
      data: (summary.value?.trend ?? []).map((item) => Number(item.consumption)),
    },
  ],
}))

function goto(path: string): void {
  void router.push(path)
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    summary.value = await energyHomeApi.load()
  } catch (error) {
    summary.value = null
    errorMessage.value = error instanceof ApiError ? error.message : '加载能源首页失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
