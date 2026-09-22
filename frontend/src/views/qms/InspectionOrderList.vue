<template>
  <entity-list-page
    title="检验单"
    entity-label="检验单"
    description="检验单是一次检验的抬头，流程为：草稿 →（录入结果）→ 已提交 → 已判定 → 已关闭。定量项目的合格与否由系统按检验项目的上下限自动判定，界面填不了结论：只要存在不合格项就不能判「合格」，全合格也不能判「不合格」；判「让步接收」必须写清原因。判定不合格会自动生成质量报警，报警没闭环时检验单关不掉。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'qms.inspection.create', update: 'qms.inspection.update' }"
    search-placeholder="搜索检验单号、来源单据号、批次号或物料"
    default-ordering="-id"
    :toggleable="false"
    :page-size="20"
    :action-width="320"
    ref="pageRef"
  >
    <template #column-inspection_type="{ row }">
      {{ meta.label('quality_inspection_types', String(row.inspection_type)) }}
    </template>
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('quality_inspection_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-judgement="{ row }">
      <el-tag :type="judgementTagType(String(row.judgement))" size="small" effect="light">
        {{ meta.label('quality_judgements', String(row.judgement)) }}
      </el-tag>
    </template>
    <template #column-results="{ row }">
      <span class="ys-mono">{{ row.result_count }}</span>
      <el-tag v-if="Number(row.failed_count) > 0" type="danger" size="small" effect="dark" class="ys-ml-4">
        不合格 {{ row.failed_count }}
      </el-tag>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canUpdate && (row.status === 'draft' || row.status === 'submitted')"
        link
        type="primary"
        size="small"
        @click="openResults(row)"
      >
        录入结果
      </el-button>
      <el-button
        v-if="canSubmit && row.status === 'draft'"
        link
        type="warning"
        size="small"
        @click="submitOrder(row, reload)"
      >
        提交
      </el-button>
      <el-button
        v-if="canJudge && row.status === 'submitted'"
        link
        type="success"
        size="small"
        @click="openJudge(row)"
      >
        判定
      </el-button>
      <el-button
        v-if="canClose && row.status === 'judged'"
        link
        type="success"
        size="small"
        @click="closeOrder(row, reload)"
      >
        关闭
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="resultsVisible" title="录入检验结果" width="960px" :close-on-click-modal="false">
    <el-alert
      v-if="dialogError"
      type="error"
      :closable="false"
      show-icon
      :title="dialogError"
      class="ys-form-error"
    />
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="定量项目只要填实测值，合格与否由系统按标准区间判定；定性项目需要给出合格 / 不合格结论。"
      class="ys-form-error"
    />
    <el-table :data="resultRows" size="small" border>
      <el-table-column label="检验项目" min-width="200">
        <template #default="{ row }">
          <el-select
            v-model="row.item_id"
            filterable
            placeholder="选择检验项目"
            style="width: 100%"
            @change="onItemChange(row)"
          >
            <el-option
              v-for="option in itemChoiceOptions"
              :key="String(option.value)"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="判定方式" width="120">
        <template #default="{ row }">
          <span class="ys-muted">{{ valueTypeLabel(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="标准区间" width="150">
        <template #default="{ row }">
          <span class="ys-mono">{{ limitsText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="实测值" width="150">
        <template #default="{ row }">
          <el-input
            v-if="isQuantitative(row)"
            v-model="row.measured_value"
            placeholder="填写实测值"
          />
          <span v-else class="ys-muted">不适用</span>
        </template>
      </el-table-column>
      <el-table-column label="实测描述" min-width="140">
        <template #default="{ row }">
          <el-input v-model="row.text_value" placeholder="选填" />
        </template>
      </el-table-column>
      <el-table-column label="结论" width="140">
        <template #default="{ row }">
          <el-select
            v-if="!isQuantitative(row)"
            v-model="row.is_qualified"
            placeholder="请判定"
            style="width: 100%"
          >
            <el-option label="合格" :value="true" />
            <el-option label="不合格" :value="false" />
          </el-select>
          <span v-else class="ys-muted">系统判定</span>
        </template>
      </el-table-column>
      <el-table-column label="备注" min-width="140">
        <template #default="{ row }">
          <el-input v-model="row.remark" placeholder="选填" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ $index }">
          <el-button link type="danger" size="small" @click="removeRow($index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-button link type="primary" class="ys-ml-4" @click="addRow">添加一行</el-button>
    <template #footer>
      <el-button @click="resultsVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitResults">保存结果</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="judgeVisible" title="判定检验单" width="600px" :close-on-click-modal="false">
    <el-alert
      v-if="dialogError"
      type="error"
      :closable="false"
      show-icon
      :title="dialogError"
      class="ys-form-error"
    />
    <el-form label-width="110px">
      <el-form-item label="判定结论" required>
        <el-select v-model="judgeForm.judgement" clearable placeholder="留空时按检验结果自动判定" style="width: 100%">
          <el-option label="合格" value="passed" />
          <el-option label="不合格" value="failed" />
          <el-option label="让步接收" value="concession" />
        </el-select>
      </el-form-item>
      <el-form-item label="检验员">
        <el-select v-model="judgeForm.inspector_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in employeeChoiceOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="判定说明">
        <el-input
          v-model="judgeForm.judge_remark as string"
          type="textarea"
          :rows="3"
          placeholder="判定为「让步接收」时必须写明原因与放行条件"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="judgeVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitJudge">确认判定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { qualityInspectionApi, qualityInspectionItemApi } from '@/api/endpoints'
import {
  companyOptions,
  employeeOptions,
  equipmentOptions,
  lineOptions,
  materialOptions,
  supplierOptions,
  workshopOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

interface ResultRow {
  item_id: number | null
  measured_value: string
  text_value: string
  is_qualified: boolean | null
  remark: string
}

interface ItemBrief {
  id: number
  value_type: string
  unit: string
  lower_limit: string | null
  upper_limit: string | null
}

const auth = useAuthStore()
const meta = useMetaStore()
const api = qualityInspectionApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canUpdate = computed(() => auth.hasPermission('qms.inspection.update'))
const canSubmit = computed(() => auth.hasPermission('qms.inspection.submit'))
const canJudge = computed(() => auth.hasPermission('qms.inspection.judge'))
const canClose = computed(() => auth.hasPermission('qms.inspection.close'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'closed') return 'success'
  if (status === 'judged') return 'primary'
  if (status === 'submitted') return 'warning'
  return 'info'
}

function judgementTagType(judgement: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (judgement === 'passed') return 'success'
  if (judgement === 'failed') return 'danger'
  if (judgement === 'concession') return 'warning'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'order_no', label: '检验单号', width: 160, sortable: true },
  { prop: 'inspection_type', label: '检验类型', width: 110 },
  { prop: 'status', label: '单据状态', width: 100 },
  { prop: 'judgement', label: '判定结论', width: 110 },
  { prop: 'source_no', label: '来源单据号', width: 150 },
  { prop: 'material_name', label: '受检物料', minWidth: 160 },
  { prop: 'batch_no', label: '批次号', width: 130 },
  { prop: 'supplier_name', label: '供应商', minWidth: 140 },
  { prop: 'results', label: '检验项 / 不合格', width: 150 },
  { prop: 'inspector_name', label: '检验员', width: 110 },
  { prop: 'inspected_at', label: '检验时间', width: 170, sortable: true },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'inspection_type',
    label: '检验类型',
    type: 'select' as const,
    options: meta.options('quality_inspection_types'),
  },
  {
    prop: 'status',
    label: '单据状态',
    type: 'select' as const,
    options: meta.options('quality_inspection_statuses'),
  },
  {
    prop: 'judgement',
    label: '判定结论',
    type: 'select' as const,
    options: meta.options('quality_judgements'),
  },
  { prop: 'batch_no', label: '批次号', type: 'text' as const },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'product_desc', label: '产品 / 物料描述' },
  { prop: 'workshop_name', label: '受检车间' },
  { prop: 'production_line_name', label: '受检线体' },
  { prop: 'equipment_name', label: '受检设备' },
  { prop: 'quantity', label: '受检数量' },
  { prop: 'sample_quantity', label: '抽样数量' },
  { prop: 'judge_remark', label: '判定说明' },
  { prop: 'judged_at', label: '判定时间' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'order_no',
    label: '检验单号',
    onlyOnUpdate: true,
    help: '同一公司内唯一；留空时由系统按编号规则自动生成',
  },
  {
    prop: 'inspection_type',
    label: '检验类型',
    type: 'select',
    required: true,
    options: meta.options('quality_inspection_types'),
    defaultValue: 'iqc',
  },
  { prop: 'source_no', label: '来源单据号', help: '如采购收货单号、生产工单号' },
  { prop: 'material_id', label: '受检物料', type: 'select', optionsLoader: materialOptions },
  { prop: 'product_desc', label: '产品 / 物料描述' },
  { prop: 'batch_no', label: '批次号' },
  { prop: 'supplier_id', label: '供应商', type: 'select', optionsLoader: supplierOptions },
  { prop: 'workshop_id', label: '受检车间', type: 'select', optionsLoader: workshopOptions },
  { prop: 'production_line_id', label: '受检线体', type: 'select', optionsLoader: lineOptions },
  { prop: 'equipment_id', label: '受检设备', type: 'select', optionsLoader: equipmentOptions },
  { prop: 'quantity', label: '受检数量', type: 'decimal' },
  { prop: 'sample_quantity', label: '抽样数量', type: 'decimal' },
  { prop: 'unit', label: '单位' },
  { prop: 'inspector_id', label: '检验员', type: 'select', optionsLoader: employeeOptions },
  { prop: 'inspected_at', label: '检验时间', type: 'date' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const resultsVisible = ref(false)
const judgeVisible = ref(false)
const dialogError = ref('')
const submitting = ref(false)
const resultsTarget = ref<Record<string, unknown> | null>(null)
const judgeTarget = ref<Record<string, unknown> | null>(null)
const resultRows = ref<ResultRow[]>([])
const itemChoiceOptions = ref<EnumOption[]>([])
const employeeChoiceOptions = ref<EnumOption[]>([])
const itemBriefs = ref<Record<number, ItemBrief>>({})

const judgeForm = reactive<Record<string, unknown>>({
  judgement: '',
  inspector_id: null,
  judge_remark: '',
})

function briefOf(row: ResultRow): ItemBrief | null {
  if (row.item_id === null) {
    return null
  }
  return itemBriefs.value[Number(row.item_id)] ?? null
}

function isQuantitative(row: ResultRow): boolean {
  return briefOf(row)?.value_type === 'quantitative'
}

function valueTypeLabel(row: ResultRow): string {
  const brief = briefOf(row)
  if (!brief) {
    return '选择项目后显示'
  }
  return meta.label('inspection_value_types', brief.value_type)
}

function limitsText(row: ResultRow): string {
  const brief = briefOf(row)
  if (!brief) {
    return '-'
  }
  if (brief.lower_limit === null && brief.upper_limit === null) {
    return '无数值口径'
  }
  const unit = brief.unit ? ` ${brief.unit}` : ''
  return `${brief.lower_limit ?? '-'} ~ ${brief.upper_limit ?? '-'}${unit}`
}

function addRow(): void {
  resultRows.value.push({
    item_id: null,
    measured_value: '',
    text_value: '',
    is_qualified: null,
    remark: '',
  })
}

function removeRow(index: number): void {
  resultRows.value.splice(index, 1)
}

function onItemChange(row: ResultRow): void {
  if (!isQuantitative(row)) {
    row.measured_value = ''
  } else {
    row.is_qualified = null
  }
}

async function loadItems(): Promise<void> {
  const page = await qualityInspectionItemApi.list({ page_size: 200, is_active: true })
  itemChoiceOptions.value = page.results.map((item) => ({
    value: item.id,
    label: `${item.code} ${item.name}`,
  }))
  const briefs: Record<number, ItemBrief> = {}
  for (const item of page.results) {
    briefs[item.id] = {
      id: item.id,
      value_type: item.value_type,
      unit: item.unit,
      lower_limit: item.lower_limit,
      upper_limit: item.upper_limit,
    }
  }
  itemBriefs.value = briefs
}

onMounted(async () => {
  employeeChoiceOptions.value = await employeeOptions().catch(() => [])
  await loadItems().catch(() => undefined)
})

async function openResults(row: Record<string, unknown>): Promise<void> {
  resultsTarget.value = row
  dialogError.value = ''
  resultRows.value = []
  resultsVisible.value = true
  try {
    const detail = await qualityInspectionApi.retrieve(Number(row.id))
    const existing = detail.results ?? []
    if (existing.length > 0) {
      resultRows.value = existing.map((item) => ({
        item_id: item.item_id,
        measured_value: item.measured_value ?? '',
        text_value: item.text_value,
        is_qualified: item.is_qualified,
        remark: item.remark,
      }))
    } else {
      addRow()
    }
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '加载检验结果失败'
  }
}

function buildPayload(): { results?: unknown[]; error?: string } {
  const seen = new Set<number>()
  const rows: Record<string, unknown>[] = []
  for (let index = 0; index < resultRows.value.length; index += 1) {
    const row = resultRows.value[index]
    if (row.item_id === null) {
      return { error: `第 ${index + 1} 行还没有选择检验项目。` }
    }
    const itemId = Number(row.item_id)
    if (seen.has(itemId)) {
      return { error: `第 ${index + 1} 行的检验项目重复，请合并后再保存。` }
    }
    seen.add(itemId)
    const payload: Record<string, unknown> = {
      item_id: itemId,
      text_value: row.text_value,
      remark: row.remark,
      sort_order: index,
    }
    if (isQuantitative(row)) {
      const measured = String(row.measured_value ?? '').trim()
      if (!measured) {
        return { error: `第 ${index + 1} 行是定量项目，必须填写实测值。` }
      }
      payload.measured_value = measured
    } else {
      if (row.is_qualified === null) {
        return { error: `第 ${index + 1} 行是定性项目，必须给出合格 / 不合格结论。` }
      }
      payload.is_qualified = row.is_qualified
    }
    rows.push(payload)
  }
  if (rows.length === 0) {
    return { error: '至少录入一行检验结果。' }
  }
  return { results: rows }
}

async function submitResults(): Promise<void> {
  const target = resultsTarget.value
  if (!target) {
    return
  }
  const payload = buildPayload()
  if (payload.error) {
    dialogError.value = payload.error
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await qualityInspectionApi.action(Number(target.id), 'results', { results: payload.results })
    ElMessage.success('检验结果已保存')
    resultsVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function submitOrder(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await qualityInspectionApi.action(Number(row.id), 'submit', {})
    ElMessage.success('检验单已提交')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '提交失败')
  }
}

async function closeOrder(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  try {
    await qualityInspectionApi.action(Number(row.id), 'close', {})
    ElMessage.success('检验单已关闭')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '关闭失败')
  }
}

function openJudge(row: Record<string, unknown>): void {
  judgeTarget.value = row
  dialogError.value = ''
  judgeForm.judgement = ''
  judgeForm.inspector_id = null
  judgeForm.judge_remark = ''
  judgeVisible.value = true
}

async function submitJudge(): Promise<void> {
  const target = judgeTarget.value
  if (!target) {
    return
  }
  if (judgeForm.judgement === 'concession' && !String(judgeForm.judge_remark ?? '').trim()) {
    dialogError.value = '判定为「让步接收」必须填写判定说明。'
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    await qualityInspectionApi.action(Number(target.id), 'judge', {
      judgement: judgeForm.judgement,
      inspector_id: judgeForm.inspector_id,
      judge_remark: judgeForm.judge_remark,
    })
    ElMessage.success('已完成判定')
    judgeVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    dialogError.value = error instanceof ApiError ? error.message : '判定失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
