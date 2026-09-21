<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="销售订单"
      entity-label="销售订单"
      description="销售订单流程：草稿 → 提交审批 → 批准 → 占用库存 → 发货出库。占用只减少可用量，不改变实存量；发货必须由本订单的占用覆盖，没有占用不允许出库。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :detail-fields="detailFields"
      readonly
      default-ordering="-id"
      search-placeholder="搜索订单号或客户名称"
      empty-text="暂无销售订单"
      :page-size="20"
      :action-width="330"
    >
      <template #toolbar>
        <el-button
          v-if="can('sales.order.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增销售订单
        </el-button>
      </template>

      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('sales_order_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-priority="{ row }">
        {{ meta.label('sales_order_priorities', String(row.priority)) }}
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('sales.order.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('sales.order.submit') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="submitOrder(row)"
        >
          提交审批
        </el-button>
        <el-button
          v-if="can('sales.order.reserve') && reservable(String(row.status))"
          link
          type="warning"
          size="small"
          @click="reserveStock(row)"
        >
          库存占用
        </el-button>
        <el-button
          v-if="can('sales.order.release') && reservable(String(row.status))"
          link
          type="info"
          size="small"
          @click="releaseStock(row)"
        >
          释放占用
        </el-button>
        <el-button
          v-if="can('sales.order.close') && closable(String(row.status))"
          link
          type="info"
          size="small"
          @click="closeOrder(row)"
        >
          关闭
        </el-button>
        <el-button
          v-if="can('sales.order.update') && cancellable(String(row.status))"
          link
          type="danger"
          size="small"
          @click="cancelOrder(row)"
        >
          取消
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer v-model="detailVisible" :title="`销售订单 ${detailRow?.order_no ?? ''}`" size="720px">
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="客户">{{ detailRow.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="下单日期">{{ detailRow.order_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="要求交期">{{ detailRow.expected_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ detailRow.priority_display }}</el-descriptions-item>
        <el-descriptions-item label="发货仓库">{{ detailRow.warehouse_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="价税合计">{{ formatAmount(detailRow.amount_with_tax) }}</el-descriptions-item>
        <el-descriptions-item label="业务员">{{ detailRow.salesman_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货地址" :span="2">
          {{ detailRow.delivery_address || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="发货出库单据">
          {{ chain?.shipments?.[0]?.issue_document_id ?? '未发货' }}
        </el-descriptions-item>
        <el-descriptions-item label="审批单号">
          {{ detailRow.approval_instance_id ?? '未提交审批' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider content-position="left">订单明细与交付进度</el-divider>
      <el-table :data="(chain?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="物料" min-width="180">
          <template #default="{ row: line }">
            {{ line.material_code }} {{ line.material_name }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="订单数量" width="110" :formatter="numberFormatter" />
        <el-table-column prop="shipped_quantity" label="已发货" width="100" />
        <el-table-column prop="returned_quantity" label="已退货" width="100" />
        <el-table-column prop="remaining_quantity" label="未发货" width="100" :formatter="numberFormatter" />
      </el-table>

      <el-divider content-position="left">关联单据（订单到交付链路）</el-divider>
      <el-table :data="(chain?.shipments ?? []) as never[]" border size="small">
        <el-table-column prop="shipment_no" label="发货单号" min-width="160" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="shipped_at" label="发货时间" min-width="160" />
        <el-table-column prop="issue_document_id" label="出库库存单据" width="130" />
      </el-table>
      <el-table
        v-if="(chain?.returns ?? []).length > 0"
        :data="(chain?.returns ?? []) as never[]"
        border
        size="small"
        style="margin-top: 8px"
      >
        <el-table-column prop="return_no" label="退货单号" min-width="160" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="inspection_result" label="检验结论" width="120" />
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增销售订单' : '编辑销售订单'"
      width="1000px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert
        v-if="formError"
        type="error"
        :closable="false"
        show-icon
        :title="formError"
        class="ys-form-error"
      />
      <el-form label-width="110px">
        <el-row :gutter="16">
          <el-col :span="9">
            <el-form-item label="客户" required>
              <el-select
                v-model="form.customer_id"
                filterable
                :disabled="editingId !== null"
                placeholder="选择客户"
                style="width: 100%"
              >
                <el-option
                  v-for="item in customerChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="发货仓库">
              <el-select v-model="form.warehouse_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in warehouseChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="7">
            <el-form-item label="优先级">
              <el-select v-model="form.priority" style="width: 100%">
                <el-option
                  v-for="item in meta.options('sales_order_priorities')"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="下单日期">
              <el-date-picker
                v-model="form.order_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="要求交期">
              <el-date-picker
                v-model="form.expected_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="税率(%)">
              <el-input v-model="form.tax_rate" placeholder="0" />
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="收货地址">
              <el-input v-model="form.delivery_address" maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="结算方式">
              <el-input v-model="form.payment_terms" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">
          订单明细（金额由系统自动计算：行金额 = 数量 × 未税单价）
        </el-divider>
        <el-table :data="form.lines" border size="small">
          <el-table-column label="物料" min-width="220">
            <template #default="{ row }">
              <el-select v-model="row.material_id" filterable placeholder="选择物料" style="width: 100%">
                <el-option
                  v-for="item in materialChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="140">
            <template #default="{ row }">
              <el-input v-model="row.quantity" placeholder="0.00" />
            </template>
          </el-table-column>
          <el-table-column label="未税单价" width="130">
            <template #default="{ row }">
              <el-input v-model="row.price" placeholder="0.00" />
            </template>
          </el-table-column>
          <el-table-column label="行交期" width="150">
            <template #default="{ row }">
              <el-date-picker
                v-model="row.expected_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="form.lines.splice($index, 1)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button link type="primary" :icon="Plus" style="margin-top: 8px" @click="addLine">
          添加明细行
        </el-button>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { salesOrderApi } from '@/api/endpoints'
import { salesOrderActionApi } from '@/api/modules'
import { customerOptions, materialOptions, warehouseOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, SalesOrder, SalesOrderChain, SalesOrderInput } from '@/types/models'
import {
  DECIMAL_PLACES,
  formatAmount,
  numberFormatter,
  toApiString,
  toEditableText,
} from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = salesOrderApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'order_no', label: '订单号', width: 165, sortable: true },
  { prop: 'customer_name', label: '客户', minWidth: 160 },
  { prop: 'status', label: '状态', width: 120 },
  { prop: 'priority', label: '优先级', width: 90 },
  { prop: 'order_date', label: '下单日期', width: 120 },
  { prop: 'expected_date', label: '要求交期', width: 120 },
  { prop: 'amount_with_tax', label: '价税合计', width: 130 },
  { prop: 'line_count', label: '明细行', width: 85 },
]

const filters = [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('sales_order_statuses'),
  },
  {
    prop: 'priority',
    label: '优先级',
    type: 'select' as const,
    options: meta.options('sales_order_priorities'),
  },
  {
    prop: 'customer_id',
    label: '客户',
    type: 'select' as const,
    optionsLoader: customerOptions,
  },
]

const detailFields = [{ prop: 'remark', label: '备注' }]

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'shipped' || status === 'approved') return 'success'
  if (status === 'partially_shipped' || status === 'submitted') return 'warning'
  if (status === 'cancelled' || status === 'rejected') return 'danger'
  return 'info'
}

function reservable(status: string): boolean {
  return status === 'approved' || status === 'partially_shipped'
}

function closable(status: string): boolean {
  return ['approved', 'partially_shipped', 'shipped'].includes(status)
}

function cancellable(status: string): boolean {
  return ['draft', 'submitted', 'approved'].includes(status)
}

// --- 下拉选项 ---------------------------------------------------------------
const customerChoices = ref<EnumOption[]>([])
const warehouseChoices = ref<EnumOption[]>([])
const materialChoices = ref<EnumOption[]>([])

async function loadChoices(): Promise<void> {
  try {
    const [customers, warehouses, materials] = await Promise.all([
      customerOptions(),
      warehouseOptions(),
      materialOptions(),
    ])
    customerChoices.value = customers
    warehouseChoices.value = warehouses
    materialChoices.value = materials
  } catch (error) {
    ElMessage.error(toMessage(error, '加载下拉选项失败'))
  }
}

// --- 列表 -------------------------------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)

function reloadList(): void {
  void pageRef.value?.reload()
}

// --- 新增 / 编辑 -------------------------------------------------------------
interface OrderLineForm {
  material_id: number | null
  quantity: string
  price: string
  expected_date: string | null
}

const formVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const editingId = ref<number | null>(null)
const editingVersion = ref<number | null>(null)
const form = reactive({
  customer_id: null as number | null,
  warehouse_id: null as number | null,
  priority: 'normal',
  order_date: null as string | null,
  expected_date: null as string | null,
  tax_rate: '0',
  payment_terms: '',
  delivery_address: '',
  remark: '',
  lines: [] as OrderLineForm[],
})

function addLine(): void {
  form.lines.push({ material_id: null, quantity: '', price: '', expected_date: null })
}

function resetForm(): void {
  form.customer_id = null
  form.warehouse_id = null
  form.priority = 'normal'
  form.order_date = null
  form.expected_date = null
  form.tax_rate = '0'
  form.payment_terms = ''
  form.delivery_address = ''
  form.remark = ''
  form.lines = []
  addLine()
}

function openCreate(): void {
  formError.value = ''
  editingId.value = null
  editingVersion.value = null
  resetForm()
  formVisible.value = true
}

function openEdit(row: SalesOrder | Record<string, unknown>): void {
  const order = row as SalesOrder
  formError.value = ''
  editingId.value = order.id
  editingVersion.value = order.version ?? null
  form.customer_id = order.customer_id
  form.warehouse_id = order.warehouse_id
  form.priority = order.priority || 'normal'
  form.order_date = order.order_date
  form.expected_date = order.expected_date
  form.tax_rate = toEditableText(order.tax_rate ?? '0')
  form.payment_terms = order.payment_terms ?? ''
  form.delivery_address = order.delivery_address ?? ''
  form.remark = order.remark ?? ''
  form.lines = (order.lines ?? []).map((line) => ({
    material_id: line.material_id,
    quantity: toEditableText(line.quantity),
    price: toEditableText(line.price),
    expected_date: line.expected_date,
  }))
  if (form.lines.length === 0) {
    addLine()
  }
  formVisible.value = true
}

function buildPayload(): SalesOrderInput {
  const lines = form.lines
    .filter((line) => line.material_id !== null)
    .map((line) => ({
      material_id: Number(line.material_id),
      quantity: toApiString(line.quantity),
      price: toApiString(line.price, 6),
      expected_date: line.expected_date || null,
    }))
  return {
    customer_id: Number(form.customer_id),
    warehouse_id: form.warehouse_id === null ? null : Number(form.warehouse_id),
    priority: form.priority,
    order_date: form.order_date || null,
    expected_date: form.expected_date || null,
    tax_rate: toApiString(form.tax_rate, DECIMAL_PLACES.rate),
    payment_terms: form.payment_terms,
    delivery_address: form.delivery_address,
    remark: form.remark,
    lines,
  }
}

async function submitForm(): Promise<void> {
  formError.value = ''
  if (!form.customer_id) {
    formError.value = '请选择客户。'
    return
  }
  const payload = buildPayload()
  if (payload.lines.length === 0) {
    formError.value = '请至少填写一行订单明细。'
    return
  }
  submitting.value = true
  try {
    if (editingId.value === null) {
      await salesOrderApi.create(payload)
      ElMessage.success('已保存草稿（审批前不影响库存）')
    } else {
      await salesOrderApi.update(editingId.value, {
        ...payload,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('已保存')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存销售订单失败')
  } finally {
    submitting.value = false
  }
}

// --- 动作 -------------------------------------------------------------------
async function submitOrder(row: Record<string, unknown>): Promise<void> {
  try {
    await salesOrderActionApi.submit(Number(row.id))
    ElMessage.success('已提交审批')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '提交失败'))
  }
}

async function reserveStock(row: Record<string, unknown>): Promise<void> {
  try {
    const result = await salesOrderActionApi.reserve(Number(row.id), '界面手动占用')
    ElMessage.success(`已占用 ${result.reserved?.length ?? 0} 行库存`)
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '库存占用失败'))
  }
}

async function releaseStock(row: Record<string, unknown>): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('释放后可用量立即恢复。', `释放 ${row.order_no} 占用`, {
      inputPlaceholder: '请填写释放原因（必填）',
      inputValidator: (value) => (value ? true : '必须填写原因'),
    })
    reason = result.value
  } catch {
    return
  }
  try {
    const result = await salesOrderActionApi.release(Number(row.id), reason)
    ElMessage.success(`已释放 ${result.released_count} 条占用`)
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '释放占用失败'))
  }
}

async function closeOrder(row: Record<string, unknown>): Promise<void> {
  try {
    await salesOrderActionApi.close(Number(row.id), '界面手动关闭')
    ElMessage.success('已关闭')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '关闭失败'))
  }
}

async function cancelOrder(row: Record<string, unknown>): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '取消后会释放未消耗的占用；已发货的订单不能取消。',
      `取消 ${row.order_no}`,
      {
        inputPlaceholder: '请填写取消原因（必填）',
        inputValidator: (value) => (value ? true : '必须填写原因'),
      },
    )
    reason = result.value
  } catch {
    return
  }
  try {
    await salesOrderActionApi.cancel(Number(row.id), reason)
    ElMessage.success('已取消')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '取消失败'))
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<SalesOrder | null>(null)
const chain = ref<SalesOrderChain | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as SalesOrder
  chain.value = null
  detailVisible.value = true
  try {
    detailRow.value = (await salesOrderApi.retrieve(Number(row.id))) as SalesOrder
    chain.value = await salesOrderActionApi.chain(Number(row.id))
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>
