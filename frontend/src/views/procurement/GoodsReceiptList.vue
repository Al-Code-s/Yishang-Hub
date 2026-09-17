<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="到货收货"
      entity-label="收货单"
      description="实物到货、库存记账与质量放行是三个不同动作：收货过账把实物计入「待检」库存，来料检验判定后待检库存才会转为合格或不合格。待检与不合格库存不能领用或销售。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :detail-fields="detailFields"
      readonly
      default-ordering="-id"
      search-placeholder="搜索收货单号、订单号或送货单号"
      empty-text="暂无收货单"
      :page-size="20"
      :action-width="300"
    >
      <template #toolbar>
        <el-button
          v-if="can('procurement.receipt.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增收货单
        </el-button>
      </template>

      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('receipt_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-inspection_result="{ row }">
        <el-tag
          v-if="row.inspection_result && row.inspection_result !== 'none'"
          :type="row.inspection_result === 'qualified' ? 'success' : 'danger'"
          size="small"
          effect="light"
        >
          {{ row.inspection_result_display || meta.label('inspection_results', String(row.inspection_result)) }}
        </el-tag>
        <span v-else>未检验</span>
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('procurement.receipt.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('procurement.receipt.post') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="postReceipt(row)"
        >
          收货过账
        </el-button>
        <el-button
          v-if="can('procurement.receipt.inspect') && row.status === 'posted'"
          link
          type="warning"
          size="small"
          @click="openInspect(row)"
        >
          来料检验
        </el-button>
        <el-button
          v-if="can('procurement.receipt.update') && row.status === 'draft'"
          link
          type="danger"
          size="small"
          @click="cancelReceipt(row)"
        >
          取消
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer v-model="detailVisible" :title="`收货单 ${detailRow?.receipt_no ?? ''}`" size="640px">
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="采购订单">{{ detailRow.order_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ detailRow.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="收货仓库">{{ detailRow.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="送货单号">{{ detailRow.supplier_delivery_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货时间">{{ detailRow.received_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="检验结论">
          {{ detailRow.inspection_result_display || '未检验' }}
        </el-descriptions-item>
        <el-descriptions-item label="检验人">{{ detailRow.inspected_by_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="检验说明" :span="2">
          {{ detailRow.inspection_remark || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="入库库存单据">
          {{ detailRow.receipt_document_id ?? '未过账' }}
        </el-descriptions-item>
        <el-descriptions-item label="质量转换单据">
          {{ detailRow.quality_document_id ?? '未检验' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">收货明细</el-divider>
      <el-table :data="(detailRow?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="物料" min-width="170">
          <template #default="{ row: line }">{{ line.material_code }} {{ line.material_name }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="收货数量" width="110" />
        <el-table-column prop="batch_no" label="批次" width="110" />
        <el-table-column prop="roll_no" label="卷号" width="100" />
        <el-table-column prop="location_name" label="储位" width="110" />
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增收货单' : '编辑收货单'"
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
          <el-col :span="10">
            <el-form-item label="采购订单" required>
              <el-select
                v-model="form.purchase_order_id"
                filterable
                :disabled="editingId !== null"
                placeholder="选择已批准且未收完的订单"
                style="width: 100%"
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
          <el-col :span="7">
            <el-form-item label="收货仓库" required>
              <el-select v-model="form.warehouse_id" filterable style="width: 100%">
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
            <el-form-item label="送货单号">
              <el-input v-model="form.supplier_delivery_no" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">
          收货明细（数量不得超过订单行未收数量；多张草稿收货单会合并占用额度）
        </el-divider>
        <el-table :data="form.lines" border size="small">
          <el-table-column label="订单行" min-width="200">
            <template #default="{ row }">
              {{ row.material_code }} {{ row.material_name }}
              <span class="ys-line-hint">（未收 {{ row.remaining_quantity }}）</span>
            </template>
          </el-table-column>
          <el-table-column label="收货数量" width="140">
            <template #default="{ row }">
              <el-input v-model="row.quantity" placeholder="0.000000" />
            </template>
          </el-table-column>
          <el-table-column label="储位" width="170">
            <template #default="{ row }">
              <el-select v-model="row.location_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in locationChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="批次号" width="140">
            <template #default="{ row }">
              <el-input v-model="row.batch_no" maxlength="64" />
            </template>
          </el-table-column>
          <el-table-column label="卷号" width="120">
            <template #default="{ row }">
              <el-input v-model="row.roll_no" maxlength="64" />
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
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          保存草稿（过账前库存不变）
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="inspectVisible"
      title="来料检验判定"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert
        v-if="inspectError"
        type="error"
        :closable="false"
        show-icon
        :title="inspectError"
        class="ys-form-error"
      />
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="当前未接入真实检测设备接口，本判定为人工录入结论，系统会记录判定人与说明。"
      />
      <el-form label-width="90px" class="ys-convert-form">
        <el-form-item label="检验结论" required>
          <el-radio-group v-model="inspectForm.result">
            <el-radio value="qualified">合格放行（待检 → 合格）</el-radio>
            <el-radio value="rejected">判为不合格（待检 → 不合格）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="检验说明" required>
          <el-input v-model="inspectForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inspectVisible = false">取消</el-button>
        <el-button type="primary" :loading="inspecting" @click="submitInspect">提交判定</el-button>
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
import { goodsReceiptApi, locationApi, purchaseOrderApi } from '@/api/endpoints'
import { goodsReceiptActionApi } from '@/api/modules'
import { warehouseOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type {
  EnumOption,
  GoodsReceipt,
  GoodsReceiptInput,
  PurchaseOrder,
  PurchaseOrderLine,
} from '@/types/models'
import { toApiString } from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = goodsReceiptApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'receipt_no', label: '收货单号', width: 160, sortable: true },
  { prop: 'order_no', label: '采购订单', width: 160 },
  { prop: 'supplier_name', label: '供应商', minWidth: 150 },
  { prop: 'status', label: '状态', width: 120 },
  { prop: 'inspection_result', label: '检验结论', width: 110 },
  { prop: 'warehouse_name', label: '收货仓库', width: 130 },
  { prop: 'received_at', label: '收货时间', width: 165 },
  { prop: 'line_count', label: '明细行', width: 85 },
]

const filters = [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('receipt_statuses'),
  },
  {
    prop: 'inspection_result',
    label: '检验结论',
    type: 'select' as const,
    options: meta.options('inspection_results'),
  },
]

const detailFields = [{ prop: 'remark', label: '备注' }]

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'inspected' || status === 'posted') return 'success'
  if (status === 'cancelled') return 'danger'
  return 'info'
}

// --- 下拉选项 ---------------------------------------------------------------
const warehouseChoices = ref<EnumOption[]>([])
const locationChoices = ref<EnumOption[]>([])
const orderChoices = ref<EnumOption[]>([])
const orders = ref<PurchaseOrder[]>([])

async function loadChoices(): Promise<void> {
  const empty: EnumOption[][] = [[], [], []]
  const [warehouses, locations] = await Promise.all([
    warehouseOptions(),
    locationApi.list({ page_size: 200, is_active: true, ordering: 'code' }),
  ]).catch(() => [empty[0], { results: [] as unknown[] }] as [EnumOption[], { results: unknown[] }])
  warehouseChoices.value = warehouses
  locationChoices.value = locations.results.map((row) => {
    const record = row as { id: number; code: string; name: string }
    return { value: record.id, label: `${record.code} ${record.name}` }
  })
  await loadOrders()
}

/** 只有「已批准 / 部分到货」的订单可以收货，界面不展示不可收货的订单。 */
async function loadOrders(): Promise<void> {
  try {
    const page = await purchaseOrderApi.list({ page_size: 200, ordering: '-id' })
    orders.value = (page.results as PurchaseOrder[]).filter((order) =>
      ['approved', 'partially_received'].includes(order.status),
    )
    orderChoices.value = orders.value.map((order) => ({
      value: order.id,
      label: `${order.order_no} ${order.supplier_name}`,
    }))
  } catch {
    orders.value = []
    orderChoices.value = []
  }
}

// --- 新增 / 编辑 ------------------------------------------------------------
interface ReceiptLineDraft {
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
  purchase_order_id: null as number | null,
  warehouse_id: null as number | null,
  supplier_delivery_no: '',
  remark: '',
  lines: [] as ReceiptLineDraft[],
})

function openCreate(): void {
  editingId.value = null
  editingVersion.value = null
  form.purchase_order_id = null
  form.warehouse_id = null
  form.supplier_delivery_no = ''
  form.remark = ''
  form.lines = []
  formError.value = ''
  formVisible.value = true
  void loadOrders()
}

function lineDraftFromOrderLine(line: PurchaseOrderLine): ReceiptLineDraft {
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
  }
  try {
    const detail = (await purchaseOrderApi.retrieve(orderId)) as PurchaseOrder
    form.lines = (detail.lines ?? [])
      .filter((line) => Number(line.remaining_quantity) > 0)
      .map(lineDraftFromOrderLine)
  } catch (error) {
    formError.value = toMessage(error, '加载订单明细失败')
  }
}

function openEdit(row: GoodsReceipt): void {
  editingId.value = row.id
  editingVersion.value = row.version
  form.purchase_order_id = row.purchase_order_id
  form.warehouse_id = row.warehouse_id
  form.supplier_delivery_no = row.supplier_delivery_no
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
  if (!form.purchase_order_id) {
    formError.value = '请选择采购订单'
    return
  }
  if (!form.warehouse_id) {
    formError.value = '请选择收货仓库'
    return
  }
  const lines: GoodsReceiptInput['lines'] = []
  for (const [index, line] of form.lines.entries()) {
    if (!line.quantity.trim()) {
      formError.value = `第 ${index + 1} 行未填写收货数量`
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
    const payload: GoodsReceiptInput = {
      purchase_order_id: form.purchase_order_id,
      warehouse_id: form.warehouse_id,
      supplier_delivery_no: form.supplier_delivery_no,
      remark: form.remark,
      lines,
    }
    if (editingId.value === null) {
      const created = await goodsReceiptApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.receipt_no}，过账前库存不变`)
    } else {
      await goodsReceiptApi.update(editingId.value, {
        ...payload,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存收货单失败')
  } finally {
    submitting.value = false
  }
}

// --- 过账 / 检验 / 取消 -----------------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)

function reloadList(): void {
  void pageRef.value?.reload()
}

async function postReceipt(row: GoodsReceipt): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '过账后实物到货计入「待检」库存，此时不能领用或销售，需要检验放行。确认过账？',
      `收货过账 ${row.receipt_no}`,
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    // 幂等键按单据+版本生成：网络重试不会重复记账
    const key = `procurement-receipt-post-${row.id}-${row.version}`
    await goodsReceiptActionApi.postReceipt(row.id, key)
    ElMessage.success('已过账，库存进入待检状态')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '收货过账失败'))
  }
}

const inspectVisible = ref(false)
const inspecting = ref(false)
const inspectError = ref('')
const inspectTarget = ref<GoodsReceipt | null>(null)
const inspectForm = reactive({ result: 'qualified', remark: '' })

function openInspect(row: GoodsReceipt): void {
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
    const key = `procurement-receipt-inspect-${inspectTarget.value.id}-${inspectForm.result}`
    await goodsReceiptActionApi.inspect(
      inspectTarget.value.id,
      inspectForm.result,
      inspectForm.remark,
      key,
    )
    ElMessage.success(
      inspectForm.result === 'qualified' ? '已放行，库存转为合格' : '已判定不合格，库存不可动用',
    )
    inspectVisible.value = false
    reloadList()
  } catch (error) {
    inspectError.value = toMessage(error, '检验判定失败')
  } finally {
    inspecting.value = false
  }
}

async function cancelReceipt(row: GoodsReceipt): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('已过账的收货单不能取消。', `取消 ${row.receipt_no}`, {
      inputPlaceholder: '请填写取消原因（必填）',
      inputValidator: (value) => (value ? true : '必须填写原因'),
    })
    reason = result.value
  } catch {
    return
  }
  try {
    await goodsReceiptActionApi.cancel(row.id, reason)
    ElMessage.success('已取消')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '取消失败'))
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<GoodsReceipt | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as GoodsReceipt
  detailVisible.value = true
  try {
    detailRow.value = (await goodsReceiptApi.retrieve(Number(row.id))) as GoodsReceipt
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>