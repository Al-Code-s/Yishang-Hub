<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">设备监控</h2>
        <p class="ys-page__description">
          按数采设备展示在线状态、各测点最新读数与近 24 小时的采集质量。在线状态由最近一次上报时间判定，
          超过「离线判定」时长没有新数据即计为离线；读数越过上下限的测点会标出「超限」，报警统一记在能源管理的报警台账里。
          模拟设备与模拟读数全程带「模拟」标签，不与真实采集数据混在一起。
          下方「采集统计」按测点与时间桶（业务时区）汇总读数，数据由明细实时聚合，
          可随时回到「采集读数」逐条核对。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button v-if="canViewAlarm" @click="goto('/ems/alarms')">报警台账</el-button>
        <el-button v-if="canViewReading" @click="goto('/iot/readings')">采集读数</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-select v-model="companyId" placeholder="所属公司" clearable style="width: 200px" @change="load">
        <el-option
          v-for="item in companies"
          :key="String(item.value)"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <span class="ys-muted">统计时间：{{ payload ? formatDateTime(payload.generated_at) : '-' }}</span>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <div class="ys-stat-cards">
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">数采设备</div>
        <div class="ys-stat__value">{{ summary.gateway_total }}</div>
        <div class="ys-stat__hint">在线 {{ summary.online }} ／ 离线 {{ summary.offline }} ／ 未知 {{ summary.unknown }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">近 24 小时读数</div>
        <div class="ys-stat__value">{{ summary.readings_24h }}</div>
        <div class="ys-stat__hint">按接收时间统计</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">近 24 小时处理失败报文</div>
        <div class="ys-stat__value">{{ summary.failed_messages_24h }}</div>
        <div class="ys-stat__hint">重复报文 {{ summary.duplicated_messages_24h }}</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">未关闭报警</div>
        <div class="ys-stat__value">{{ summary.open_alarms }}</div>
        <div class="ys-stat__hint">待处理与处理中合计</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">模拟设备</div>
        <div class="ys-stat__value">{{ summary.simulated }}</div>
        <div class="ys-stat__hint">模拟数据不计入真实产量与能耗</div>
      </el-card>
    </div>

    <h3 class="ys-section-title">设备与测点</h3>
    <el-table v-loading="loading" :data="gateways" border stripe>
      <el-table-column type="expand">
        <template #default="{ row }">
          <el-table :data="row.points" size="small" border>
            <el-table-column prop="code" label="测点编码" width="150" />
            <el-table-column prop="name" label="测点名称" min-width="150" />
            <el-table-column prop="quantity" label="物理量" width="100" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column
              prop="lower_limit"
              label="报警下限"
              width="110"
              :formatter="numberFormatter"
            />
            <el-table-column
              prop="upper_limit"
              label="报警上限"
              width="110"
              :formatter="numberFormatter"
            />
            <el-table-column label="最新读数" width="130">
              <template #default="scope">
                {{ scope.row.latest_value === null ? '-' : formatDecimal(scope.row.latest_value) }}
              </template>
            </el-table-column>
            <el-table-column label="读数时间" width="170">
              <template #default="scope">{{ formatDateTime(scope.row.latest_device_time) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="scope">
                <el-tag v-if="scope.row.is_over_limit" type="danger" size="small" effect="light">超限</el-tag>
                <el-tag v-else type="success" size="small" effect="light">正常</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数据标识" width="90">
              <template #default="scope">
                <el-tag v-if="scope.row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
                <span v-else class="ys-muted">真实</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="row.points.length === 0" class="ys-muted">该设备还没有启用中的测点。</div>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="设备编码" width="150" />
      <el-table-column prop="name" label="设备名称" min-width="150" />
      <el-table-column label="在线状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
            {{ meta.label('iot_gateway_statuses', String(row.status)) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="connection_name" label="所属连接" width="140" />
      <el-table-column prop="location" label="安装位置" width="140" />
      <el-table-column label="最近上报时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.last_seen_at) }}</template>
      </el-table-column>
      <el-table-column prop="offline_minutes" label="离线判定（分钟）" width="140" />
      <el-table-column label="超限测点" width="100">
        <template #default="{ row }">
          <el-tag v-if="overLimitCount(row) > 0" type="danger" size="small" effect="light">
            {{ overLimitCount(row) }}
          </el-tag>
          <span v-else class="ys-muted">0</span>
        </template>
      </el-table-column>
      <el-table-column label="数据标识" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
          <span v-else class="ys-muted">真实</span>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无数采设备。请先在「数采设备」里登记设备并下发令牌。" />
      </template>
    </el-table>

    <h3 class="ys-section-title">采集统计</h3>
    <div class="ys-filter-bar">
      <el-radio-group v-model="granularity" @change="loadStatistics">
        <el-radio :value="'hour'">按小时</el-radio>
        <el-radio :value="'day'">按天</el-radio>
      </el-radio-group>
      <span class="ys-muted">
        统计区间：{{ statistics ? formatDateTime(statistics.since) : '-' }} ~
        {{ statistics ? formatDateTime(statistics.until) : '-' }}
      </span>
      <el-button :loading="statLoading" @click="loadStatistics">刷新统计</el-button>
    </div>
    <el-alert v-if="statError" type="error" :closable="false" show-icon :title="statError" />

    <div class="ys-stat-cards">
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">样本数</div>
        <div class="ys-stat__value">{{ statTotals.sample_count }}</div>
        <div class="ys-stat__hint">其中模拟 {{ statTotals.simulated_count }} 条</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">覆盖测点</div>
        <div class="ys-stat__value">{{ statTotals.point_count }}</div>
        <div class="ys-stat__hint">来自 {{ statTotals.gateway_count }} 台设备</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">超限时间桶</div>
        <div class="ys-stat__value">{{ overLimitBuckets }}</div>
        <div class="ys-stat__hint">桶内出现过越限读数</div>
      </el-card>
      <el-card shadow="never" class="ys-stat-card">
        <div class="ys-stat__label">读数合计</div>
        <div class="ys-stat__value">
          {{ statTotals.value_sum === null ? '-' : formatDecimal(statTotals.value_sum) }}
        </div>
        <div class="ys-stat__hint">累计型测点才有物理含义，仅供参考</div>
      </el-card>
    </div>

    <el-alert
      v-if="statistics?.truncated"
      type="warning"
      :closable="false"
      show-icon
      title="明细行已达上限，只显示最近的分桶；缩小统计区间可以看到更早的数据。"
    />
    <el-table v-loading="statLoading" :data="statistics?.rows ?? []" border stripe>
      <el-table-column label="时间桶" width="180">
        <template #default="{ row }">{{ formatDateTime(row.bucket) }}</template>
      </el-table-column>
      <el-table-column prop="gateway_code" label="设备编码" width="140" />
      <el-table-column prop="point_code" label="测点编码" width="140" />
      <el-table-column prop="point_name" label="测点名称" min-width="140" />
      <el-table-column prop="sample_count" label="样本数" width="90" />
      <el-table-column label="最小" width="110">
        <template #default="{ row }">
          {{ row.value_min === null ? '-' : formatDecimal(row.value_min) }}
        </template>
      </el-table-column>
      <el-table-column label="最大" width="110">
        <template #default="{ row }">
          {{ row.value_max === null ? '-' : formatDecimal(row.value_max) }}
        </template>
      </el-table-column>
      <el-table-column label="平均" width="110">
        <template #default="{ row }">{{ formatDecimal(row.value_avg) }}</template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="80" />
      <el-table-column label="越限" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_over_limit" type="danger" size="small" effect="light">超限</el-tag>
          <span v-else class="ys-muted">正常</span>
        </template>
      </el-table-column>
      <el-table-column label="数据标识" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
          <span v-else-if="row.simulated_count > 0" class="ys-muted">含模拟</span>
          <span v-else class="ys-muted">真实</span>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="统计区间内暂无采集读数。设备上报后这里才会有统计。" />
      </template>
    </el-table>

    <h3 class="ys-section-title">最近读数</h3>
    <el-table :data="payload?.recent_readings ?? []" border stripe>
      <el-table-column prop="device_time" label="设备时间" width="170" />
      <el-table-column prop="gateway_code" label="设备编码" width="140" />
      <el-table-column prop="point_code" label="测点编码" width="140" />
      <el-table-column prop="point_name" label="测点名称" min-width="150" />
      <el-table-column label="读数" width="130">
        <template #default="{ row }">{{ formatDecimal(row.value) }}</template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="80" />
      <el-table-column label="数据标识" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
          <span v-else class="ys-muted">真实</span>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无采集读数。" />
      </template>
    </el-table>

    <h3 class="ys-section-title">报文处理情况（近 24 小时）</h3>
    <el-table :data="payload?.message_stats ?? []" border stripe>
      <el-table-column label="处理状态" width="160">
        <template #default="{ row }">
          {{ meta.label('iot_message_statuses', String(row.status)) }}
        </template>
      </el-table-column>
      <el-table-column prop="total" label="报文条数" width="140" />
      <template #empty>
        <el-empty description="暂无采集报文。" />
      </template>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ApiError } from '@/api/http'
import { iotMonitorApi, iotStatisticsApi } from '@/api/iot'
import { companyOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal, numberFormatter } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'
import type {
  EnumOption,
  IoTMonitorGateway,
  IoTMonitorPayload,
  IoTStatisticsPayload,
} from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const router = useRouter()

const payload = ref<IoTMonitorPayload | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const companyId = ref<number | null>(null)
const companies = ref<EnumOption[]>([])

const granularity = ref<'hour' | 'day'>('day')
const statistics = ref<IoTStatisticsPayload | null>(null)
const statLoading = ref(false)
const statError = ref('')

const statTotals = computed(
  () =>
    statistics.value?.totals ?? {
      sample_count: 0,
      simulated_count: 0,
      point_count: 0,
      gateway_count: 0,
      value_sum: null,
    },
)
const overLimitBuckets = computed(
  () => (statistics.value?.rows ?? []).filter((row) => row.is_over_limit).length,
)

async function loadStatistics(): Promise<void> {
  statLoading.value = true
  statError.value = ''
  try {
    statistics.value = await iotStatisticsApi.load(
      companyId.value === null
        ? { granularity: granularity.value }
        : { granularity: granularity.value, company_id: companyId.value },
    )
  } catch (error) {
    statistics.value = null
    statError.value = error instanceof ApiError ? error.message : '加载采集统计失败'
  } finally {
    statLoading.value = false
  }
}

const canViewAlarm = computed(() => auth.hasPermission('ems.alarm.view'))
const canViewReading = computed(() => auth.hasPermission('iot.reading.view'))

const summary = computed(
  () =>
    payload.value?.summary ?? {
      gateway_total: 0,
      online: 0,
      offline: 0,
      unknown: 0,
      simulated: 0,
      readings_24h: 0,
      failed_messages_24h: 0,
      duplicated_messages_24h: 0,
      open_alarms: 0,
    },
)

const gateways = computed(() => payload.value?.gateways ?? [])

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'online') return 'success'
  if (status === 'offline') return 'danger'
  if (status === 'disabled') return 'info'
  return 'warning'
}

function overLimitCount(row: IoTMonitorGateway): number {
  return row.points.filter((point) => point.is_over_limit).length
}

function goto(path: string): void {
  void router.push(path)
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    payload.value = await iotMonitorApi.load(
      companyId.value === null ? {} : { company_id: companyId.value },
    )
  } catch (error) {
    payload.value = null
    errorMessage.value = error instanceof ApiError ? error.message : '加载设备监控失败'
  } finally {
    loading.value = false
  }
  await loadStatistics()
}

onMounted(async () => {
  companies.value = await companyOptions().catch(() => [])
  await load()
})
</script>
