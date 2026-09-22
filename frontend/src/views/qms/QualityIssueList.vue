<template>
  <entity-list-page
    title="质量问题知识库"
    entity-label="质量问题"
    description="把「这一次为什么不合格」沉淀成「下次怎么避免」。条目从草稿开始：现象必填，原因分析与纠正 / 预防措施补齐后发布；过时条目归档而不是删除，历史结论与来源单据都能追溯。由质量报警转换来的条目会自动带上来源报警与检验单。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'qms.issue.create', update: 'qms.issue.update' }"
    search-placeholder="搜索问题编号、标题、现象或原因"
    default-ordering="-id"
    :toggleable="false"
    :page-size="20"
    :action-width="240"
    ref="pageRef"
  >
    <template #column-category="{ row }">
      {{ meta.label('quality_issue_categories', String(row.category)) }}
    </template>
    <template #column-severity="{ row }">
      <el-tag :type="severityTagType(String(row.severity))" size="small" effect="light">
        {{ meta.label('quality_alert_levels', String(row.severity)) }}
      </el-tag>
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('quality_issue_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-source="{ row }">
      <span class="ys-mono">{{ row.source_alert_no || row.source_order_no || '-' }}</span>
    </template>
    <template #row-actions="{ row }">
      <el-button
        v-if="canPublish && row.status === 'draft'"
        link
        type="success"
        size="small"
        @click="publishIssue(row)"
      >
        发布
      </el-button>
      <el-button
        v-if="canArchive && row.status !== 'archived'"
        link
        type="warning"
        size="small"
        @click="archiveIssue(row)"
      >
        归档
      </el-button>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { qualityIssueApi } from '@/api/endpoints'
import { companyOptions, materialOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'

const auth = useAuthStore()
const meta = useMetaStore()
const api = qualityIssueApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canPublish = computed(() => auth.hasPermission('qms.issue.publish'))
const canArchive = computed(() => auth.hasPermission('qms.issue.archive'))

function severityTagType(severity: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (severity === 'critical') return 'danger'
  if (severity === 'major') return 'warning'
  return 'info'
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'published') return 'success'
  if (status === 'archived') return 'info'
  return 'warning'
}

const columns: ProTableColumn[] = [
  { prop: 'issue_no', label: '问题编号', width: 150, sortable: true },
  { prop: 'title', label: '问题标题', minWidth: 220 },
  { prop: 'category', label: '问题分类', width: 110 },
  { prop: 'severity', label: '严重程度', width: 100 },
  { prop: 'material_name', label: '关联物料', minWidth: 140 },
  { prop: 'source', label: '来源单据', width: 160 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'published_at', label: '发布时间', width: 170, sortable: true },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'category',
    label: '问题分类',
    type: 'select' as const,
    options: meta.options('quality_issue_categories'),
  },
  {
    prop: 'severity',
    label: '严重程度',
    type: 'select' as const,
    options: meta.options('quality_alert_levels'),
  },
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('quality_issue_statuses'),
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'phenomenon', label: '问题现象' },
  { prop: 'cause', label: '原因分析' },
  { prop: 'corrective_action', label: '纠正措施' },
  { prop: 'preventive_action', label: '预防措施' },
  { prop: 'product_desc', label: '产品 / 物料描述' },
  { prop: 'source_order_no', label: '来源检验单' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'issue_no',
    label: '问题编号',
    onlyOnUpdate: true,
    help: '同一公司内唯一；留空时由系统按编号规则自动生成',
  },
  { prop: 'title', label: '问题标题', required: true, span: 24 },
  {
    prop: 'category',
    label: '问题分类',
    type: 'select',
    required: true,
    options: meta.options('quality_issue_categories'),
    defaultValue: 'material',
  },
  {
    prop: 'severity',
    label: '严重程度',
    type: 'select',
    options: meta.options('quality_alert_levels'),
    defaultValue: 'major',
  },
  { prop: 'material_id', label: '关联物料', type: 'select', optionsLoader: materialOptions },
  { prop: 'product_desc', label: '产品 / 物料描述' },
  { prop: 'phenomenon', label: '问题现象', type: 'textarea', span: 24, required: true },
  { prop: 'cause', label: '原因分析', type: 'textarea', span: 24 },
  { prop: 'corrective_action', label: '纠正措施', type: 'textarea', span: 24 },
  { prop: 'preventive_action', label: '预防措施', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

async function publishIssue(row: Record<string, unknown>): Promise<void> {
  try {
    await qualityIssueApi.action(Number(row.id), 'publish', {})
    ElMessage.success('已发布')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '发布失败')
  }
}

async function archiveIssue(row: Record<string, unknown>): Promise<void> {
  try {
    await qualityIssueApi.action(Number(row.id), 'archive', {})
    ElMessage.success('已归档')
    await pageRef.value?.reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '归档失败')
  }
}
</script>
