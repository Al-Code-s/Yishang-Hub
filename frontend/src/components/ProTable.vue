<template>
  <div class="ys-table-card">
    <div v-if="$slots.filters" class="ys-filter-bar">
      <slot name="filters" />
      <el-button type="primary" @click="emit('refresh')">查询</el-button>
      <el-button @click="emit('reset')">重置</el-button>
    </div>

    <div v-if="$slots.toolbar" class="ys-toolbar">
      <slot name="toolbar" />
    </div>

    <el-alert
      v-if="errorMessage"
      class="ys-table-card__error"
      type="error"
      :closable="false"
      show-icon
      :title="errorMessage"
    >
      <template #default>
        <div class="ys-muted">{{ errorHint }}</div>
      </template>
    </el-alert>

    <el-table
      v-loading="loading"
      :data="rows"
      border
      stripe
      size="small"
      :row-key="rowKey"
      :default-sort="defaultSort"
      @sort-change="onSortChange"
    >
      <el-table-column
        v-for="column in columns"
        :key="column.prop"
        :prop="column.prop"
        :label="column.label"
        :width="column.width"
        :min-width="column.minWidth"
        :sortable="column.sortable ? 'custom' : false"
        :fixed="column.fixed"
        show-overflow-tooltip
      >
        <template #default="scope">
          <slot :name="`column-${column.prop}`" :row="scope.row" :index="scope.$index">
            <span v-if="column.formatter">{{ column.formatter(scope.row) }}</span>
            <span v-else>{{ displayValue(scope.row, column.prop) }}</span>
          </slot>
        </template>
      </el-table-column>

      <el-table-column v-if="$slots.actions" label="操作" :width="actionWidth" fixed="right">
        <template #default="scope">
          <slot name="actions" :row="scope.row" :index="scope.$index" />
        </template>
      </el-table-column>

      <template #empty>
        <el-empty :description="emptyText" />
      </template>
    </el-table>

    <div class="ys-pagination">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @update:current-page="emit('update:page', $event)"
        @update:page-size="emit('update:pageSize', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/** 列定义。formatter 只在没有对应插槽时生效。 */
export interface ProTableColumn {
  prop: string
  label: string
  width?: number | string
  minWidth?: number | string
  sortable?: boolean
  fixed?: boolean | 'left' | 'right'
  formatter?: (row: Record<string, unknown>) => string
}

const props = withDefaults(
  defineProps<{
    columns: ProTableColumn[]
    rows: Record<string, unknown>[]
    total: number
    page: number
    pageSize: number
    loading?: boolean
    errorMessage?: string
    errorHint?: string
    emptyText?: string
    actionWidth?: number
    rowKey?: string
    defaultSort?: { prop: string; order: 'ascending' | 'descending' } | undefined
  }>(),
  {
    loading: false,
    errorMessage: '',
    errorHint: '如持续失败，请把页面提示与后端日志中的 request_id 一起反馈给系统管理员。',
    emptyText: '暂无数据',
    actionWidth: 200,
    rowKey: 'id',
    defaultSort: undefined,
  },
)

const emit = defineEmits<{
  refresh: []
  reset: []
  'update:page': [value: number]
  'update:pageSize': [value: number]
  'sort-change': [payload: { prop: string; order: 'ascending' | 'descending' | null }]
}>()

const columns = computed(() => props.columns)

function displayValue(row: Record<string, unknown>, prop: string): string {
  // 枚举列：后端会同时返回英文键与中文标签（如 warehouse_type / warehouse_type_display），
  // 展示层一律优先用中文标签，避免界面出现 raw / management / finished 这类英文值。
  const label = row[`${prop}_display`]
  if (label !== null && label !== undefined && label !== '') {
    return String(label)
  }
  const value = row[prop]
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? '-' : value.map((item) => String(item)).join('、')
  }
  return String(value)
}

function onSortChange(payload: { prop: string; order: string | null }): void {
  emit('sort-change', {
    prop: payload.prop,
    order: (payload.order as 'ascending' | 'descending' | null) ?? null,
  })
}
</script>

<style scoped>
.ys-table-card__error {
  margin-bottom: 12px;
}
</style>