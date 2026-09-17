<template>
  <entity-list-page
    title="物料档案"
    entity-label="物料"
    description="面料 / 辅料 / 半成品 / 成品 / 包装物 / 备品备件 / 消耗品的统一物料主数据。米与公斤不做无条件换算，面料卷的实际换算依据记录在卷记录上。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'masterdata.material.create', update: 'masterdata.material.update' }"
    search-placeholder="搜索物料编码或名称"
    :page-size="20"
  >
    <template #toolbar>
      <el-tag type="info" effect="plain">数量精度 6 位小数 · 金额 4 位小数</el-tag>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { materialApi } from '@/api/endpoints'
import { companyOptions, materialCategoryOptions, uomOptions } from '@/composables/optionLoaders'
import { formatAmount } from '@/utils/decimal'

const api = materialApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '物料编码', width: 150, sortable: true },
  { prop: 'name', label: '物料名称', minWidth: 160 },
  { prop: 'category_name', label: '分类', minWidth: 120 },
  { prop: 'spec', label: '规格', minWidth: 120 },
  { prop: 'base_uom_name', label: '基本单位', width: 100 },
  {
    prop: 'purchase_price',
    label: '采购价',
    width: 110,
    formatter: (row) => formatAmount(row.purchase_price as string, 4),
  },
  {
    prop: 'safe_stock',
    label: '安全库存',
    width: 110,
    formatter: (row) => formatAmount(row.safe_stock as string, 3),
  },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'category_id',
    label: '物料分类',
    type: 'select' as const,
    optionsLoader: materialCategoryOptions,
  },
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
])

const detailFields = [
  { prop: 'brand', label: '品牌' },
  { prop: 'season', label: '季节' },
  { prop: 'year', label: '年份' },
  { prop: 'series', label: '系列' },
  { prop: 'purchase_uom_name', label: '采购单位' },
  { prop: 'sales_uom_name', label: '销售单位' },
  { prop: 'is_batch_managed', label: '批次管理' },
  { prop: 'is_roll_managed', label: '卷号管理' },
  { prop: 'is_serial_managed', label: '序列号管理' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '物料编码', required: true, help: '创建后不建议修改，编码被条码与流水引用' },
  { prop: 'name', label: '物料名称', required: true },
  {
    prop: 'category_id',
    label: '物料分类',
    type: 'select',
    required: true,
    optionsLoader: materialCategoryOptions,
  },
  { prop: 'spec', label: '规格' },
  { prop: 'base_uom_id', label: '基本单位', type: 'select', required: true, optionsLoader: uomOptions },
  { prop: 'purchase_uom_id', label: '采购单位', type: 'select', optionsLoader: uomOptions },
  { prop: 'purchase_factor', label: '采购换算率', type: 'decimal', help: '1 采购单位 = N 基本单位' },
  { prop: 'sales_uom_id', label: '销售单位', type: 'select', optionsLoader: uomOptions },
  { prop: 'sales_factor', label: '销售换算率', type: 'decimal' },
  { prop: 'safe_stock', label: '安全库存', type: 'decimal', defaultValue: '0' },
  { prop: 'purchase_price', label: '采购价', type: 'decimal' },
  { prop: 'reference_cost', label: '参考成本', type: 'decimal', help: '仅供管理参考，不等同财务核算成本' },
  { prop: 'brand', label: '品牌' },
  { prop: 'season', label: '季节' },
  { prop: 'year', label: '年份' },
  { prop: 'series', label: '系列' },
  { prop: 'is_batch_managed', label: '批次管理', type: 'switch', defaultValue: false },
  { prop: 'is_roll_managed', label: '卷号管理', type: 'switch', defaultValue: false },
  { prop: 'is_serial_managed', label: '序列号管理', type: 'switch', defaultValue: false },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>