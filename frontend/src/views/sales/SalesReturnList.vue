<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="销售退货"
      entity-label="退货单"
      description="销售退货：草稿 → 收货过账（退回货物先进入「待检」库存）→ 检验判定（合格回库可再销售 / 不合格留在仓内不可动用）。退货先验收再决定质量状态，收货过账不等于可以直接再销售。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :detail-fields="detailFields"
      readonly
      default-ordering="-id"
      search-placeholder="搜索退货单号、订单号或发货单号"
      empty-text="暂无退货单"
      :page-size="20"
      :action-width="290"
    >
      <template #toolbar>
        <el-button
          v-if="can('sales.return.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增退货单
        </el-button>
      </template>

      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('return_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-inspection_result="{ row }">
        <el-tag
          v-if="row.inspection_result && row.inspection_result !== 'none'"
          :type="row.inspection_result === 'qualified' ? 'success' : 'danger'"
          size="small"
          effect="light"
        >
          {{
            row.inspection_result_display ||
            meta.label('return_dispositions', String(row.inspection_result))
          }}
        </el-tag>
        <span v-else>未判定</span>
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('sales.return.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('sales.return.post') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="postReturn(row)"
        >
          退货收货
        </el-button>
        <el-button
          v-if="can('sales.return.inspect') && row.status === 'posted'"
          link
          type="warning"
          size="small"
          @click="openInspect(row)"
        >
          检验判定
        </el-button>
        <el-button
          v-if="can('sales.return.update') && row.status === 'draft'"
          link
          type="danger"
          size="small"
          @click="cancelReturn(row)"
        >
          取消
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer v-model="detailVisible" :title="`退货单 ${detailRow?.return_no ?? ''}`" size="680px">
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="销售订单">{{ detailRow.order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ detailRow.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="退货仓库">{{ detailRow.warehouse_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联发货单">{{ detailRow.shipment_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="退货原因">{{ detailRow.reason || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货时间">{{ detailRow.received_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货人">{{ detailRow.received_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="检验结论">
          {{ detailRow.inspection_result_display || '未判定' }}
        </el-descriptions-item>
        <el-descriptions-item label="检验人">{{ detailRow.inspected_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="检验时间">{{ detailRow.inspected_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="版本">v{{ detailRow.version }}</el-descriptions-item>
        <el-descriptions-item label="入库库存单据">
          {{ detailRow.receipt_document_id ?? '未过账' }}
        </el-descriptions-item>
        <el-descriptions-item label="质量转换单据">
          {{ detailRow.quality_document_id ?? '未判定' }}
        </el-descriptions-item>
        <el-descriptions-item label="检验说明" :span="2">
          {{ detailRow.inspection_remark || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">退货明细</el-divider>
      <el-table :data="(detailRow?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="物料" min-width="180">
          <template #default="{ row: line }">
            {{ line.material_code }} {{ line.material_name }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="退货数量" width="120" />
        <el-table-column prop="batch_no" label="批次" width="110" />
        <el-table-column prop="roll_no" label="卷号" width="110" />
      </el-table>
    </el-drawer>    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增退货单' : '编辑退货单'"
      width="920px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        title="退货数量不得超过「已发货 - 已退货」；收货过账后货物进入待检库存，需要检验判定才能再销售。"
      />
      <el-form label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="销售订单" required>
              <el-select
                v-model="form.sales_order_id"
                filterable
                style="width: 100%"
                :disabled="editingId !== null"
                placeholder="选择已有发货记录的订单"
                @change="onOrderChange"
              >
                <el-option
                  v-for="item in orderChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="退货仓库" required>
              <el-select v-model="form.warehouse_id" style="width: 100%" placeholder="选择退货收货仓库">
                <el-option
                  v-for="item in warehouseChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联发货单">
              <el-select v-model="form.shipment_id" clearable style="width: 100%">
                <el-option
                  v-for="item in shipmentChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="退货原因">
              <el-input v-model="form.reason" maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-divider content-position="left">退货明细（数量由后端校验，不得超过可退货数量）</el-divider>
      <el-table :data="form.lines as never[]" border size="small">
        <el-table-column prop="material_code" label="物料编码" width="130" />
        <el-table-column prop="material_name" label="物料名称" min-width="150" />
        <el-table-column prop="returnable_quantity" label="可退货" width="100" />
        <el-table-column label="本次退货" width="140">
          <template #default="{ row: line }">
            <el-input v-model="line.quantity" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="储位" min-width="160">
          <template #default="{ row: line }">
            <el-select v-model="line.location_id" clearable size="small" style="width: 100%">
              <el-option
                v-for="item in locationChoices"
                :key="String(item.value)"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="批次" width="130">
          <template #default="{ row: line }">
            <el-input v-model="line.batch_no" size="small" maxlength="64" />
          </template>
        </el-table-column>
        <el-table-column label="卷号" width="120">
          <template #default="{ row: line }">
            <el-input v-model="line.roll_no" size="small" maxlength="64" />
          </template>
        </el-table-column>
      </el-table>

      <el-alert
        v-if="formError"
        type="error"
        :closable="false"
        show-icon
        style="margin-top: 12px"
        :title="formError"
      />
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ editingId === null ? '保存草稿' : '保存修改' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="inspectVisible" title="退货检验判定" width="520px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        title="未接入真实检测设备接口：此处为人工判定，结论与判定人一并留痕，不得作为自动检测结果。"
      />
      <el-form label-width="90px">
        <el-form-item label="判定结论" required>
          <el-radio-group v-model="inspectForm.result">
            <el-radio value="qualified">合格（待检转合格，可再销售）</el-radio>
            <el-radio value="rejected">不合格（留在仓内，不可动用）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="判定说明" required>
          <el-input v-model="inspectForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <el-alert
        v-if="inspectError"
        type="error"
        :closable="false"
        show-icon
        :title="inspectError"
      />
      <template #footer>
        <el-button @click="inspectVisible = false">取消</el-button>
        <el-button type="primary" :loading="inspecting" @click="submitInspect">提交判定</el-button>
      </template>
    </el-dialog>
  </div>
</template><script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { locationApi, salesOrderApi, salesReturnApi, salesShipmentApi } from '@/api/endpoints'
import { salesReturnActionApi } from '@/api/modules'
import { warehouseOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, ReturnInput, SalesOrder, SalesOrderLine, SalesReturn } from '@/types/models'
import { toApiString } from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = salesReturnApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'return_no', label: '退货单号', width: 160, sortable: true },
  { prop: 'order_no', label: '销售订单', width: 160 },
  { prop: 'customer_name', label: '客户', minWidth: 150 },
  { prop: 'status', label: '状态', width: 110 },
  { prop: 'inspection_result', label: '检验结论', width: 110 },
  { prop: 'warehouse_name', label: '退货仓库', width: 130 },
  { prop: 'received_at', label: '收货时间', width: 165 },
  { prop: 'line_count', label: '明细行', width: 85 },
]

const filters = [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('return_statuses'),
  },
  {
    prop: 'inspection_result',
    label: '检验结论',
    type: 'select' as const,
    options: meta.options('return_dispositions'),
  },
]

const detailFields = [{ prop: 'remark', label: '备注' }]

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'posted' || status === 'inspected') return 'success'
  if (status === 'cancelled') return 'danger'
  return 'info'
}

// --- 下拉选项 ---------------------------------------------------------------
const warehouseChoices = ref<EnumOption[]>([])
const locationChoices = ref<EnumOption[]>([])
const orderChoices = ref<EnumOption[]>([])
const shipmentChoices = ref<EnumOption[]>([])
const orders = ref<SalesOrder[]>([])

async function loadChoices(): Promise<void> {
  const [warehouses, locations] = await Promise.all([
    warehouseOptions(),
    locationApi
      .list({ page_size: 200, is_active: true, ordering: 'code' })
      .catch(() => ({ results: [] as unknown[] })),
  ]).catch(() => [[], { results: [] as unknown[] }] as [EnumOption[], { results: unknown[] }])
  warehouseChoices.value = warehouses
  locationChoices.value = locations.results.map((row) => {
    const record = row as { id: number; code: string; name: string }
    return { value: record.id, label: `${record.code} ${record.name}` }
  })
  await loadOrders()
}

/** 只有存在发货记录的订单才可能有退货，界面不展示其余订单。 */
async function loadOrders(): Promise<void> {
  try {
    const page = await salesOrderApi.list({ page_size: 200, ordering: '-id' })
    orders.value = (page.results as SalesOrder[]).filter((order) =>
      ['partially_shipped', 'shipped', 'closed'].includes(order.status),
    )
    orderChoices.value = orders.value.map((order) => ({
      value: order.id,
      label: `${order.order_no} ${order.customer_name}`,
    }))
  } catch {
    orders.value = []
    orderChoices.value = []
  }
}

// --- 新增 / 编辑 ------------------------------------------------------------
interface ReturnLineDraft {
  order_line_id: number
  material_code: string
  material_name: string
  returnable_quantity: string
  quantity: string
  location_id: number | null
  batch_no: string
  roll_no: string
}

const formVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const editingId = ref<number | null>(null)
const editingVersion = ref<number | null>(null)
const form = reactive({
  sales_order_id: null as number | null,
  shipment_id: null as number | null,
  warehouse_id: null as number | null,
  reason: '',
  remark: '',
  lines: [] as ReturnLineDraft[],
})

function openCreate(): void {
  editingId.value = null
  editingVersion.value = null
  form.sales_order_id = null
  form.shipment_id = null
  form.warehouse_id = null
  form.reason = ''
  form.remark = ''
  form.lines = []
  shipmentChoices.value = []
  formError.value = ''
  formVisible.value = true
  void loadOrders()
}

function lineDraftFromOrderLine(line: SalesOrderLine): ReturnLineDraft {
  return {
    order_line_id: line.id,
    material_code: line.material_code,
    material_name: line.material_name,
    returnable_quantity: String(line.returnable_quantity),
    quantity: String(line.returnable_quantity),
    location_id: null,
    batch_no: '',
    roll_no: '',
  }
}

async function onOrderChange(orderId: number): Promise<void> {
  form.lines = []
  form.shipment_id = null
  shipmentChoices.value = []
  const order = orders.value.find((item) => item.id === orderId)
  if (order) {
    form.warehouse_id = order.warehouse_id ?? form.warehouse_id
  }
  try {
    const detail = (await salesOrderApi.retrieve(orderId)) as SalesOrder
    form.lines = (detail.lines ?? [])
      .filter((line) => Number(line.returnable_quantity) > 0)
      .map(lineDraftFromOrderLine)
  } catch (error) {
    formError.value = toMessage(error, '加载订单明细失败')
  }
  try {
    const page = await salesShipmentApi.list({ sales_order_id: orderId, page_size: 200 })
    shipmentChoices.value = page.results
      .filter((shipment) => shipment.status === 'posted')
      .map((shipment) => ({ value: shipment.id, label: shipment.shipment_no }))
  } catch {
    shipmentChoices.value = []
  }
}

function openEdit(row: SalesReturn): void {
  editingId.value = row.id
  editingVersion.value = row.version
  form.sales_order_id = row.sales_order_id
  form.shipment_id = row.shipment_id
  form.warehouse_id = row.warehouse_id
  form.reason = row.reason
  form.remark = row.remark
  form.lines = (row.lines ?? []).map((line) => ({
    order_line_id: line.order_line_id,
    material_code: line.material_code,
    material_name: line.material_name,
    returnable_quantity: '-',
    quantity: String(line.quantity),
    location_id: line.location_id,
    batch_no: line.batch_no,
    roll_no: line.roll_no,
  }))
  formError.value = ''
  formVisible.value = true
}

async function submitForm(): Promise<void> {
  formError.value = ''
  if (!form.sales_order_id) {
    formError.value = '请选择销售订单'
    return
  }
  if (!form.warehouse_id) {
    formError.value = '请选择退货仓库'
    return
  }
  const lines: ReturnInput['lines'] = []
  for (const [index, line] of form.lines.entries()) {
    if (!line.quantity.trim()) {
      formError.value = `第 ${index + 1} 行未填写退货数量`
      return
    }
    lines.push({
      order_line_id: line.order_line_id,
      quantity: toApiString(line.quantity),
      location_id: line.location_id,
      batch_no: line.batch_no,
      roll_no: line.roll_no,
    })
  }
  if (lines.length === 0) {
    formError.value = '至少需要一行明细'
    return
  }
  submitting.value = true
  try {
    const payload: ReturnInput = {
      sales_order_id: form.sales_order_id,
      shipment_id: form.shipment_id,
      warehouse_id: form.warehouse_id,
      reason: form.reason,
      remark: form.remark,
      lines,
    }
    if (editingId.value === null) {
      const created = await salesReturnApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.return_no}，收货过账前进待检库存`)
    } else {
      await salesReturnApi.update(editingId.value, {
        shipment_id: form.shipment_id,
        warehouse_id: form.warehouse_id,
        reason: form.reason,
        remark: form.remark,
        lines,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存退货单失败')
  } finally {
    submitting.value = false
  }
}

// --- 收货过账 / 检验判定 / 取消 ---------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)

function reloadList(): void {
  void pageRef.value?.reload()
}

async function postReturn(row: SalesReturn): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '收货过账后退回货物进入「待检」库存，此时不能领用或再销售，需要检验判定放行。确认过账？',
      `退货收货 ${row.return_no}`,
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    // 幂等键按单据+版本生成：网络重试不会重复记账
    const key = `sales-return-post-${row.id}-${row.version}`
    await salesReturnActionApi.postReturn(row.id, key)
    ElMessage.success('已收货，库存进入待检状态')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '退货收货失败'))
  }
}

const inspectVisible = ref(false)
const inspecting = ref(false)
const inspectError = ref('')
const inspectTarget = ref<SalesReturn | null>(null)
const inspectForm = reactive({ result: 'qualified', remark: '' })

function openInspect(row: SalesReturn): void {
  inspectTarget.value = row
  inspectForm.result = 'qualified'
  inspectForm.remark = ''
  inspectError.value = ''
  inspectVisible.value = true
}

async function submitInspect(): Promise<void> {
  inspectError.value = ''
  if (!inspectTarget.value) {
    return
  }
  if (!inspectForm.remark.trim()) {
    inspectError.value = '检验判定必须填写说明'
    return
  }
  inspecting.value = true
  try {
    const key = `sales-return-inspect-${inspectTarget.value.id}-${inspectForm.result}`
    await salesReturnActionApi.inspect(
      inspectTarget.value.id,
      inspectForm.result,
      inspectForm.remark,
      key,
    )
    ElMessage.success(
      inspectForm.result === 'qualified' ? '已放行，待检库存转为合格' : '已判定不合格，库存不可动用',
    )
    inspectVisible.value = false
    reloadList()
  } catch (error) {
    inspectError.value = toMessage(error, '检验判定失败')
  } finally {
    inspecting.value = false
  }
}

async function cancelReturn(row: SalesReturn): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('已收货的退货单不能取消。', `取消 ${row.return_no}`, {
      inputPlaceholder: '请填写取消原因（必填）',
      inputValidator: (value) => (value ? true : '必须填写原因'),
    })
    reason = result.value
  } catch {
    return
  }
  try {
    await salesReturnActionApi.cancel(row.id, reason)
    ElMessage.success('已取消')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '取消失败'))
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<SalesReturn | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as SalesReturn
  detailVisible.value = true
  try {
    detailRow.value = (await salesReturnApi.retrieve(Number(row.id))) as SalesReturn
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>