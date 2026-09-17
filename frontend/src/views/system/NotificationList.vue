<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">我的通知</h2>
        <p class="ys-page__description">
          通知由业务事件异步产生，只显示当前账号自己的记录；带业务类型与业务 ID 的通知可以直接跳到对应单据。
          通知是提醒手段，不是业务凭证，最终以业务单据状态为准。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :disabled="rows.length === 0" @click="markAllRead">全部标记已读</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-select v-model="filters.is_read" placeholder="阅读状态" clearable style="width: 140px">
        <el-option label="未读" :value="false" />
        <el-option label="已读" :value="true" />
      </el-select>
      <el-input
        v-model="filters.biz_type"
        placeholder="业务类型"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
      />
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
      <span class="ys-muted">未读 {{ auth.unreadNotifications }}</span>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column label="" width="70">
        <template #default="{ row }">
          <el-tag v-if="!row.is_read" type="danger" size="small" effect="light">未读</el-tag>
          <span v-else class="ys-muted">已读</span>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column prop="body" label="内容" min-width="280" />
      <el-table-column prop="biz_type" label="业务类型" width="160" />
      <el-table-column prop="biz_id" label="业务 ID" width="120" />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.is_read" link type="primary" size="small" @click="markRead(row)">
            标记已读
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无通知" />
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import { useAuthStore } from '@/stores/auth'
import type { Notification } from '@/types/models'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

const rows = ref<Notification[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive<{ is_read: boolean | ''; biz_type: string }>({ is_read: '', biz_type: '' })

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await identityApi.notifications({
      page: page.value,
      page_size: pageSize.value,
      is_read: filters.is_read === '' ? undefined : filters.is_read,
      biz_type: filters.biz_type || undefined,
      ordering: '-id',
    })
    rows.value = result.results
    total.value = result.count
    await auth.refreshUnreadCount()
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载通知失败'
  } finally {
    loading.value = false
  }
}

function reload(): void {
  page.value = 1
  void load()
}

function resetFilters(): void {
  filters.is_read = ''
  filters.biz_type = ''
  reload()
}

async function markRead(row: Notification): Promise<void> {
  try {
    await identityApi.markNotificationRead(row.id)
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function markAllRead(): Promise<void> {
  try {
    await identityApi.markAllNotificationsRead()
    ElMessage.success('已全部标记为已读')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

onMounted(load)
</script>