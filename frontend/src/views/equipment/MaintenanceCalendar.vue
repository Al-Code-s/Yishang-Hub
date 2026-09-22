<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">保养日历</h2>
        <p class="ys-page__description">
          按月查看保养任务的排期：绿色为已完成，蓝色为进行中，橙色为待执行，灰色为已取消。
          日历数据来自保养任务，因此这里看到的排期与「保养任务」页面完全一致。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" type="error" show-icon :closable="false" :title="errorMessage" />

    <el-card v-loading="loading" shadow="never">
      <el-calendar v-model="currentDate">
        <template #date-cell="{ data }">
          <div class="ys-calendar-cell">
            <div class="ys-calendar-cell__day">{{ dayText(data.day) }}</div>
            <div
              v-for="task in tasksOf(data.day)"
              :key="task.id"
              class="ys-calendar-cell__task"
              :class="`ys-calendar-cell__task--${task.status}`"
              :title="`${task.task_no} ${task.equipment_name}`"
            >
              {{ task.equipment_name }}
            </div>
          </div>
        </template>
      </el-calendar>
    </el-card>

    <p class="ys-muted">
      日历按月份加载该月全部保养任务；跨月的长期计划请用「保养计划」页面的「生成任务」补足。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { maintenanceTaskApi } from '@/api/endpoints'
import type { MaintenanceTask } from '@/types/models'

const currentDate = ref(new Date())
const loading = ref(false)
const errorMessage = ref('')
const tasks = ref<MaintenanceTask[]>([])

function dayText(day: string): string {
  return String(Number(day.split('-')[2]))
}

const monthRange = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  return { start: toIsoDate(first), end: toIsoDate(last) }
})

function toIsoDate(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${value.getFullYear()}-${month}-${day}`
}

function tasksOf(day: string): MaintenanceTask[] {
  return tasks.value.filter((task) => task.plan_date === day)
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const page = await maintenanceTaskApi.list({
      page_size: 200,
      ordering: 'plan_date',
      plan_date__gte: monthRange.value.start,
      plan_date__lte: monthRange.value.end,
    })
    tasks.value = page.results
  } catch (error) {
    tasks.value = []
    errorMessage.value = error instanceof ApiError ? `${error.message}（${error.code}）` : '加载失败'
  } finally {
    loading.value = false
  }
}

watch(currentDate, () => void load())
onMounted(() => void load())
</script>

<style scoped>
.ys-calendar-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 100%;
}

.ys-calendar-cell__day {
  font-weight: 600;
  color: var(--ys-navy-900, #1f2d3d);
}

.ys-calendar-cell__task {
  padding: 0 4px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 18px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  background: var(--el-color-info-light-9);
}

.ys-calendar-cell__task--completed {
  background: var(--el-color-success-light-9);
}

.ys-calendar-cell__task--in_progress {
  background: var(--el-color-primary-light-9);
}

.ys-calendar-cell__task--pending {
  background: var(--el-color-warning-light-9);
}

.ys-calendar-cell__task--cancelled {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
}
</style>