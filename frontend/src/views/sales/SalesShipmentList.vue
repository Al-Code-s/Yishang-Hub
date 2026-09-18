<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="销售发货"
      entity-label="发货单"
      description="销售发货：草稿 → 发货过账（出库）。过账调用统一库存服务扣减实存量，且必须由「本订单的库存占用」覆盖，未占用不允许出库；重复点击按幂等键只扣一次。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :detail-fields="detailFields"
      readonly
      default-ordering="-id"
      search-placeholder="搜索发货单号、订单号或运单号"
      empty-text="暂无发货单"
      :page-size="20"
      :action-width="270"
    >
      <template #toolbar>
        <el-button
          v-if="can('sales.shipment.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增发货单
        </el-button>
      </template>

      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('shipment_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('sales.shipment.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('sales.shipment.post') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="postShipment(row)"
        >
          发货过账
        </el-button>
        <el-button
          v-if="can('sales.shipment.update') && row.status === 'draft'"
          link
          type="danger"
          size="small"
          @click="cancelShipment(row)"
        >
          取消
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer v-model="detailVisible" :title="`发货单 ${detailRow?.shipment_no ?? ''}`" size="680px">
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="销售订单">{{ detailRow.order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ detailRow.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="发货仓库">{{ detailRow.warehouse_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货人">{{ detailRow.receiver_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货电话">{{ detailRow.receiver_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="承运商">{{ detailRow.carrier || '-' }}</el-descriptions-item>
        <el-descriptions-item label="运单号">{{ detailRow.tracking_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发货时间">{{ detailRow.shipped_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发货人">{{ detailRow.shipped_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="出库库存单据">
          {{ detailRow.issue_document_id ?? '未过账' }}
        </el-descriptions-item>
        <el-descriptions-item label="版本">v{{ detailRow.version }}</el-descriptions-item>
        <el-descriptions-item label="收货地址" :span="2">
          {{ detailRow.delivery_address || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">发货明细</el-divider>
      <el-table :data="(detailRow?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="物料" min-width="180">
          <template #default="{ row: line }">
            {{ line.material_code }} {{ line.material_name }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="发货数量" width="120" />
        <el-table-column prop="location_name" label="储位" min-width="120" />
        <el-table-column prop="batch_no" label="批次" width="110" />
        <el-table-column prop="roll_no" label="卷号" width="110" />
      </el-table>
    </el-drawer>    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增发货单' : '编辑发货单'"
      width="920px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
        title="发货过账必须由本订单的库存占用覆盖：请先在「销售订单」上执行「库存占用」，未占用不允许出库。"
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
                placeholder="选择已批准或部分发货的订单"
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
            <el-form-item label="发货仓库" required>
              <el-select v-model="form.warehouse_id" style="width: 100%" placeholder="选择发货仓库">
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
            <el-form-item label="收货人">
              <el-input v-model="form.receiver_name" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="收货电话">
              <el-input v-model="form.receiver_phone" maxlength="32" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="承运商">
              <el-input v-model="form.carrier" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="运单号">
              <el-input v-model="form.tracking_no" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="收货地址">
              <el-input v-model="form.delivery_address" maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-divider content-position="left">发货明细（数量由后端校验，不得超过未发货数量）</el-divider>
      <el-table :data="form.lines as never[]" border size="small">
        <el-table-column prop="material_code" label="物料编码" width="130" />
        <el-table-column prop="material_name" label="物料名称" min-width="150" />
        <el-table-column prop="remaining_quantity" label="未发货" width="100" />
        <el-table-column label="本次发货" width="140">
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
  </div>
</template><script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { locationApi, salesOrderApi, salesShipmentApi } from '@/api/endpoints'
import { salesShipmentActionApi } from '@/api/modules'
import { warehouseOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, SalesOrder, SalesOrderLine, SalesShipment, ShipmentInput } from '@/types/models'
import { toApiString } from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = salesShipmentApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'shipment_no', label: '发货单号', width: 160, sortable: true },
  { prop: 'order_no', label: '销售订单', width: 160 },
  { prop: 'customer_name', label: '客户', minWidth: 150 },
  { prop: 'status', label: '状态', width: 110 },
  { prop: 'warehouse_name', label: '发货仓库', width: 130 },
  { prop: 'receiver_name', label: '收货人', width: 110 },
  { prop: 'shipped_at', label: '发货时间', width: 165 },
  { prop: 'line_count', label: '明细行', width: 85 },
]

const filters = [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('shipment_statuses'),
  },
]

const detailFields = [{ prop: 'remark', label: '备注' }]

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'posted') return 'success'
  if (status === 'cancelled') return 'danger'
  return 'info'
}

// --- 下拉选项 ---------------------------------------------------------------
const warehouseChoices = ref<EnumOption[]>([])
const locationChoices = ref<EnumOption[]>([])
const orderChoices = ref<EnumOption[]>([])
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

/** 只有「已批准 / 部分发货」的订单可以发货，界面不展示不可发货的订单。 */
async function loadOrders(): Promise<void> {
  try {
    const page = await salesOrderApi.list({ page_size: 200, ordering: '-id' })
    orders.value = (page.results as SalesOrder[]).filter((order) =>
      ['approved', 'partially_shipped'].includes(order.status),
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
interface ShipmentLineDraft {
  order_line_id: number
  material_code: string
  material_name: string
  remaining_quantity: string
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
  warehouse_id: null as number | null,
  receiver_name: '',
  receiver_phone: '',
  delivery_address: '',
  carrier: '',
  tracking_no: '',
  remark: '',
  lines: [] as ShipmentLineDraft[],
})

function openCreate(): void {
  editingId.value = null
  editingVersion.value = null
  form.sales_order_id = null
  form.warehouse_id = null
  form.receiver_name = ''
  form.receiver_phone = ''
  form.delivery_address = ''
  form.carrier = ''
  form.tracking_no = ''
  form.remark = ''
  form.lines = []
  formError.value = ''
  formVisible.value = true
  void loadOrders()
}

function lineDraftFromOrderLine(line: SalesOrderLine): ShipmentLineDraft {
  return {
    order_line_id: line.id,
    material_code: line.material_code,
    material_name: line.material_name,
    remaining_quantity: String(line.remaining_quantity),
    quantity: String(line.remaining_quantity),
    location_id: null,
    batch_no: '',
    roll_no: '',
  }
}

async function onOrderChange(orderId: number): Promise<void> {
  form.lines = []
  const order = orders.value.find((item) => item.id === orderId)
  if (order) {
    form.warehouse_id = order.warehouse_id ?? form.warehouse_id
    form.delivery_address = order.delivery_address || form.delivery_address
  }
  try {
    const detail = (await salesOrderApi.retrieve(orderId)) as SalesOrder
    form.lines = (detail.lines ?? [])
      .filter((line) => Number(line.remaining_quantity) > 0)
      .map(lineDraftFromOrderLine)
  } catch (error) {
    formError.value = toMessage(error, '加载订单明细失败')
  }
}

function openEdit(row: SalesShipment): void {
  editingId.value = row.id
  editingVersion.value = row.version
  form.sales_order_id = row.sales_order_id
  form.warehouse_id = row.warehouse_id
  form.receiver_name = row.receiver_name
  form.receiver_phone = row.receiver_phone
  form.delivery_address = row.delivery_address
  form.carrier = row.carrier
  form.tracking_no = row.tracking_no
  form.remark = row.remark
  form.lines = (row.lines ?? []).map((line) => ({
    order_line_id: line.order_line_id,
    material_code: line.material_code,
    material_name: line.material_name,
    remaining_quantity: '-',
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
    formError.value = '请选择发货仓库'
    return
  }
  const lines: ShipmentInput['lines'] = []
  for (const [index, line] of form.lines.entries()) {
    if (!line.quantity.trim()) {
      formError.value = `第 ${index + 1} 行未填写发货数量`
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
    const payload: ShipmentInput = {
      sales_order_id: form.sales_order_id,
      warehouse_id: form.warehouse_id,
      receiver_name: form.receiver_name,
      receiver_phone: form.receiver_phone,
      delivery_address: form.delivery_address,
      carrier: form.carrier,
      tracking_no: form.tracking_no,
      remark: form.remark,
      lines,
    }
    if (editingId.value === null) {
      const created = await salesShipmentApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.shipment_no}，过账前库存不变`)
    } else {
      await salesShipmentApi.update(editingId.value, {
        ...payload,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存发货单失败')
  } finally {
    submitting.value = false
  }
}

// --- 过账 / 取消 ------------------------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)

function reloadList(): void {
  void pageRef.value?.reload()
}

async function postShipment(row: SalesShipment): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '过账会扣减实存量，且必须由本订单的库存占用覆盖；未占用会被后端拒绝。确认过账？',
      `发货过账 ${row.shipment_no}`,
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    // 幂等键按单据+版本生成：网络重试不会重复扣减库存
    const key = `sales-shipment-post-${row.id}-${row.version}`
    await salesShipmentActionApi.postShipment(row.id, key)
    ElMessage.success('已过账，库存已出库')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '发货过账失败'))
  }
}

async function cancelShipment(row: SalesShipment): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('已过账的发货单不能取消。', `取消 ${row.shipment_no}`, {
      inputPlaceholder: '请填写取消原因（必填）',
      inputValidator: (value) => (value ? true : '必须填写原因'),
    })
    reason = result.value
  } catch {
    return
  }
  try {
    await salesShipmentActionApi.cancel(row.id, reason)
    ElMessage.success('已取消')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '取消失败'))
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<SalesShipment | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as SalesShipment
  detailVisible.value = true
  try {
    detailRow.value = (await salesShipmentApi.retrieve(Number(row.id))) as SalesShipment
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>