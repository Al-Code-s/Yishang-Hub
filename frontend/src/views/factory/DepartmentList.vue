<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="部门"
      entity-label="部门"
      description="部门层级必须同公司且不能形成循环；已使用的部门只能停用，不能删除。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :form-fields="formFields"
      :permissions="{ create: 'factory.department.create', update: 'factory.department.update' }"
      search-placeholder="搜索部门编码或名称"
    />

    <el-card shadow="never" class="ys-department-tree">
      <template #header>
        <div class="ys-toolbar">
          <span>组织结构预览</span>
          <el-button size="small" @click="loadTree" :loading="treeLoading">刷新</el-button>
        </div>
      </template>
      <el-alert v-if="treeError" type="error" :closable="false" show-icon :title="treeError" />
      <el-tree
        v-if="tree.length > 0"
        :data="tree"
        node-key="id"
        :props="{ label: 'name', children: 'children' }"
        default-expand-all
      >
        <template #default="{ data }">
          <span>{{ data.code }} {{ data.name }}</span>
          <el-tag v-if="data.is_active === false" type="info" size="small" effect="plain">停用</el-tag>
        </template>
      </el-tree>
      <el-empty v-else-if="!treeLoading" description="暂无部门数据" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { departmentApi } from '@/api/endpoints'
import { factoryApi } from '@/api/modules'
import { companyOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import type { Department } from '@/types/models'

const meta = useMetaStore()
const pageRef = ref<InstanceType<typeof EntityListPage>>()
const api = departmentApi as never
const tree = ref<Department[]>([])
const treeLoading = ref(false)
const treeError = ref('')

const columns: ProTableColumn[] = [
  { prop: 'code', label: '部门编码', width: 130, sortable: true },
  { prop: 'name', label: '部门名称', minWidth: 160 },
  { prop: 'company_name', label: '所属公司', width: 160 },
  { prop: 'parent_name', label: '上级部门', width: 140 },
  { prop: 'full_path', label: '层级路径', minWidth: 200 },
  { prop: 'department_type', label: '部门类型', width: 110 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'department_type',
    label: '部门类型',
    type: 'select' as const,
    options: meta.options('department_types'),
  },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '部门编码', required: true },
  { prop: 'name', label: '部门名称', required: true },
  {
    prop: 'parent_id',
    label: '上级部门',
    type: 'select',
    optionsLoader: async () => {
      const page = await departmentApi.list({ page_size: 200, is_active: true, ordering: 'code' })
      return page.results.map((row) => ({ value: row.id, label: `${row.full_path || row.code}` }))
    },
    help: '上级部门必须属于同一公司，且不能选择自己的下级',
  },
  {
    prop: 'department_type',
    label: '部门类型',
    type: 'select',
    options: meta.options('department_types'),
  },
  { prop: 'sort_order', label: '排序号', type: 'number' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function loadTree(): Promise<void> {
  treeLoading.value = true
  treeError.value = ''
  try {
    tree.value = await factoryApi.departmentTree({ page_size: 200 })
  } catch (error) {
    treeError.value = error instanceof ApiError ? error.message : '加载组织结构失败'
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
.ys-department-tree {
  margin: 16px;
}
</style>