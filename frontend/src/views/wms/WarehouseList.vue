<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">仓库与储位</h2>
        <p class="ys-page__description">
          阶段 1 只交付仓库、库区、储位主数据。库存余额、流水、单据过账属阶段 2，
          此处不展示任何虚构的库存数字。
        </p>
      </div>
      <el-button @click="loadTree" :loading="treeLoading">刷新结构</el-button>
    </div>

    <el-alert
      v-if="treeError"
      type="error"
      :closable="false"
      show-icon
      :title="treeError"
      class="ys-form-error"
    />

    <el-tabs v-model="activeTab">
      <el-tab-pane label="仓库" name="warehouse">
        <entity-list-page
          v-if="activeTab === 'warehouse'"
          title="仓库"
          entity-label="仓库"
          :api="warehouseApiRef"
          :columns="warehouseColumns"
          :filters="warehouseFilters"
          :form-fields="warehouseFormFields"
          :permissions="{ create: 'wms.warehouse.create', update: 'wms.warehouse.update' }"
          search-placeholder="搜索仓库编码或名称"
        />
      </el-tab-pane>

      <el-tab-pane label="库区" name="zone">
        <entity-list-page
          v-if="activeTab === 'zone'"
          title="库区"
          entity-label="库区"
          :api="zoneApiRef"
          :columns="zoneColumns"
          :filters="zoneFilters"
          :form-fields="zoneFormFields"
          :permissions="{ create: 'wms.zone.create', update: 'wms.zone.update' }"
          search-placeholder="搜索库区编码或名称"
        />
      </el-tab-pane>

      <el-tab-pane label="储位" name="location">
        <entity-list-page
          v-if="activeTab === 'location'"
          title="储位"
          entity-label="储位"
          :api="locationApiRef"
          :columns="locationColumns"
          :filters="locationFilters"
          :form-fields="locationFormFields"
          :permissions="{ create: 'wms.location.create', update: 'wms.location.update' }"
          search-placeholder="搜索储位编码或名称"
        />
      </el-tab-pane>
    </el-tabs>

    <el-card shadow="never" class="ys-warehouse-tree">
      <template #header>仓库结构预览</template>
      <el-tree
        v-if="tree.length > 0"
        :data="tree"
        node-key="key"
        :props="{ label: 'label', children: 'children' }"
        default-expand-all
      />
      <el-empty v-else-if="!treeLoading" description="暂无仓库结构数据" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { locationApi, warehouseApi, zoneApi } from '@/api/endpoints'
import { wmsApi } from '@/api/modules'
import { companyOptions, departmentOptions, factoryOptions, warehouseOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const activeTab = ref<'warehouse' | 'zone' | 'location'>('warehouse')

const warehouseApiRef = warehouseApi as never
const zoneApiRef = zoneApi as never
const locationApiRef = locationApi as never

const warehouseColumns: ProTableColumn[] = [
  { prop: 'code', label: '仓库编码', width: 130, sortable: true },
  { prop: 'name', label: '仓库名称', minWidth: 150 },
  { prop: 'warehouse_type', label: '仓库类型', width: 120 },
  { prop: 'company_name', label: '所属公司', width: 170 },
  { prop: 'factory_name', label: '所属工厂', width: 140 },
  { prop: 'manager_name', label: '负责人', width: 110 },
  { prop: 'allow_negative_stock', label: '允许负库存', width: 120 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const zoneColumns: ProTableColumn[] = [
  { prop: 'code', label: '库区编码', width: 130, sortable: true },
  { prop: 'name', label: '库区名称', minWidth: 150 },
  { prop: 'warehouse_name', label: '所属仓库', width: 160 },
  { prop: 'zone_type', label: '库区类型', width: 120 },
  { prop: 'allow_mixed_batch', label: '允许混批', width: 110 },
  { prop: 'location_count', label: '储位数', width: 100 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const locationColumns: ProTableColumn[] = [
  { prop: 'code', label: '储位编码', width: 140, sortable: true },
  { prop: 'name', label: '储位名称', minWidth: 130 },
  { prop: 'zone_name', label: '所属库区', width: 150 },
  { prop: 'warehouse_code', label: '所属仓库', width: 130 },
  { prop: 'location_type', label: '储位类型', width: 110 },
  { prop: 'row_no', label: '排', width: 70 },
  { prop: 'column_no', label: '列', width: 70 },
  { prop: 'level_no', label: '层', width: 70 },
  {
    prop: 'capacity',
    label: '容量',
    width: 110,
    formatter: (row) => formatAmount(row.capacity as string, 3),
  },
  { prop: 'is_locked', label: '锁定', width: 80 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const warehouseFilters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'factory_id', label: '所属工厂', type: 'select' as const, optionsLoader: factoryOptions },
  {
    prop: 'warehouse_type',
    label: '仓库类型',
    type: 'select' as const,
    options: meta.options('warehouse_types'),
  },
])

const zoneFilters = computed(() => [
  { prop: 'warehouse_id', label: '所属仓库', type: 'select' as const, optionsLoader: warehouseOptions },
  { prop: 'zone_type', label: '库区类型', type: 'select' as const, options: meta.options('zone_types') },
])

const locationFilters = computed(() => [
  { prop: 'zone_id', label: '所属库区', type: 'select' as const, optionsLoader: warehouseOptions },
  {
    prop: 'location_type',
    label: '储位类型',
    type: 'select' as const,
    options: meta.options('location_types'),
  },
])

const warehouseFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '仓库编码', required: true },
  { prop: 'name', label: '仓库名称', required: true },
  {
    prop: 'warehouse_type',
    label: '仓库类型',
    type: 'select',
    options: meta.options('warehouse_types'),
  },
  { prop: 'factory_id', label: '所属工厂', type: 'select', optionsLoader: factoryOptions },
  { prop: 'department_id', label: '管理部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'manager_name', label: '负责人' },
  {
    prop: 'allow_negative_stock',
    label: '允许负库存',
    type: 'switch',
    defaultValue: false,
    help: '默认禁止负库存；开启仅用于确有必要且经审批的仓库',
  },
  { prop: 'address', label: '地址', span: 24 },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const zoneFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'warehouse_id', label: '所属仓库', type: 'select', required: true, optionsLoader: warehouseOptions },
  { prop: 'code', label: '库区编码', required: true },
  { prop: 'name', label: '库区名称', required: true },
  { prop: 'zone_type', label: '库区类型', type: 'select', options: meta.options('zone_types') },
  { prop: 'allow_mixed_batch', label: '允许混批', type: 'switch', defaultValue: false },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const locationFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'zone_id', label: '所属库区', type: 'select', required: true, optionsLoader: zoneOptionsForForm },
  { prop: 'code', label: '储位编码', required: true },
  { prop: 'name', label: '储位名称' },
  {
    prop: 'location_type',
    label: '储位类型',
    type: 'select',
    options: meta.options('location_types'),
  },
  { prop: 'row_no', label: '排' },
  { prop: 'column_no', label: '列' },
  { prop: 'level_no', label: '层' },
  { prop: 'capacity', label: '容量', type: 'decimal' },
  { prop: 'is_locked', label: '锁定', type: 'switch', defaultValue: false },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function zoneOptionsForForm() {
  const page = await zoneApi.list({ page_size: 200, is_active: true, ordering: 'code' })
  return page.results.map((row) => ({
    value: row.id,
    label: `${row.warehouse_name} / ${row.code} ${row.name}`,
  }))
}

interface TreeNode {
  key: string
  label: string
  children?: TreeNode[]
}

const tree = ref<TreeNode[]>([])
const treeLoading = ref(false)
const treeError = ref('')

async function loadTree(): Promise<void> {
  treeLoading.value = true
  treeError.value = ''
  try {
    const rows = await wmsApi.warehouseTree()
    tree.value = rows.map((warehouse) => ({
      key: `wh-${warehouse.id}`,
      label: `${warehouse.code} ${warehouse.name}`,
      children: warehouse.zones.map((zone) => ({
        key: `zone-${zone.id}`,
        label: `${zone.code} ${zone.name}`,
        children: zone.locations.map((location) => ({
          key: `loc-${location.id}`,
          label: `${location.code} ${location.name}${location.is_locked ? '（锁定）' : ''}`,
        })),
      })),
    }))
  } catch (error) {
    treeError.value = error instanceof ApiError ? error.message : '加载仓库结构失败'
    tree.value = []
  } finally {
    treeLoading.value = false
  }
}

onMounted(() => {
  void loadTree()
})
</script>

<style scoped>
.ys-warehouse-tree {
  margin: 16px;
}
</style>