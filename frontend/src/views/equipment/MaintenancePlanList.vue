<template>
  <entity-list-page
    title="保养计划"
    entity-label="保养计划"
    description="保养计划按周期给设备排保养：计划编号留空时自动生成，下次保养日期默认等于开始日期。到期后在行上点「生成任务」即按周期补出保养任务，重复点击不会重复生成。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.maintenance_plan.create', update: 'equipment.maintenance_plan.update', deactivate: 'equipment.maintenance_plan.update' }"
    search-placeholder="搜索计划编号、名称或设备"
    default-ordering="-id"
    :page-size="20"
    :action-width="260"
  >
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canGenerateTasks"
        link
        type="warning"
        size="small"
        @click="generateTasks(row, reload)"
      >
        生成任务
      </el-button>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { maintenancePlanApi } from '@/api/endpoints'
import { departmentOptions, employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { maintenanceItemOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const api = maintenancePlanApi as never

const canGenerateTasks = computed(() => auth.hasPermission('equipment.maintenance_task.create'))

interface GenerateResult {
  created_count: number
  next_date: string
  limit: number
}

async function generateTasks(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    const result = await maintenancePlanApi.action<GenerateResult>(
      Number(row.id),
      'generate-tasks',
      {},
    )
    if (result.created_count === 0) {
      ElMessage.info(`当前没有到期的保养任务，下次保养日期为 ${result.next_date}`)
    } else {
      ElMessage.success(
        `已生成 ${result.created_count} 条保养任务，下次保养日期 ${result.next_date}`,
      )
    }
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '生成保养任务失败')
  }
}

const columns: ProTableColumn[] = [
  { prop: 'plan_no', label: '计划编号', width: 150, sortable: true },
  { prop: 'name', label: '计划名称', minWidth: 150 },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'cycle_days', label: '保养周期（天）', width: 130 },
  { prop: 'start_date', label: '开始日期', width: 120 },
  { prop: 'next_date', label: '下次保养日期', width: 130 },
  { prop: 'responsible_employee_name', label: '负责人', width: 110 },
  { prop: 'item_names', label: '保养项目', minWidth: 180 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'department_id',
    label: '负责部门',
    type: 'select' as const,
    optionsLoader: departmentOptions,
  },
])

const detailFields = [
  { prop: 'department_name', label: '负责部门' },
  { prop: 'item_names', label: '保养项目' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'equipment_id',
    label: '设备',
    type: 'select',
    required: true,
    optionsLoader: equipmentOptions,
  },
  { prop: 'name', label: '计划名称', required: true },
  {
    prop: 'plan_no',
    label: '计划编号',
    onlyOnUpdate: true,
    help: '同一公司内唯一；留空时由系统按编号规则自动生成',
  },
  { prop: 'cycle_days', label: '保养周期（天）', type: 'number', required: true, defaultValue: 30 },
  { prop: 'start_date', label: '开始日期', type: 'date', required: true },
  {
    prop: 'next_date',
    label: '下次保养日期',
    type: 'date',
    onlyOnUpdate: true,
    help: '「生成任务」时会自动往后推进，通常不需要手工改',
  },
  {
    prop: 'item_ids',
    label: '保养项目',
    type: 'select',
    multiple: true,
    optionsLoader: maintenanceItemOptions,
    help: '可多选；留空表示由任务执行时按现场情况填写',
  },
  {
    prop: 'responsible_employee_id',
    label: '负责人',
    type: 'select',
    optionsLoader: employeeOptions,
  },
  { prop: 'department_id', label: '负责部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>