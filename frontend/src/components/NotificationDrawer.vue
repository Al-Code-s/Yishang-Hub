<template>
  <el-drawer v-model="visible" title="我的通知" size="420px">
    <div class="ys-toolbar">
      <el-button size="small" @click="load" :loading="loading">刷新</el-button>
      <el-button size="small" type="primary" plain :disabled="rows.length === 0" @click="markAll">
        全部标记已读
      </el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-empty v-if="rows.length === 0 && !loading" description="暂无通知" />

    <ul class="ys-notification-list">
      <li
        v-for="row in rows"
        :key="row.id"
        class="ys-notification"
        :class="{ 'ys-notification--unread': !row.is_read }"
      >
        <div class="ys-notification__head">
          <span class="ys-notification__title">{{ row.title }}</span>
          <el-tag v-if="!row.is_read" type="danger" size="small" effect="light">未读</el-tag>
        </div>
        <p class="ys-notification__body">{{ row.body || '（无正文）' }}</p>
        <div class="ys-notification__foot">
          <span class="ys-muted">{{ formatDateTime(row.created_at) }}</span>
          <el-button v-if="!row.is_read" link type="primary" size="small" @click="markRead(row.id)">
            标记已读
          </el-button>
        </div>
      </li>
    </ul>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import { useAuthStore } from '@/stores/auth'
import type { Notification } from '@/types/models'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ modelValue: boolean; canView: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const auth = useAuthStore()
const visible = ref(props.modelValue)
const rows = ref<Notification[]>([])
const loading = ref(false)
const errorMessage = ref('')

watch(
  () => props.modelValue,
  async (value) => {
    visible.value = value
    if (value) {
      await load()
    }
  },
)

watch(visible, (value) => emit('update:modelValue', value))

async function load(): Promise<void> {
  if (!props.canView) {
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await identityApi.notifications({ page_size: 20, ordering: '-id' })
    rows.value = result.results
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '加载通知失败'
  } finally {
    loading.value = false
  }
}

async function markRead(id: number): Promise<void> {
  try {
    await identityApi.markNotificationRead(id)
    await load()
    await auth.refreshUnreadCount()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function markAll(): Promise<void> {
  try {
    await identityApi.markAllNotificationsRead()
    await load()
    await auth.refreshUnreadCount()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>

<style scoped>
.ys-notification-list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.ys-notification {
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid var(--ys-gray-200);
  border-radius: 6px;
}

.ys-notification--unread {
  border-left: 3px solid var(--ys-blue-600);
  background: var(--ys-blue-100);
}

.ys-notification__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ys-notification__title {
  font-weight: 600;
  color: var(--ys-navy-900);
}

.ys-notification__body {
  margin: 6px 0;
  font-size: 12px;
  color: var(--ys-gray-700);
}

.ys-notification__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>