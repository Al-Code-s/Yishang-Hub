<template>
  <entity-list-page
    title="环保合规"
    entity-label="合规检查"
    description="内部自查、政府检查、第三方审核与排污许可核查的记录：检查机构、检查日期、结论、发现问题与整改期限。发现问题后要先整改完成，再点「确认关闭」销项。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.compliance.create', update: 'ehs.compliance.update' }"
    search-placeholder="搜索检查编号、标题、检查机构或问题"
    default-ordering="-check_date"
    :toggleable="false"
    :page-size="20"
    :action-width="200"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('compliance_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canClose && row.status !== 'closed'"
        link
        type="success"
        size="small"
        @click="closeCheck(row, reload)"
      >
        确认关闭
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
import { complianceCheckApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'

const auth = useAuthStore()
const meta = useMetaStore()
const api = complianceCheckApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canClose = computed(() => auth.hasPermission('ehs.compliance.update'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'rectified') return 'primary'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'check_no', label: '检查编号', width: 150, sortable: true },
  { prop: 'title', label: '检查标题', minWidth: 180 },
  { prop: 'check_type', label: '检查类型', width: 130 },
  { prop: 'check_date', label: '检查日期', width: 120, sortable: true },
  { prop: 'organization', label: '检查机构', width: 160 },
  { prop: 'checker_name', label: '陪同/检查人', width: 130 },
  { prop: 'result', label: '检查结论', width: 120 },
  { prop: 'rectify_due_date', label: '整改期限', width: 120 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'rectified_date', label: '整改完成日期', width: 140 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'check_type', label: '检查类型', type: 'select' as const, options: meta.options('compliance_check_types') },
  { prop: 'result', label: '检查结论', type: 'select' as const, options: meta.options('compliance_results') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('compliance_statuses') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'issues', label: '发现问题' },
  { prop: 'owner_employee_name', label: '整改负责人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'check_no', label: '检查编号', onlyOnUpdate: true, help: '留空时由系统按编号规则自动生成' },
  { prop: 'title', label: '检查标题', required: true, span: 24 },
  {
    prop: 'check_type',
    label: '检查类型',
    type: 'select',
    required: true,
    options: meta.options('compliance_check_types'),
    defaultValue: 'self',
  },
  { prop: 'check_date', label: '检查日期', type: 'date' },
  { prop: 'organization', label: '检查机构' },
  { prop: 'checker_id', label: '陪同/检查人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'result', label: '检查结论', type: 'select', options: meta.options('compliance_results'), defaultValue: 'compliant' },
  { prop: 'rectify_due_date', label: '整改期限', type: 'date' },
  { prop: 'owner_employee_id', label: '整改负责人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'issues', label: '发现问题', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function closeCheck(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '关闭后该次合规检查视为已销项。确认关闭？',
    '关闭合规检查',
    { type: 'warning', confirmButtonText: '确认关闭', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await complianceCheckApi.action(Number(row.id), 'close', {})
    ElMessage.success('已关闭')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>
