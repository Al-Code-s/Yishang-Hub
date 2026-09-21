<template>
  <entity-list-page
    title="员工档案"
    entity-label="员工"
    description="员工档案记录所属公司、部门、岗位与排班。需要登录系统的员工，另在「系统管理 → 用户管理」中建立账号并关联本档案。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'factory.employee.create', update: 'factory.employee.update' }"
    search-placeholder="搜索工号或姓名"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('employee_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-user_id="{ row }">
      <el-tag v-if="row.user_id" type="success" size="small" effect="plain">
        {{ row.username }}
      </el-tag>
      <span v-else class="ys-muted">无登录账号</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { employeeApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, factoryOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = employeeApi as never

const columns: ProTableColumn[] = [
  { prop: 'employee_no', label: '工号', width: 120, sortable: true },
  { prop: 'name', label: '姓名', width: 120 },
  { prop: 'company_name', label: '所属公司', width: 160 },
  { prop: 'department_name', label: '部门', width: 130 },
  { prop: 'factory_name', label: '工厂', width: 130 },
  { prop: 'position', label: '岗位', width: 120 },
  { prop: 'employment_type', label: '用工形式', width: 110 },
  { prop: 'status', label: '在职状态', width: 110 },
  { prop: 'user_id', label: '登录账号', width: 130 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'department_id', label: '部门', type: 'select' as const, optionsLoader: departmentOptions },
  { prop: 'factory_id', label: '工厂', type: 'select' as const, optionsLoader: factoryOptions },
  {
    prop: 'status',
    label: '在职状态',
    type: 'select' as const,
    options: meta.options('employee_statuses'),
  },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'employee_no', label: '工号', required: true, help: '同一公司内唯一' },
  { prop: 'name', label: '姓名', required: true },
  { prop: 'department_id', label: '部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'factory_id', label: '所属工厂', type: 'select', optionsLoader: factoryOptions },
  { prop: 'gender', label: '性别', type: 'select', options: meta.options('employee_genders') },
  { prop: 'phone', label: '手机号' },
  { prop: 'email', label: '邮箱' },
  { prop: 'position', label: '岗位' },
  {
    prop: 'employment_type',
    label: '用工形式',
    type: 'select',
    options: meta.options('employment_types'),
  },
  { prop: 'hire_date', label: '入职日期', type: 'date' },
  { prop: 'leave_date', label: '离职日期', type: 'date' },
  { prop: 'status', label: '在职状态', type: 'select', options: meta.options('employee_statuses') },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

function statusTagType(status: string): 'success' | 'info' | 'warning' {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'leave') {
    return 'warning'
  }
  return 'info'
}
</script>