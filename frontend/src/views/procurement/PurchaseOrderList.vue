<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="采购订单"
      entity-label="采购订单"
      description="采购订单金额由系统按明细自动计算，不需要手工填写（税率按百分比填写，0~100）。向未准入或已停用的供应商下单，必须填写例外原因并拥有相应权限，例外会记入操作日志。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :detail-fields="detailFields"
      readonly
      default-ordering="-id"
      search-placeholder="搜索订单号、供应商或备注"
      empty-text="暂无采购订单"
      :page-size="20"
      :action-width="300"
    >
      <template #toolbar>
        <el-button
          v-if="can('procurement.order.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增采购订单
        </el-button>
      </template>

      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('purchase_order_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-supplier_exception="{ row }">
        <el-tag v-if="row.supplier_exception" type="warning" size="small" effect="light">
          例外授权
        </el-tag>
        <span v-else>-</span>
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>
      <template #column-amount_with_tax="{ row }">
        {{ formatAmount(String(row.amount_with_tax)) }}
      </template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('procurement.order.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('procurement.order.submit') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="submitOrder(row)"
        >
          提交审批
        </el-button>
        <el-button
          v-if="can('procurement.order.close') && closable(String(row.status))"
          link
          type="warning"
          size="small"
          @click="closeOrder(row)"
        >
          关闭
        </el-button>
        <el-button
          v-if="can('procurement.order.update') && cancellable(String(row.status))"
          link
          type="danger"
          size="small"
          @click="cancelOrder(row)"
        >
          取消
        </el-button>
      </template>
    </entity-list-page>

    <el-drawer v-model="detailVisible" :title="`采购订单 ${detailRow?.order_no ?? ''}`" size="640px">
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="供应商">{{ detailRow.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="订单日期">{{ detailRow.order_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="期望到货">{{ detailRow.expected_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="收货仓库">{{ detailRow.warehouse_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="采购员">{{ detailRow.buyer_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="税率(%)">{{ formatAmount(detailRow.tax_rate) }}</el-descriptions-item>
        <el-descriptions-item label="结算方式">{{ detailRow.payment_terms || '-' }}</el-descriptions-item>
        <el-descriptions-item label="未税金额">
          {{ formatAmount(String(detailRow.total_amount)) }}
        </el-descriptions-item>
        <el-descriptions-item label="税额">
          {{ formatAmount(String(detailRow.tax_amount)) }}
        </el-descriptions-item>
        <el-descriptions-item label="价税合计">
          {{ formatAmount(String(detailRow.amount_with_tax)) }}
        </el-descriptions-item>
        <el-descriptions-item label="来源申请">
          {{ detailRow.source_requisition_no || '直接下单' }}
        </el-descriptions-item>
        <el-descriptions-item label="供应商例外" :span="2">
          {{ detailRow.supplier_exception ? detailRow.supplier_exception_reason : '无' }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">订单明细</el-divider>
      <el-table :data="(detailRow?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="物料" min-width="170">
          <template #default="{ row: line }">{{ line.material_code }} {{ line.material_name }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="订单量" width="100" :formatter="numberFormatter" />
        <el-table-column prop="received_quantity" label="已收" width="100" />
        <el-table-column prop="remaining_quantity" label="未收" width="100" :formatter="numberFormatter" />
        <el-table-column prop="price" label="未税单价" width="100" :formatter="numberFormatter" />
        <el-table-column prop="amount" label="金额" width="110" :formatter="numberFormatter" />
      </el-table>
      <el-alert
        class="ys-detail-hint"
        type="info"
        :closable="false"
        show-icon
        title="订单本身不产生库存变动；到货后需先过账进入待检库存，再由质检判定放行或不合格。"
      />
    </el-drawer>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增采购订单' : '编辑采购订单'"
      width="1020px"
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
          <el-col :span="8">
            <el-form-item label="供应商" required>
              <el-select v-model="form.supplier_id" filterable style="width: 100%">
                <el-option
                  v-for="item in supplierChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="收货仓库">
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
          <el-col :span="8">
            <el-form-item label="采购员">
              <el-select v-model="form.buyer_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in employeeChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="订单日期">
              <el-date-picker
                v-model="form.order_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="期望到货日">
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
              <el-input v-model="form.tax_rate" placeholder="0 ~ 100" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="币种">
              <el-input v-model="form.currency" maxlength="8" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="结算方式">
              <el-input v-model="form.payment_terms" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="例外原因">
              <el-input
                v-model="form.supplier_exception_reason"
                placeholder="供应商停用/未准入时必填"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">订单明细（金额由系统按 数量 × 未税单价 自动计算）</el-divider>
        <el-table :data="form.lines" border size="small">
          <el-table-column label="物料" min-width="200">
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
          <el-table-column label="数量" width="130">
            <template #default="{ row }">
              <el-input v-model="row.quantity" placeholder="0.00" />
            </template>
          </el-table-column>
          <el-table-column label="未税单价" width="130">
            <template #default="{ row }">
              <el-input v-model="row.price" placeholder="0.00" />
            </template>
          </el-table-column>
          <el-table-column label="计量单位" width="130">
            <template #default="{ row }">
              <el-select v-model="row.uom_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in uomChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="期望到货" width="150">
            <template #default="{ row }">
              <el-date-picker
                v-model="row.expected_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.remark" />
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
        <el-button class="ys-line-add" @click="addLine">添加明细行</el-button>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
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
import { purchaseOrderApi } from '@/api/endpoints'
import { purchaseOrderActionApi } from '@/api/modules'
import {
  employeeOptions,
  materialOptions,
  supplierOptions,
  uomOptions,
  warehouseOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, PurchaseOrder, PurchaseOrderInput } from '@/types/models'
import {
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
const api = purchaseOrderApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

/** 关闭：已批准或已到货，余量不再到货时使用。 */
function closable(status: string): boolean {
  return ['approved', 'partially_received', 'received'].includes(status)
}

/** 取消：草稿、审批中、已批准；存在未取消收货单时后端会拒绝。 */
function cancellable(status: string): boolean {
  return ['draft', 'submitted', 'approved'].includes(status)
}

const columns: ProTableColumn[] = [
  { prop: 'order_no', label: '订单号', width: 160, sortable: true },
  { prop: 'supplier_name', label: '供应商', minWidth: 160 },
  { prop: 'status', label: '状态', width: 110 },
  { prop: 'order_date', label: '订单日期', width: 115 },
  { prop: 'expected_date', label: '期望到货', width: 115 },
  { prop: 'amount_with_tax', label: '价税合计', width: 130 },
  { prop: 'supplier_exception', label: '例外', width: 100 },
  { prop: 'line_count', label: '明细行', width: 90 },
]

const filters = [
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('purchase_order_statuses'),
  },
  // 供应商 / 仓库选项在 loadChoices 中与表单共用同一份数据
  { prop: 'supplier_id', label: '供应商', type: 'select' as const, options: [] as { value: number; label: string }[] },
  { prop: 'warehouse_id', label: '收货仓库', type: 'select' as const, options: [] as { value: number; label: string }[] },
]

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'remark', label: '备注' },
]

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (['approved', 'received'].includes(status)) return 'success'
  if (['submitted', 'partially_received'].includes(status)) return 'warning'
  if (['rejected', 'cancelled'].includes(status)) return 'danger'
  return 'info'
}

// --- 下拉选项 ---------------------------------------------------------------
const materialChoices = ref<EnumOption[]>([])
const uomChoices = ref<EnumOption[]>([])
const supplierChoices = ref<EnumOption[]>([])
const warehouseChoices = ref<EnumOption[]>([])
const employeeChoices = ref<EnumOption[]>([])

async function loadChoices(): Promise<void> {
  const empty: EnumOption[][] = [[], [], [], [], []]
  const loaded = await Promise.all([
    materialOptions(),
    uomOptions(),
    supplierOptions(),
    warehouseOptions(),
    employeeOptions(),
  ]).catch(() => empty)
  materialChoices.value = loaded[0]
  uomChoices.value = loaded[1]
  supplierChoices.value = loaded[2]
  warehouseChoices.value = loaded[3]
  employeeChoices.value = loaded[4]
  // 过滤器选项与表单共用同一份数据，避免出现「能选供应商但筛不出结果」
  filters[1].options = supplierChoices.value
  filters[2].options = warehouseChoices.value
}

// --- 新增 / 编辑 ------------------------------------------------------------
interface LineDraft {
  material_id: number | null
  quantity: string
  price: string
  uom_id: number | null
  expected_date: string
  remark: string
}

const formVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const editingId = ref<number | null>(null)
const editingVersion = ref<number | null>(null)
const form = reactive({
  supplier_id: null as number | null,
  warehouse_id: null as number | null,
  buyer_id: null as number | null,
  order_date: '',
  expected_date: '',
  tax_rate: '',
  currency: 'CNY',
  payment_terms: '',
  supplier_exception_reason: '',
  remark: '',
  lines: [] as LineDraft[],
})

function emptyLine(): LineDraft {
  return { material_id: null, quantity: '', price: '', uom_id: null, expected_date: '', remark: '' }
}

function addLine(): void {
  form.lines.push(emptyLine())
}

function openCreate(): void {
  editingId.value = null
  editingVersion.value = null
  form.supplier_id = null
  form.warehouse_id = null
  form.buyer_id = null
  form.order_date = ''
  form.expected_date = ''
  form.tax_rate = ''
  form.currency = 'CNY'
  form.payment_terms = ''
  form.supplier_exception_reason = ''
  form.remark = ''
  form.lines = [emptyLine()]
  formError.value = ''
  formVisible.value = true
}

function openEdit(row: PurchaseOrder): void {
  editingId.value = row.id
  editingVersion.value = row.version
  form.supplier_id = row.supplier_id
  form.warehouse_id = row.warehouse_id
  form.buyer_id = row.buyer_id
  form.order_date = row.order_date ?? ''
  form.expected_date = row.expected_date ?? ''
  form.tax_rate = toEditableText(row.tax_rate)
  form.currency = row.currency
  form.payment_terms = row.payment_terms
  form.supplier_exception_reason = row.supplier_exception_reason
  form.remark = row.remark
  form.lines = (row.lines ?? []).map((line) => ({
    material_id: line.material_id,
    quantity: toEditableText(line.quantity),
    price: toEditableText(line.price),
    uom_id: line.uom_id,
    expected_date: line.expected_date ?? '',
    remark: line.remark,
  }))
  formError.value = ''
  formVisible.value = true
}

function buildLines(): PurchaseOrderInput['lines'] {
  const rows: PurchaseOrderInput['lines'] = []
  for (const [index, line] of form.lines.entries()) {
    if (!line.material_id) {
      throw new Error(`第 ${index + 1} 行未选择物料`)
    }
    if (!line.quantity.trim()) {
      throw new Error(`第 ${index + 1} 行未填写数量`)
    }
    rows.push({
      material_id: line.material_id,
      quantity: toApiString(line.quantity),
      price: line.price.trim() ? toApiString(line.price) : '0',
      uom_id: line.uom_id,
      expected_date: line.expected_date || null,
      remark: line.remark,
    })
  }
  if (rows.length === 0) {
    throw new Error('至少需要一行明细')
  }
  return rows
}

async function submitForm(): Promise<void> {
  formError.value = ''
  if (!form.supplier_id) {
    formError.value = '请选择供应商'
    return
  }
  let lines: PurchaseOrderInput['lines']
  try {
    lines = buildLines()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '明细不完整'
    return
  }
  submitting.value = true
  try {
    const payload: PurchaseOrderInput = {
      supplier_id: form.supplier_id,
      warehouse_id: form.warehouse_id,
      buyer_id: form.buyer_id,
      order_date: form.order_date || null,
      expected_date: form.expected_date || null,
      currency: form.currency || 'CNY',
      // 税率按百分比原样提交（后端 0~100 校验，小数位由 DecimalField 决定）
      tax_rate: form.tax_rate.trim() || '0',
      payment_terms: form.payment_terms,
      supplier_exception_reason: form.supplier_exception_reason,
      remark: form.remark,
      lines,
    }
    if (editingId.value === null) {
      const created = await purchaseOrderApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.order_no}，价税合计 ${created.amount_with_tax}`)
    } else {
      await purchaseOrderApi.update(editingId.value, {
        ...payload,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存采购订单失败')
  } finally {
    submitting.value = false
  }
}

// --- 提交 / 取消 / 关闭 -----------------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)

function reloadList(): void {
  void pageRef.value?.reload()
}

async function submitOrder(row: PurchaseOrder): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '提交后进入平台审批中心，审批通过后订单才可收货。',
      `提交 ${row.order_no}`,
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await purchaseOrderActionApi.submit(row.id, '')
    ElMessage.success('已提交审批')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '提交审批失败'))
  }
}

async function closeOrder(row: PurchaseOrder): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '关闭后不再收货；已到货部分不会回退。',
      `关闭 ${row.order_no}`,
      { inputPlaceholder: '关闭原因（可选）', inputValue: '' },
    )
    reason = result.value ?? ''
  } catch {
    return
  }
  try {
    await purchaseOrderActionApi.close(row.id, reason)
    ElMessage.success('已关闭')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '关闭失败'))
  }
}

async function cancelOrder(row: PurchaseOrder): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('存在未取消收货记录的订单不能取消。', `取消 ${row.order_no}`, {
      inputPlaceholder: '请填写取消原因（必填）',
      inputValidator: (value) => (value ? true : '必须填写原因'),
    })
    reason = result.value
  } catch {
    return
  }
  try {
    await purchaseOrderActionApi.cancel(row.id, reason)
    ElMessage.success('已取消')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '取消失败'))
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<PurchaseOrder | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as PurchaseOrder
  detailVisible.value = true
  try {
    detailRow.value = (await purchaseOrderApi.retrieve(Number(row.id))) as PurchaseOrder
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>