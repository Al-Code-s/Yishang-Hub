<template>
  <entity-list-page
    title="电价管理"
    entity-label="价格"
    description="用电价管理：按尖峰平谷时段维护单价，能耗统计与报表按发生日期套用对应时段的价格折算费用。同一介质同一时段请只保留一条生效中的价格，改价时新增一条并把旧价的失效日期填上，历史费用才不会跟着变。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ems.price.create', update: 'ems.price.update' }"
    search-placeholder="搜索价格方案名称"
    default-ordering="effective_from"
    :initial-filters="{ medium: MEDIUM }"
    :transform="transform"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { energyPriceApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const api = energyPriceApi as never
const meta = useMetaStore()
const MEDIUM = 'electricity'
const transform = (payload: Record<string, unknown>): Record<string, unknown> => ({
  ...payload,
  medium: MEDIUM,
})

const columns: ProTableColumn[] = [
  { prop: 'medium', label: '介质', width: 80 },
  { prop: 'tariff_period', label: '时段', width: 80 },
  { prop: 'name', label: '价格方案', minWidth: 160 },
  { prop: 'unit_price', label: '单价', width: 110, formatter: (row) => formatAmount(row.unit_price as string) },
  { prop: 'currency_unit', label: '单位', width: 90 },
  { prop: 'effective_from', label: '生效日期', width: 120, sortable: true },
  { prop: 'effective_to', label: '失效日期', width: 120 },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'tariff_period', label: '时段', type: 'select' as const, options: meta.options('tariff_periods') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'tariff_period', label: '时段', type: 'select', required: true, options: meta.options('tariff_periods'), defaultValue: "flat" },
  { prop: 'name', label: '价格方案', required: true },
  { prop: 'unit_price', label: '单价', type: 'decimal', required: true, defaultValue: "0" },
  { prop: 'currency_unit', label: '计量单位', defaultValue: "元" },
  { prop: 'effective_from', label: '生效日期', type: 'date', required: true },
  { prop: 'effective_to', label: '失效日期', type: 'date', help: '留空表示一直有效', nullable: true },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
