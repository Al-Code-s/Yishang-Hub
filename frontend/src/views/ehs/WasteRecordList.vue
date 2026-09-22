<template>
  <entity-list-page
    title="固废危废"
    entity-label="固废危废记录"
    description="一般固废与危险废物的产生、厂内暂存、转移与处置记录：废物代码、产生量、暂存位置、处置方式、转移单号与处置单位。危废转移必须留下转移单号，方便应对环保核查。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.waste.create', update: 'ehs.waste.update' }"
    search-placeholder="搜索废物编号、名称、代码、转移单号或处置单位"
    default-ordering="-produced_date"
    :toggleable="false"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { wasteRecordApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'

const api = wasteRecordApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'waste_no', label: '废物编号', width: 150, sortable: true },
  { prop: 'waste_name', label: '废物名称', minWidth: 160 },
  { prop: 'waste_type', label: '废物类别', width: 110 },
  { prop: 'waste_code', label: '废物代码', width: 120 },
  { prop: 'quantity', label: '产生量', width: 110, formatter: (row) => formatDecimal(row.quantity as string) },
  { prop: 'unit', label: '单位', width: 80 },
  { prop: 'produced_date', label: '产生日期', width: 120, sortable: true },
  { prop: 'storage_location', label: '暂存位置', width: 140 },
  { prop: 'disposal_method', label: '处置方式', width: 130 },
  { prop: 'disposal_org', label: '处置单位', width: 160 },
  { prop: 'transfer_no', label: '转移单号', width: 150 },
  { prop: 'status', label: '状态', width: 100 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'waste_type', label: '废物类别', type: 'select' as const, options: meta.options('waste_types') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('waste_statuses') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'disposed_date', label: '处置日期' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'waste_no', label: '废物编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'waste_name', label: '废物名称', required: true },
  { prop: 'waste_type', label: '废物类别', type: 'select', required: true, options: meta.options('waste_types'), defaultValue: "general" },
  { prop: 'waste_code', label: '废物代码', help: '危险废物按国家名录填写，例如 HW08' },
  { prop: 'quantity', label: '产生量', type: 'decimal', defaultValue: "0" },
  { prop: 'unit', label: '单位', defaultValue: "吨" },
  { prop: 'produced_date', label: '产生日期', type: 'date' },
  { prop: 'storage_location', label: '暂存位置' },
  { prop: 'disposal_method', label: '处置方式' },
  { prop: 'disposal_org', label: '处置单位' },
  { prop: 'transfer_no', label: '转移单号' },
  { prop: 'disposed_date', label: '处置日期', type: 'date' },
  { prop: 'status', label: '状态', type: 'select', options: meta.options('waste_statuses'), defaultValue: "stored" },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
