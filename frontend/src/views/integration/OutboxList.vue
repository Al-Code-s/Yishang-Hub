<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">内部协同中心</h2>
        <p class="ys-page__description">
          跨模块事件采用发件箱（Outbox）模式：事件与业务数据在同一事务写入，后台任务以
          「至少一次」语义投递，因此消费者必须自行幂等。失败事件可人工重放，重放同样不会重复产生业务结果。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canRetry" type="primary" plain :loading="dispatching" @click="dispatchNow">
          立即投递到期事件
        </el-button>
        <el-button :loading="loading" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="ys-outbox__cards">
      <el-col v-for="item in healthItems" :key="item.key" :span="4">
        <el-card shadow="never">
          <div class="ys-outbox__label">{{ item.label }}</div>
          <div class="ys-outbox__value">{{ item.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-alert
      v-if="healthError"
      type="warning"
      :closable="false"
      show-icon
      :title="`发件箱健康统计加载失败：${healthError}`"
    />

    <el-tabs v-model="activeTab" class="ys-outbox__tabs">
      <el-tab-pane label="事件列表" name="events">
        <div class="ys-filter-bar">
          <el-input
            v-model="filters.search"
            placeholder="搜索事件类型、聚合 ID 或错误信息"
            clearable
            style="width: 260px"
            @keyup.enter="reload"
          />
          <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px">
            <el-option
              v-for="item in statusOptions"
              :key="item"
              :label="statusLabel(item)"
              :value="item"
            />
          </el-select>
          <el-input
            v-model="filters.event_type"
            placeholder="事件类型"
            clearable
            style="width: 200px"
            @keyup.enter="reload"
          />
          <el-button type="primary" @click="reload">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>

        <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

        <el-table v-loading="loading" :data="rows" border stripe size="small">
          <el-table-column prop="event_type" label="事件类型" min-width="200" />
          <el-table-column prop="aggregate_type" label="聚合类型" width="140" />
          <el-table-column prop="aggregate_id" label="聚合 ID" width="120" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="light">
                {{ row.status_display || statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="尝试次数" width="110" align="center">
            <template #default="{ row }">{{ row.attempts }} / {{ row.max_attempts }}</template>
          </el-table-column>
          <el-table-column label="下次重试" width="170">
            <template #default="{ row }">{{ formatDateTime(row.next_retry_at) }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="last_error" label="最后一次错误" min-width="200" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
              <el-button
                v-if="canRetry && row.status !== 'done'"
                link
                type="warning"
                size="small"
                @click="retry(row)"
              >
                重放
              </el-button>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无发件箱事件" />
          </template>
        </el-table>

        <div class="ys-pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            background
            @current-change="load"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="单据关系" name="links">
        <div class="ys-filter-bar">
          <el-input
            v-model="linkFilters.source_type"
            placeholder="来源单据类型，如 wms.document"
            clearable
            style="width: 240px"
            @keyup.enter="reloadLinks"
          />
          <el-input
            v-model="linkFilters.target_type"
            placeholder="目标单据类型"
            clearable
            style="width: 220px"
            @keyup.enter="reloadLinks"
          />
          <el-input
            v-model="linkFilters.source_id"
            placeholder="来源单据 ID"
            clearable
            style="width: 160px"
            @keyup.enter="reloadLinks"
          />
          <el-button type="primary" @click="reloadLinks">查询</el-button>
          <el-button @click="resetLinkFilters">重置</el-button>
        </div>

        <el-alert
          v-if="linkError"
          type="error"
          :closable="false"
          show-icon
          :title="linkError"
        />

        <el-table v-loading="linkLoading" :data="links" border stripe size="small">
          <el-table-column prop="source_no" label="来源单号" width="150" />
          <el-table-column prop="source_type" label="来源类型" min-width="150" />
          <el-table-column prop="target_no" label="目标单号" width="150" />
          <el-table-column prop="target_type" label="目标类型" min-width="150" />
          <el-table-column prop="relation" label="关系" width="130" />
          <el-table-column label="数量" width="120" align="right">
            <template #default="{ row }">{{ formatAmount(row.quantity, 6) }}</template>
          </el-table-column>
          <el-table-column label="建立时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无单据关系记录。阶段 1 尚未产生跨模块单据，列表为空属于预期结果。" />
          </template>
        </el-table>

        <div class="ys-pagination">
          <el-pagination
            v-model:current-page="linkPage"
            :page-size="linkPageSize"
            :total="linkTotal"
            layout="total, prev, pager, next"
            background
            @current-change="loadLinks"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="detailVisible" title="发件箱事件详情" size="560px">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="事件 ID">
            <span class="ys-mono">{{ detail.event_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="事件类型">{{ detail.event_type }}</el-descriptions-item>
          <el-descriptions-item label="聚合对象">
            {{ detail.aggregate_type }} / {{ detail.aggregate_id }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            {{ detail.status_display || statusLabel(detail.status) }}
          </el-descriptions-item>
          <el-descriptions-item label="尝试次数">
            {{ detail.attempts }} / {{ detail.max_attempts }}
          </el-descriptions-item>
          <el-descriptions-item label="去重键">{{ detail.dedup_key || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(detail.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="处理时间">
            {{ formatDateTime(detail.processed_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="最后错误">
            {{ detail.last_error || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="ys-section-title">载荷（payload）</h4>
        <pre class="ys-outbox__payload">{{ prettyPayload }}</pre>
      </template>
      <el-empty v-else description="未加载到事件详情" />
    </el-drawer>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiError } from '@/api/http'
import { integrationApi } from '@/api/modules'
import { useAuthStore } from '@/stores/auth'
import type { DocumentLink, OutboxEvent, OutboxHealth } from '@/types/models'
import { formatAmount } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

const activeTab = ref('events')

const rows = ref<OutboxEvent[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive<{ search: string; status: string; event_type: string }>({
  search: '',
  status: '',
  event_type: '',
})

const links = ref<DocumentLink[]>([])
const linkTotal = ref(0)
const linkPage = ref(1)
const linkPageSize = ref(20)
const linkLoading = ref(false)
const linkError = ref('')
const linkFilters = reactive({ source_type: '', target_type: '', source_id: '' })
const linksLoaded = ref(false)

const health = ref<OutboxHealth | null>(null)
const healthError = ref('')
const dispatching = ref(false)

const detailVisible = ref(false)
const detail = ref<OutboxEvent | null>(null)

const STATUS_OPTIONS = ['pending', 'processing', 'done', 'failed', 'dead']
const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  done: '已完成',
  failed: '失败待重试',
  dead: '超限待人工',
}

const canView = computed(() => auth.hasPermission('integration.outbox.view'))
const canRetry = computed(() => auth.hasPermission('integration.outbox.retry'))

const statusOptions = computed(() => STATUS_OPTIONS)

const healthItems = computed(() => {
  const data = health.value
  const keys: (keyof OutboxHealth)[] = ['pending', 'processing', 'done', 'failed', 'dead']
  const labels: Record<keyof OutboxHealth, string> = {
    pending: '待处理',
    processing: '处理中',
    done: '已完成',
    failed: '失败待重试',
    dead: '超限待人工',
  }
  return keys.map((key) => ({ key, label: labels[key], value: data ? data[key] : '-' }))
})

const prettyPayload = computed(() => {
  if (!detail.value?.payload) {
    return '（无载荷）'
  }
  return JSON.stringify(detail.value.payload, null, 2)
})

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'done') {
    return 'success'
  }
  if (status === 'failed') {
    return 'warning'
  }
  if (status === 'dead') {
    return 'danger'
  }
  if (status === 'pending' || status === 'processing') {
    return 'primary'
  }
  return 'info'
}

async function loadHealth(): Promise<void> {
  healthError.value = ''
  try {
    health.value = await integrationApi.outboxHealth()
  } catch (error) {
    health.value = null
    healthError.value = error instanceof ApiError ? error.message : '未知错误'
  }
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await integrationApi.outbox({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      status: filters.status || undefined,
      event_type: filters.event_type || undefined,
      ordering: '-id',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载发件箱事件失败'
  } finally {
    loading.value = false
  }
}

async function loadLinks(): Promise<void> {
  linkLoading.value = true
  linkError.value = ''
  try {
    const result = await integrationApi.documentLinks({
      page: linkPage.value,
      page_size: linkPageSize.value,
      source_type: linkFilters.source_type || undefined,
      target_type: linkFilters.target_type || undefined,
      source_id: linkFilters.source_id || undefined,
      ordering: '-id',
    })
    links.value = result.results
    linkTotal.value = result.count
    linksLoaded.value = true
  } catch (error) {
    links.value = []
    linkTotal.value = 0
    linkError.value = error instanceof ApiError ? error.message : '加载单据关系失败'
  } finally {
    linkLoading.value = false
  }
}

function reload(): void {
  page.value = 1
  void load()
}

function resetFilters(): void {
  filters.search = ''
  filters.status = ''
  filters.event_type = ''
  reload()
}

function reloadLinks(): void {
  linkPage.value = 1
  void loadLinks()
}

function resetLinkFilters(): void {
  linkFilters.source_type = ''
  linkFilters.target_type = ''
  linkFilters.source_id = ''
  reloadLinks()
}

async function refreshAll(): Promise<void> {
  await Promise.all([loadHealth(), load()])
}

function openDetail(row: OutboxEvent): void {
  detail.value = row
  detailVisible.value = true
}

async function retry(row: OutboxEvent): Promise<void> {
  try {
    await integrationApi.retry(row.id)
    ElMessage.success('已重新入队；重放不会重复产生业务结果')
    await refreshAll()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '重放失败')
  }
}

async function dispatchNow(): Promise<void> {
  dispatching.value = true
  try {
    const result = await integrationApi.dispatchNow()
    ElMessage.success(
      `本次投递：认领 ${result.claimed} 条，成功 ${result.done} 条，失败 ${result.failed} 条`,
    )
    await refreshAll()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '投递失败')
  } finally {
    dispatching.value = false
  }
}

watch(activeTab, (value) => {
  if (value === 'links' && !linksLoaded.value) {
    void loadLinks()
  }
})

onMounted(async () => {
  if (!canView.value) {
    errorMessage.value = '当前账号没有 integration.outbox.view 权限，无法查看发件箱。'
    return
  }
  await refreshAll()
})
</script>

<style scoped>
.ys-outbox__cards {
  margin-bottom: 12px;
}

.ys-outbox__label {
  font-size: 12px;
  color: var(--ys-gray-500);
}

.ys-outbox__value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 600;
  color: var(--ys-navy-900);
}

.ys-outbox__tabs {
  padding: 0 12px 12px;
  background: #fff;
  border: 1px solid var(--ys-gray-200);
  border-radius: 6px;
}

.ys-section-title {
  margin: 16px 0 12px;
  font-size: 14px;
  color: var(--ys-navy-900);
}

.ys-outbox__payload {
  max-height: 320px;
  padding: 12px;
  overflow: auto;
  font-size: 12px;
  background: var(--ys-gray-50);
  border: 1px solid var(--ys-gray-200);
  border-radius: 4px;
}
</style>