<template>
  <entity-list-page
    title="款式档案"
    entity-label="款式"
    description="款式档案是产品资料的第一层，下按颜色 + 尺码派生 SKU。SKU 与库存物料一一对应，避免同一件商品出现两套编码。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'masterdata.style.create', update: 'masterdata.style.update' }"
    search-placeholder="搜索款式编码或名称"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { styleApi } from '@/api/endpoints'
import { companyOptions, materialCategoryOptions } from '@/composables/optionLoaders'

const api = styleApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '款式编码', width: 150, sortable: true },
  { prop: 'name', label: '款式名称', minWidth: 160 },
  { prop: 'category_name', label: '分类', minWidth: 120 },
  { prop: 'brand', label: '品牌', width: 110 },
  { prop: 'season', label: '季节', width: 90 },
  { prop: 'year', label: '年份', width: 80 },
  { prop: 'series', label: '系列', width: 110 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'category_id', label: '分类', type: 'select' as const, optionsLoader: materialCategoryOptions },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '款式编码', required: true },
  { prop: 'name', label: '款式名称', required: true },
  { prop: 'category_id', label: '分类', type: 'select', optionsLoader: materialCategoryOptions },
  { prop: 'brand', label: '品牌' },
  { prop: 'season', label: '季节' },
  { prop: 'year', label: '年份' },
  { prop: 'series', label: '系列' },
  { prop: 'gender', label: '适用性别' },
  { prop: 'description', label: '款式说明', type: 'textarea', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>