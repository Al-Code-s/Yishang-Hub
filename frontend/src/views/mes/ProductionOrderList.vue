<template>
  <entity-list-page
    title="生产工单"
    entity-label="生产工单"
    description="生产工单是生产执行的起点：草稿 → 下达 → 生产中 → 已完工 → 已关闭，草稿与已下达（未开工）可以取消。下达会冻结当时的工艺路线与 BOM 快照并生成工序，之后工程数据出新版本不影响本工单；领料与完工入库都会生成并过账对应的库存单据，库存余额随之变化。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'mes.order.create', update: 'mes.order.update' }"
    search-placeholder="搜索工单号、来源单号或款式"
    default-ordering="-id"
    :page-size="20"
    :action-width="300"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('production_order_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-quantity="{ row }">
      {{ formatDecimal(row.quantity) }} {{ row.unit }}
    </template>
    <template #column-progress_rate="{ row }">
      {{ row.progress_rate }}%
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canRelease && row.status === 'draft'"
        link
        type="primary"
        size="small"
        @click="releaseOrder(row, reload)"
      >
        下达
      </el-button>
      <el-button
        v-if="canIssue && (row.status === 'released' || row.status === 'in_progress') && !row.issue_document_no"
        link
        type="primary"
        size="small"
        @click="issueMaterials(row, reload)"
      >
        领料
      </el-button>
      <el-button
        v-if="canComplete && row.status === 'in_progress'"
        link
        type="success"
        size="small"
        @click="completeOrder(row, reload)"
      >
        完工
      </el-button>
      <el-button
        v-if="canComplete && row.status === 'completed' && !row.receipt_document_no"
        link
        type="success"
        size="small"
        @click="openReceipt(row)"
      >
        完工入库
      </el-button>
      <el-button
        v-if="canClose && row.status === 'completed'"
        link
        type="info"
        size="small"
        @click="closeOrder(row, reload)"
      >
        关闭
      </el-button>
      <el-button
        v-if="canCancel && (row.status === 'draft' || row.status === 'released')"
        link
        type="danger"
        size="small"
        @click="cancelOrder(row, reload)"
      >
        取消
      </el-button>
    </template>

    <template #detail="{ row }">
      <el-divider content-position="left">工序（{{ (row?.steps as unknown[] | undefined)?.length ?? 0 }}）</el-divider>
      <el-table :data="(row?.steps as Record<string, unknown>[] | undefined) ?? []" size="small" border>
        <el-table-column prop="sequence" label="顺序" width="60" />
        <el-table-column prop="name" label="工序" min-width="100" />
        <el-table-column prop="status_display" label="状态" width="90" />
        <el-table-column label="报工 / 合格" width="130">
          <template #default="scope">
            {{ formatDecimal(scope.row.reported_quantity) }} /
            {{ formatDecimal(scope.row.qualified_quantity) }}
          </template>
        </el-table-column>
        <el-table-column label="质检点" width="90">
          <template #default="scope">{{ scope.row.is_quality_gate ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="inspection_order_no" label="检验单" width="130" />
        <el-table-column prop="inspection_judgement" label="判定" width="90" />
      </el-table>

      <el-divider content-position="left">用料（{{ (row?.materials as unknown[] | undefined)?.length ?? 0 }}）</el-divider>
      <el-table :data="(row?.materials as Record<string, unknown>[] | undefined) ?? []" size="small" border>
        <el-table-column prop="material_code" label="物料编码" width="130" />
        <el-table-column prop="material_name" label="物料名称" min-width="120" />
        <el-table-column label="应领 / 已领" width="150">
          <template #default="scope">
            {{ formatDecimal(scope.row.required_quantity) }} /
            {{ formatDecimal(scope.row.issued_quantity) }}
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="source_display" label="来源" width="100" />
      </el-table>
    </template>
  </entity-list-page>

  <el-dialog v-model="receiptVisible" title="完工入库" width="560px" :close-on-click-modal="false">
    <el-alert
      v-if="receiptError"
      type="error"
      :closable="false"
      show-icon
      :title="receiptError"
      class="ys-form-error"
    />
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="按「合格数量」生成并过账一张入库单据；重复提交不会重复入库。"
    />
    <el-form :model="receiptForm" label-width="120px" class="ys-mt-4">
      <el-form-item label="入库储位">
        <el-select v-model="receiptForm.location_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in receiptLocationOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="批次号">
        <el-input v-model="receiptForm.batch_no" placeholder="留空时用工单号作为批次" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="receiptVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitReceipt">确认入库</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { productionOrderApi } from '@/api/endpoints'
import {
  companyOptions,
  employeeOptions,
  factoryOptions,
  lineOptions,
  locationOptions as loadLocationOptions,
  materialOptions,
  skuOptions,
  styleOptions,
  warehouseOptions,
  workshopOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'
import { formatDecimal } from '@/utils/decimal'

const auth = useAuthStore()
const meta = useMetaStore()
const api = productionOrderApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canRelease = computed(() => auth.hasPermission('mes.order.release'))
const canIssue = computed(() => auth.hasPermission('mes.order.issue'))
const canComplete = computed(() => auth.hasPermission('mes.order.complete'))
const canClose = computed(() => auth.hasPermission('mes.order.close'))
const canCancel = computed(() => auth.hasPermission('mes.order.cancel'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'completed') return 'success'
  if (status === 'in_progress') return 'primary'
  if (status === 'released') return 'warning'
  if (status === 'cancelled') return 'info'
  if (status === 'closed') return 'info'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'order_no', label: '工单号', width: 160, sortable: true },
  { prop: 'style_name', label: '款式', minWidth: 140 },
  { prop: 'sku_name', label: 'SKU', width: 150 },
  { prop: 'quantity', label: '计划数量', width: 120 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'progress_rate', label: '进度', width: 90 },
  { prop: 'workshop_name', label: '车间', width: 120 },
  { prop: 'planned_end', label: '计划完工', width: 170, sortable: true },
  { prop: 'issue_document_no', label: '领料单', width: 150 },
  { prop: 'receipt_document_no', label: '入库单', width: 150 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'status',
    label: '工单状态',
    type: 'select' as const,
    options: meta.options('production_order_statuses'),
  },
  {
    prop: 'source_type',
    label: '来源',
    type: 'select' as const,
    options: meta.options('production_source_types'),
  },
  { prop: 'style_id', label: '款式', type: 'select' as const, optionsLoader: styleOptions },
  { prop: 'workshop_id', label: '车间', type: 'select' as const, optionsLoader: workshopOptions },
  {
    prop: 'production_line_id',
    label: '线体',
    type: 'select' as const,
    optionsLoader: lineOptions,
  },
])

const detailFields = [
  { prop: 'source_type_display', label: '来源类型' },
  { prop: 'source_no', label: '来源单号' },
  { prop: 'factory_name', label: '工厂' },
  { prop: 'production_line_name', label: '线体' },
  { prop: 'material_warehouse_name', label: '领料仓库' },
  { prop: 'receipt_warehouse_name', label: '完工入库仓库' },
  { prop: 'owner_name', label: '责任人' },
  { prop: 'planned_start', label: '计划开工' },
  { prop: 'actual_start', label: '实际开工' },
  { prop: 'actual_end', label: '实际完工' },
  { prop: 'completed_quantity', label: '完工数量' },
  { prop: 'qualified_quantity', label: '合格数量' },
  { prop: 'scrap_quantity', label: '报废数量' },
  { prop: 'released_at', label: '下达时间' },
  { prop: 'closed_at', label: '关闭时间' },
  { prop: 'cancel_reason', label: '取消原因' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'company_id',
    label: '所属公司',
    type: 'select',
    required: true,
    optionsLoader: companyOptions,
  },
  {
    prop: 'order_no',
    label: '工单号',
    help: '留空时由系统按编号规则自动生成；已保存的工单号不能改空',
    onlyOnUpdate: true,
  },
  {
    prop: 'source_type',
    label: '来源类型',
    type: 'select',
    options: meta.options('production_source_types'),
    defaultValue: 'manual',
  },
  { prop: 'source_no', label: '来源单号', help: '例如销售订单号或 MRP 建议行号' },
  { prop: 'style_id', label: '款式', type: 'select', required: true, optionsLoader: styleOptions },
  { prop: 'sku_id', label: '差异 SKU', type: 'select', optionsLoader: skuOptions },
  {
    prop: 'product_material_id',
    label: '产出物料',
    type: 'select',
    optionsLoader: materialOptions,
    help: '完工入库与质检单使用的成品 / 半成品',
  },
  { prop: 'quantity', label: '计划数量', type: 'decimal', required: true },
  { prop: 'unit', label: '单位' },
  { prop: 'factory_id', label: '工厂', type: 'select', optionsLoader: factoryOptions },
  { prop: 'workshop_id', label: '车间', type: 'select', optionsLoader: workshopOptions },
  { prop: 'production_line_id', label: '线体', type: 'select', optionsLoader: lineOptions },
  {
    prop: 'material_warehouse_id',
    label: '领料仓库',
    type: 'select',
    optionsLoader: warehouseOptions,
    help: '领料时必须指定，否则领料会被拒绝',
  },
  {
    prop: 'receipt_warehouse_id',
    label: '完工入库仓库',
    type: 'select',
    optionsLoader: warehouseOptions,
  },
  { prop: 'owner_id', label: '责任人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'planned_start', label: '计划开工', type: 'datetime' },
  {
    prop: 'planned_end',
    label: '计划完工',
    type: 'datetime',
    help: '在制供给按此日期计入 MRP 分段',
  },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const receiptLocationOptions = ref<EnumOption[]>([])
onMounted(async () => {
  receiptLocationOptions.value = await loadLocationOptions().catch(() => [])
})

const submitting = ref(false)
const receiptVisible = ref(false)
const receiptError = ref('')
const receiptTarget = ref<Record<string, unknown> | null>(null)
const receiptForm = reactive<Record<string, unknown>>({ location_id: null, batch_no: '' })

async function releaseOrder(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '下达后会冻结当前的工艺路线与 BOM 快照，并生成工序与用料行，之后不能再改用料。确认下达？',
    '下达确认',
    { type: 'warning', confirmButtonText: '确认下达', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await productionOrderApi.action(Number(row.id), 'release')
    ElMessage.success('工单已下达')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function issueMaterials(
  row: Record<string, unknown>,
  reload: () => Promise<void>,
): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '按工单用料的未领数量整单领料，并生成、过账一张出库单据。确认领料？',
    '领料确认',
    { type: 'warning', confirmButtonText: '确认领料', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await productionOrderApi.action(Number(row.id), 'issue-materials', {})
    ElMessage.success('领料完成，出库单据已过账')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function completeOrder(
  row: Record<string, unknown>,
  reload: () => Promise<void>,
): Promise<void> {
  try {
    await productionOrderApi.action(Number(row.id), 'complete', {})
    ElMessage.success('工单已完工')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

function openReceipt(row: Record<string, unknown>): void {
  receiptTarget.value = row
  receiptError.value = ''
  receiptForm.location_id = null
  receiptForm.batch_no = ''
  receiptVisible.value = true
}

async function submitReceipt(): Promise<void> {
  const target = receiptTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  receiptError.value = ''
  try {
    await productionOrderApi.action(Number(target.id), 'receipt', {
      location_id: receiptForm.location_id || null,
      batch_no: receiptForm.batch_no || '',
    })
    ElMessage.success('完工入库完成，入库单据已过账')
    receiptVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    receiptError.value = error instanceof ApiError ? error.message : '入库失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function closeOrder(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '关闭后工单视为业务终结，不再计入在制供给。确认关闭？',
    '关闭确认',
    { type: 'warning', confirmButtonText: '确认关闭', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await productionOrderApi.action(Number(row.id), 'close', {})
    ElMessage.success('工单已关闭')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

async function cancelOrder(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const result = await ElMessageBox.prompt('取消工单必须填写原因。', '取消工单', {
    confirmButtonText: '确认取消',
    cancelButtonText: '再想想',
    inputValidator: (value: string) => (value && value.trim() ? true : '请填写取消原因'),
  }).catch(() => null)
  if (!result) {
    return
  }
  try {
    await productionOrderApi.action(Number(row.id), 'cancel', { reason: result.value })
    ElMessage.success('工单已取消')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>
