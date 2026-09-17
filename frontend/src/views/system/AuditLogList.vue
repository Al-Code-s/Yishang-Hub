<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">审计日志</h2>
        <p class="ys-page__description">
          审计记录只写不改：平台不提供任何修改或删除审计的接口。
          关键业务操作的审计与业务数据在同一事务内保存，业务回滚则审计一并回滚。
          密码、令牌等敏感原文不会写入审计内容。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button type="primary" plain :disabled="rows.length === 0" @click="exportCsv">
          导出当前页
        </el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索对象、操作人或 request_id"
        clearable
        style="width: 260px"
        @keyup.enter="reload"
      />
      <el-input
        v-model="filters.action"
        placeholder="操作类型，如 create / update"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
      />
      <el-input
        v-model="filters.object_type"
        placeholder="对象类型"
        clearable
        style="width: 180px"
        @keyup.enter="reload"
      />
      <el-input
        v-model="filters.request_id"
        placeholder="request_id"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
      />
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small" @row-click="openDetail">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="actor_name" label="操作人" width="120" />
      <el-table-column prop="action_display" label="操作" width="110" />
      <el-table-column prop="object_type" label="对象类型" width="140" />
      <el-table-column prop="object_repr" label="对象" min-width="180" />
      <el-table-column prop="reason" label="原因 / 依据" min-width="160" />
      <el-table-column label="request_id" width="200">
        <template #default="{ row }">
          <span class="ys-mono">{{ row.request_id.slice(0, 12) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="ip_address" label="来源 IP" width="140" />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click.stop="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无审计记录" />
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

    <el-drawer v-model="detailVisible" title="审计详情" size="560px">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="操作时间">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="操作人">
            {{ detail.actor_name || '-' }}（{{ detail.actor_username || '-' }}）
          </el-descriptions-item>
          <el-descriptions-item label="操作类型">
            {{ detail.action_display || detail.action }}
          </el-descriptions-item>
          <el-descriptions-item label="对象">
            {{ detail.object_type }} / {{ detail.object_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="对象描述">{{ detail.object_repr || '-' }}</el-descriptions-item>
          <el-descriptions-item label="原因">{{ detail.reason || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审批依据">{{ detail.approval_basis || '-' }}</el-descriptions-item>
          <el-descriptions-item label="request_id">
            <span class="ys-mono">{{ detail.request_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="来源 IP">{{ detail.ip_address || '-' }}</el-descriptions-item>
          <el-descriptions-item label="User-Agent">{{ detail.user_agent || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="ys-section-title">字段变更摘要</h4>
        <pre class="ys-audit__changes">{{ prettyChanges }}</pre>
      </template>
      <el-empty v-else description="未加载到审计详情" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { ApiError } from '@/api/http'
import { coreApi } from '@/api/modules'
import type { AuditLog } from '@/types/models'
import { exportCsv as exportCsvFile } from '@/utils/download'
import { formatDateTime } from '@/utils/format'

const rows = ref<AuditLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive({
  search: '',
  action: '',
  object_type: '',
  request_id: '',
})

const detailVisible = ref(false)
const detail = ref<AuditLog | null>(null)

const prettyChanges = computed(() => {
  if (!detail.value?.changes) {
    return '（本次操作没有字段级变更摘要）'
  }
  return JSON.stringify(detail.value.changes, null, 2)
})

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await coreApi.auditLogs({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      action: filters.action || undefined,
      object_type: filters.object_type || undefined,
      request_id: filters.request_id || undefined,
      ordering: '-id',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载审计日志失败'
  } finally {
    loading.value = false
  }
}

function reload(): void {
  page.value = 1
  void load()
}

function resetFilters(): void {
  filters.search = ''
  filters.action = ''
  filters.object_type = ''
  filters.request_id = ''
  reload()
}

function openDetail(row: AuditLog): void {
  detail.value = row
  detailVisible.value = true
}

function exportCsv(): void {
  exportCsvFile(
    `audit-logs-page-${page.value}.csv`,
    ['时间', '操作人', '操作', '对象类型', '对象', '原因', 'request_id', '来源 IP'],
    rows.value.map((row) => [
      formatDateTime(row.created_at),
      row.actor_name,
      row.action_display,
      row.object_type,
      row.object_repr,
      row.reason,
      row.request_id,
      row.ip_address,
    ]),
  )
}

onMounted(load)
</script>

<style scoped>
.ys-section-title {
  margin: 16px 0 12px;
  font-size: 14px;
  color: var(--ys-navy-900);
}

.ys-audit__changes {
  max-height: 320px;
  padding: 12px;
  overflow: auto;
  font-size: 12px;
  background: var(--ys-gray-50);
  border: 1px solid var(--ys-gray-200);
  border-radius: 4px;
}
</style>