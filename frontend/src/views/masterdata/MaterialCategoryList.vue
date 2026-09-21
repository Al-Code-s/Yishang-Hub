<template>
  <entity-list-page
    title="物料分类"
    entity-label="分类"
    description="物料分类：面料、辅料、半成品、成品、包装物、备品备件、消耗品。已被物料或款式使用的分类只能停用，不能删除。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'masterdata.material_category.create', update: 'masterdata.material_category.update' }"
    search-placeholder="搜索分类编码或名称"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { materialCategoryApi } from '@/api/endpoints'
import { materialCategoryOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = materialCategoryApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '分类编码', width: 140, sortable: true },
  { prop: 'name', label: '分类名称', minWidth: 160 },
  { prop: 'parent_name', label: '上级分类', minWidth: 140 },
  {
    prop: 'category_type',
    label: '分类类型',
    width: 120,
  },
  { prop: 'sort_order', label: '排序', width: 80 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'category_type',
    label: '分类类型',
    type: 'select' as const,
    options: meta.options('material_category_types'),
  },
  { prop: 'parent_id', label: '上级分类', type: 'select' as const, optionsLoader: materialCategoryOptions },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '分类编码', required: true, help: '唯一，建议 2-32 位大写字母与数字' },
  { prop: 'name', label: '分类名称', required: true },
  {
    prop: 'parent_id',
    label: '上级分类',
    type: 'select',
    optionsLoader: materialCategoryOptions,
  },
  {
    prop: 'category_type',
    label: '分类类型',
    type: 'select',
    options: meta.options('material_category_types'),
  },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>