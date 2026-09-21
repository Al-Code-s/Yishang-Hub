<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">车间与线体</h2>
        <p class="ys-page__description">
          工厂 → 车间 → 线体 → 工位的四级组织结构。工位是生产报工、质量检验等现场记录的最小归属单位。
        </p>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="车间" name="workshop">
        <entity-list-page
          v-if="activeTab === 'workshop'"
          title="车间"
          entity-label="车间"
          :api="workshopApiRef"
          :columns="workshopColumns"
          :filters="workshopFilters"
          :form-fields="workshopFormFields"
          :permissions="{ create: 'factory.workshop.create', update: 'factory.workshop.update' }"
          search-placeholder="搜索车间编码或名称"
        />
      </el-tab-pane>
      <el-tab-pane label="线体" name="line">
        <entity-list-page
          v-if="activeTab === 'line'"
          title="线体"
          entity-label="线体"
          :api="lineApiRef"
          :columns="lineColumns"
          :filters="lineFilters"
          :form-fields="lineFormFields"
          :permissions="{ create: 'factory.line.create', update: 'factory.line.update' }"
          search-placeholder="搜索线体编码或名称"
        />
      </el-tab-pane>
      <el-tab-pane label="工位" name="station">
        <entity-list-page
          v-if="activeTab === 'station'"
          title="工位"
          entity-label="工位"
          :api="stationApiRef"
          :columns="stationColumns"
          :filters="stationFilters"
          :form-fields="stationFormFields"
          :permissions="{ create: 'factory.station.create', update: 'factory.station.update' }"
          search-placeholder="搜索工位编码或名称"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { lineApi, stationApi, workshopApi } from '@/api/endpoints'
import { factoryOptions, lineOptions, workshopOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const activeTab = ref<'workshop' | 'line' | 'station'>('workshop')

const workshopApiRef = workshopApi as never
const lineApiRef = lineApi as never
const stationApiRef = stationApi as never

const workshopColumns: ProTableColumn[] = [
  { prop: 'code', label: '车间编码', width: 130, sortable: true },
  { prop: 'name', label: '车间名称', minWidth: 160 },
  { prop: 'factory_name', label: '所属工厂', width: 160 },
  { prop: 'workshop_type', label: '车间类型', width: 120 },
  { prop: 'sort_order', label: '排序', width: 80 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const lineColumns: ProTableColumn[] = [
  { prop: 'code', label: '线体编码', width: 130, sortable: true },
  { prop: 'name', label: '线体名称', minWidth: 160 },
  { prop: 'workshop_name', label: '所属车间', width: 160 },
  { prop: 'line_type', label: '线体类型', width: 120 },
  {
    prop: 'daily_capacity',
    label: '日产能',
    width: 120,
    formatter: (row) => formatAmount(row.daily_capacity as string, 0),
  },
  { prop: 'is_active', label: '状态', width: 90 },
]

const stationColumns: ProTableColumn[] = [
  { prop: 'code', label: '工位编码', width: 130, sortable: true },
  { prop: 'name', label: '工位名称', minWidth: 160 },
  { prop: 'line_name', label: '所属线体', width: 160 },
  { prop: 'station_type', label: '工位类型', width: 120 },
  { prop: 'sort_order', label: '排序', width: 80 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const workshopFilters = computed(() => [
  { prop: 'factory_id', label: '所属工厂', type: 'select' as const, optionsLoader: factoryOptions },
  {
    prop: 'workshop_type',
    label: '车间类型',
    type: 'select' as const,
    options: meta.options('workshop_types'),
  },
])

const lineFilters = computed(() => [
  { prop: 'workshop_id', label: '所属车间', type: 'select' as const, optionsLoader: workshopOptions },
  { prop: 'line_type', label: '线体类型', type: 'select' as const, options: meta.options('line_types') },
])

const stationFilters = [
  { prop: 'line_id', label: '所属线体', type: 'select' as const, optionsLoader: lineOptions },
]

const workshopFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'factory_id', label: '所属工厂', type: 'select', required: true, optionsLoader: factoryOptions },
  { prop: 'code', label: '车间编码', required: true },
  { prop: 'name', label: '车间名称', required: true },
  {
    prop: 'workshop_type',
    label: '车间类型',
    type: 'select',
    options: meta.options('workshop_types'),
  },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const lineFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'workshop_id', label: '所属车间', type: 'select', required: true, optionsLoader: workshopOptions },
  { prop: 'code', label: '线体编码', required: true },
  { prop: 'name', label: '线体名称', required: true },
  { prop: 'line_type', label: '线体类型', type: 'select', options: meta.options('line_types') },
  { prop: 'daily_capacity', label: '日产能', type: 'decimal' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const stationFormFields: FormFieldDef[] = [
  { prop: 'line_id', label: '所属线体', type: 'select', required: true, optionsLoader: lineOptions },
  { prop: 'code', label: '工位编码', required: true },
  { prop: 'name', label: '工位名称', required: true },
  { prop: 'station_type', label: '工位类型' },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
]
</script>