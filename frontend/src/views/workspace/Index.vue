<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">工作台</h2>
        <p class="ys-page__description">
          卡片数值全部由业务数据实时计算，每张卡片在鼠标悬停时显示数据来源、统计口径与所需权限。
          无对应权限的卡片后端不会返回，因此本页不会出现「看得见但看不到数」的指标。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-alert class="ys-dashboard__banner" type="info" :closable="false" show-icon>
      <template #title>当前阶段说明</template>
      <div>
        本平台当前处于阶段 1（登录、权限、组织、主数据、基础审批、审计）。
        采购、销售、生产、仓储、质量、设备、能源等模块将在后续阶段直接在本平台内实现，
        本页不展示这些模块的占位卡片。
        <router-link to="/system/progress">查看实施进度</router-link>
      </div>
    </el-alert>

    <el-row :gutter="12" class="ys-dashboard__row">
      <el-col :span="6">
        <el-card shadow="never" class="ys-dashboard__approval">
          <div class="ys-dashboard__approval-label">我的待办审批</div>
          <div class="ys-dashboard__approval-value">
            {{ dashboard?.approval.todo === null || dashboard?.approval.todo === undefined ? '无权限' : dashboard.approval.todo }}
          </div>
          <el-button
            v-if="dashboard?.approval.todo !== null && dashboard?.approval.todo !== undefined"
            link
            type="primary"
            @click="goto('/workflow/todo')"
          >
            前往待办
          </el-button>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="ys-dashboard__approval">
          <div class="ys-dashboard__approval-label">我提交的审批中单据</div>
          <div class="ys-dashboard__approval-value">
            {{ dashboard?.approval.my_submitted_pending ?? '-' }}
          </div>
          <el-button
            v-if="dashboard?.approval.my_submitted_pending !== null && dashboard?.approval.my_submitted_pending !== undefined"
            link
            type="primary"
            @click="goto('/workflow/my-requests')"
          >
            前往我的申请
          </el-button>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="ys-dashboard__approval">
          <div class="ys-dashboard__approval-label">未读通知</div>
          <div class="ys-dashboard__approval-value">{{ auth.unreadNotifications }}</div>
          <el-button
            v-if="canViewNotifications"
            link
            type="primary"
            @click="goto('/system/notifications')"
          >
            查看通知
          </el-button>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="ys-dashboard__approval">
          <div class="ys-dashboard__approval-label">数据中心时间</div>
          <div class="ys-dashboard__approval-time">{{ formatDateTime(dashboard?.generated_at) }}</div>
          <div class="ys-muted">业务时区 {{ dashboard?.business_timezone || 'Asia/Shanghai' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <h3 class="ys-section-title">主数据规模（按数据范围统计）</h3>
    <el-empty v-if="cards.length === 0 && !loading" description="当前账号没有任何主数据查看权限" />
    <div class="ys-dashboard__cards">
      <el-tooltip
        v-for="card in cards"
        :key="card.key"
        placement="top"
        effect="light"
        :content="`来源：${card.definition.source} ｜ 时间字段：${card.definition.time_field} ｜ 口径：${card.definition.scope} ｜ 权限：${card.definition.permission}`"
      >
        <el-card shadow="hover" class="ys-dashboard__card">
          <div class="ys-dashboard__card-label">{{ card.label }}</div>
          <div class="ys-dashboard__card-value">
            {{ card.value === null ? '无权限' : formatAmount(card.value, 0) }}
          </div>
        </el-card>
      </el-tooltip>
    </div>

    <el-row :gutter="12" class="ys-dashboard__row">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="ys-dashboard__card-header">
              <span>内部协同发件箱状态（实时）</span>
              <el-button v-if="canViewOutbox" link type="primary" @click="goto('/integration/outbox')">
                打开发件箱
              </el-button>
            </div>
          </template>
          <div v-if="!canViewOutbox" class="ys-muted">
            当前账号没有 integration.outbox.view 权限，后端不会返回发件箱统计。
          </div>
          <template v-else>
            <el-alert v-if="outboxError" type="error" :closable="false" show-icon :title="outboxError" />
            <div v-show="!outboxError" ref="chartRef" class="ys-dashboard__chart"></div>
          </template>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div class="ys-dashboard__card-header">
              <span>最近业务动态</span>
              <el-button v-if="canViewAudit" link type="primary" @click="goto('/system/audit-logs')">
                查看审计日志
              </el-button>
            </div>
          </template>
          <el-empty v-if="recentActivity.length === 0" description="暂无动态" :image-size="60" />
          <el-timeline v-else>
            <el-timeline-item
              v-for="row in recentActivity"
              :key="row.id"
              :timestamp="formatDateTime(row.created_at)"
            >
              {{ row.actor_name || '系统' }} {{ row.object_type }} {{ row.object_repr }}
            </el-timeline-item>
          </el-timeline>
          <div v-if="!canViewAudit" class="ys-muted">
            当前账号没有 core.audit.view 权限，这里只显示本人最近的操作记录。
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template><script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'

import { ApiError } from '@/api/http'
import { analyticsApi, integrationApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import type { DashboardPayload, OutboxHealth } from '@/types/models'
import { formatAmount } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const router = useRouter()

const dashboard = ref<DashboardPayload | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const outbox = ref<OutboxHealth | null>(null)
const outboxError = ref('')
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const cards = computed(() => dashboard.value?.cards ?? [])
const recentActivity = computed(() => dashboard.value?.recent_activity ?? [])

const canViewOutbox = computed(() => auth.hasPermission('integration.outbox.view'))
const canViewAudit = computed(() => auth.hasPermission('core.audit.view'))
const canViewNotifications = computed(() => auth.hasPermission('core.notification.view'))

function goto(path: string): void {
  void router.push(path)
}

const OUTBOX_LABELS: Record<keyof OutboxHealth, string> = {
  pending: '待处理',
  processing: '处理中',
  done: '已完成',
  failed: '失败待重试',
  dead: '超限待人工',
}

function renderChart(): void {
  if (!chartRef.value || !outbox.value) {
    return
  }
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  const keys = Object.keys(OUTBOX_LABELS) as (keyof OutboxHealth)[]
  chart.setOption({
    grid: { top: 24, left: 48, right: 16, bottom: 32 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: keys.map((key) => OUTBOX_LABELS[key]) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'bar',
        barMaxWidth: 40,
        data: keys.map((key) => outbox.value?.[key] ?? 0),
        itemStyle: { color: '#1668dc' },
      },
    ],
  })
  chart.resize()
}

function resizeChart(): void {
  chart?.resize()
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    dashboard.value = await analyticsApi.dashboard()
  } catch (error) {
    dashboard.value = null
    errorMessage.value = error instanceof ApiError ? error.message : '加载工作台数据失败'
  } finally {
    loading.value = false
  }

  if (!canViewOutbox.value) {
    return
  }
  outboxError.value = ''
  try {
    outbox.value = await integrationApi.outboxHealth()
    renderChart()
  } catch (error) {
    outbox.value = null
    outboxError.value = error instanceof ApiError ? error.message : '加载发件箱状态失败'
  }
}

watch(outbox, () => renderChart())

onMounted(async () => {
  window.addEventListener('resize', resizeChart)
  await load()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.ys-dashboard__banner {
  margin-bottom: 12px;
}

.ys-dashboard__row {
  margin-bottom: 12px;
}

.ys-dashboard__approval-label {
  font-size: 12px;
  color: var(--ys-gray-500);
}

.ys-dashboard__approval-value {
  margin: 6px 0 4px;
  font-size: 28px;
  font-weight: 600;
  color: var(--ys-navy-900);
}

.ys-dashboard__approval-time {
  margin: 6px 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ys-navy-900);
}

.ys-section-title {
  margin: 16px 0 12px;
  font-size: 14px;
  color: var(--ys-navy-900);
}

.ys-dashboard__cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ys-dashboard__card {
  width: 168px;
}

.ys-dashboard__card-label {
  font-size: 12px;
  color: var(--ys-gray-500);
}

.ys-dashboard__card-value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ys-navy-900);
}

.ys-dashboard__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ys-dashboard__chart {
  height: 220px;
}
</style>