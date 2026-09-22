<template>
  <entity-list-page
    title="点巡检记录"
    entity-label="点巡检记录"
    description="点巡检记录逐项登记实测值与判定。判定为异常的记录可以点「转报修」直接生成故障保修单，形成「点检发现 → 报修 → 维修」闭环。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.inspection_record.create', update: 'equipment.inspection_record.update' }"
    search-placeholder="搜索记录编号、设备或异常描述"
    default-ordering="-inspected_at"
    :toggleable="false"
    :page-size="20"
    :action-width="220"
    ref="pageRef"
  >
    <template #column-result="{ row }">
      <el-tag
        :type="row.result === 'abnormal' ? 'danger' : 'success'"
        size="small"
        effect="light"
      >
        {{ row.result_display || meta.label('equipment_inspection_results', String(row.result)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canRaiseFault && row.result === 'abnormal'"
        link
        type="danger"
        size="small"
        @click="raiseFault(row)"
      >
        转报修
      </el-button>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { inspectionRecordApi } from '@/api/endpoints'
import {
  employeeOptions,
  equipmentOptions,
  inspectionItemOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'

const auth = useAuthStore()
const meta = useMetaStore()
const api = inspectionRecordApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canRaiseFault = computed(() => auth.hasPermission('equipment.fault_report.create'))

const columns: ProTableColumn[] = [
  { prop: 'record_no', label: '记录编号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'item_name', label: '点巡检项目', width: 150 },
  { prop: 'measured_value', label: '实测值', width: 110 },
  { prop: 'result', label: '判定', width: 100 },
  { prop: 'abnormal_desc', label: '异常描述', minWidth: 180 },
  { prop: 'inspector_name', label: '检查人', width: 110 },
  { prop: 'inspected_at', label: '检查时间', width: 170 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'item_id',
    label: '点巡检项目',
    type: 'select' as const,
    optionsLoader: inspectionItemOptions,
  },
  {
    prop: 'result',
    label: '判定',
    type: 'select' as const,
    options: meta.options('equipment_inspection_results'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
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
  {
    prop: 'item_id',
    label: '点巡检项目',
    type: 'select',
    optionsLoader: inspectionItemOptions,
  },
  { prop: 'measured_value', label: '实测值', type: 'decimal', nullable: true },
  {
    prop: 'result',
    label: '判定',
    type: 'select',
    options: meta.options('equipment_inspection_results'),
    defaultValue: 'normal',
  },
  {
    prop: 'abnormal_desc',
    label: '异常描述',
    type: 'textarea',
    span: 24,
    help: '判定为异常时请写清楚现象，转报修时这段描述会带给维修人员',
  },
  { prop: 'inspector_id', label: '检查人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function raiseFault(row: Record<string, unknown>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '将按该记录的设备与描述生成一张故障保修单，随后可在「故障保修」里派工。确认转报修？',
    '转报修确认',
    { type: 'warning', confirmButtonText: '确认转报修', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await inspectionRecordApi.action(Number(row.id), 'raise-fault', { level: 'medium' })
    ElMessage.success('已生成故障保修单')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '转报修失败')
  }
}
</script>