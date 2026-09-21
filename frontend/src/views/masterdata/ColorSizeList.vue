<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">颜色与尺码</h2>
        <p class="ys-page__description">
          颜色与尺码组成 SKU 的两个维度。已被款式或 SKU 使用的颜色、尺码只能停用、不能删除，
          以保证历史条码与单据仍能正常识别。
        </p>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="颜色" name="color">
        <entity-list-page
          v-if="activeTab === 'color'"
          title="颜色"
          entity-label="颜色"
          :api="colorApiRef"
          :columns="colorColumns"
          :form-fields="colorFormFields"
          :permissions="{ create: 'masterdata.color.create', update: 'masterdata.color.update' }"
          search-placeholder="搜索颜色编码或名称"
          default-ordering="sort_order"
        />
      </el-tab-pane>
      <el-tab-pane label="尺码" name="size">
        <entity-list-page
          v-if="activeTab === 'size'"
          title="尺码"
          entity-label="尺码"
          :api="sizeApiRef"
          :columns="sizeColumns"
          :form-fields="sizeFormFields"
          :permissions="{ create: 'masterdata.size.create', update: 'masterdata.size.update' }"
          search-placeholder="搜索尺码编码或名称"
          default-ordering="sort_order"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { colorApi, sizeApi } from '@/api/endpoints'

const activeTab = ref<'color' | 'size'>('color')

const colorApiRef = colorApi as never
const sizeApiRef = sizeApi as never

const colorColumns: ProTableColumn[] = [
  { prop: 'code', label: '颜色编码', width: 140, sortable: true },
  { prop: 'name', label: '颜色名称', minWidth: 140 },
  { prop: 'hex_code', label: '色值', width: 120 },
  { prop: 'sort_order', label: '排序', width: 80 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const sizeColumns: ProTableColumn[] = [
  { prop: 'code', label: '尺码编码', width: 140, sortable: true },
  { prop: 'name', label: '尺码名称', minWidth: 140 },
  { prop: 'sort_order', label: '排序', width: 80 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const colorFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '颜色编码', required: true },
  { prop: 'name', label: '颜色名称', required: true },
  { prop: 'hex_code', label: '色值', placeholder: '例如 #1B4C7E', help: '仅用于界面展示' },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const sizeFormFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '尺码编码', required: true },
  { prop: 'name', label: '尺码名称', required: true },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>