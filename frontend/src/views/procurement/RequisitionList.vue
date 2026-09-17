<template>
  <div>
    <entity-list-page
      title="采购申请"
      entity-label="采购申请"
      description="常规 / 计划 / 紧急申请统一在此登记。提交后进入审批（复用平台审批中心），只有「已批准」的申请可以转采购订单，且转单数量不得超过未转数量。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :detail-fields="detailFields"
      ref="pageRef"
      readonly
      default-ordering="-id"
      search-placeholder="搜索申请单号、用途或备注"
      empty-text="暂无采购申请"
      :page-size="20"
      :action-width="300"
    >
      <template #toolbar>
        <el-button
          v-if="can('procurement.requisition.create')"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增采购申请
        </el-button>
      </template>

      <template #column-request_type="{ row }">
        {{ meta.label('requisition_types', String(row.request_type)) }}
      </template>
      <template #column-status="{ row }">
        <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
          {{ row.status_display || meta.label('requisition_statuses', String(row.status)) }}
        </el-tag>
      </template>
      <template #column-line_count="{ row }">{{ (row.lines ?? []).length }}</template>

      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        <el-button
          v-if="can('procurement.requisition.update') && row.status === 'draft'"
          link
          type="primary"
          size="small"
          @click="openEdit(row)"
        >
          编辑
        </el-button>
        <el-button
          v-if="can('procurement.requisition.submit') && row.status === 'draft'"
          link
          type="success"
          size="small"
          @click="submitRequisition(row)"
        >
          提交审批
        </el-button>
        <el-button
          v-if="can('procurement.order.create') && row.status === 'approved'"
          link
          type="warning"
          size="small"
          @click="openConvert(row)"
        >
          转订单
        </el-button>
        <el-button
          v-if="can('procurement.requisition.update') && row.status === 'draft'"
          link
          type="danger"
          size="small"
          @click="cancelRequisition(row)"
        >
          取消
        </el-button>
      </template>

    </entity-list-page>

    <el-drawer
      v-model="detailVisible"
      :title="`采购申请 ${detailRow?.requisition_no ?? ''}`"
      size="600px"
    >
      <el-descriptions v-if="detailRow" :column="2" border size="small">
        <el-descriptions-item label="申请类型">
          {{ meta.label('requisition_types', String(detailRow.request_type)) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">{{ detailRow.status_display }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ detailRow.applicant_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="需求日期">{{ detailRow.needed_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用途说明" :span="2">{{ detailRow.purpose || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detailRow.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批实例">
          {{ detailRow.approval_instance_id ?? '未提交审批' }}
        </el-descriptions-item>
        <el-descriptions-item label="批准时间">{{ detailRow.approved_at || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">申请明细</el-divider>
      <el-table :data="(detailRow?.lines ?? []) as never[]" border size="small">
        <el-table-column prop="line_no" label="行号" width="60" />
        <el-table-column label="物料" min-width="180">
          <template #default="{ row: line }">
            {{ line.material_code }} {{ line.material_name }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="申请数量" width="110" />
        <el-table-column prop="ordered_quantity" label="已转数量" width="110" />
        <el-table-column prop="needed_date" label="需求日期" width="110" />
      </el-table>
      <el-alert
        class="ys-detail-hint"
        type="info"
        :closable="false"
        show-icon
        title="采购申请不产生库存变动；只有收货过账才影响库存，质量放行决定库存能否被动用。"
      />
    </el-drawer>


    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增采购申请' : '编辑采购申请'"
      width="960px"
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
            <el-form-item label="申请类型" required>
              <el-select v-model="form.request_type" style="width: 100%">
                <el-option
                  v-for="item in meta.options('requisition_types')"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="需求日期">
              <el-date-picker
                v-model="form.needed_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="申请部门">
              <el-select v-model="form.department_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in departmentChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="用途说明">
              <el-input v-model="form.purpose" maxlength="255" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="需求工厂">
              <el-select v-model="form.factory_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in factoryChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">申请明细（数量必须大于 0）</el-divider>
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
              <el-input v-model="row.quantity" placeholder="0.000000" />
            </template>
          </el-table-column>
          <el-table-column label="计量单位" width="140">
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
          <el-table-column label="建议供应商" width="180">
            <template #default="{ row }">
              <el-select v-model="row.suggested_supplier_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in supplierChoices"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="140">
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

    <el-dialog
      v-model="convertVisible"
      title="按申请转采购订单"
      width="620px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert
        v-if="convertError"
        type="error"
        :closable="false"
        show-icon
        :title="convertError"
        class="ys-form-error"
      />
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="不选择明细行表示按申请全部未转数量转单；转单后申请行的「已转数量」会增加，重复转单会被后端拒绝。"
      />
      <el-form label-width="110px" class="ys-convert-form">
        <el-form-item label="供应商" required>
          <el-select v-model="convertForm.supplier_id" filterable style="width: 100%">
            <el-option
              v-for="item in supplierChoices"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="收货仓库">
          <el-select v-model="convertForm.warehouse_id" clearable filterable style="width: 100%">
            <el-option
              v-for="item in warehouseChoices"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="期望到货日">
          <el-date-picker
            v-model="convertForm.expected_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="税率(%)">
          <el-input v-model="convertForm.tax_rate" placeholder="0 ~ 100，留空按 0" />
        </el-form-item>
        <el-form-item label="结算方式">
          <el-input v-model="convertForm.payment_terms" maxlength="64" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="convertForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="convertVisible = false">取消</el-button>
        <el-button type="primary" :loading="converting" @click="submitConvert">生成采购订单</el-button>
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
import { requisitionApi } from '@/api/endpoints'
import { requisitionActionApi } from '@/api/modules'
import {
  departmentOptions,
  factoryOptions,
  materialOptions,
  supplierOptions,
  uomOptions,
  warehouseOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type {
  EnumOption,
  PurchaseRequisition,
  PurchaseRequisitionLine,
  RequisitionInput,
} from '@/types/models'
import { toApiString } from '@/utils/decimal'

function toMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}

const meta = useMetaStore()
const auth = useAuthStore()
const api = requisitionApi as never

function can(code: string): boolean {
  return auth.hasPermission(code)
}

const columns: ProTableColumn[] = [
  { prop: 'requisition_no', label: '申请单号', width: 160, sortable: true },
  { prop: 'request_type', label: '申请类型', width: 110 },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'needed_date', label: '需求日期', width: 120 },
  { prop: 'applicant_name', label: '申请人', width: 110 },
  { prop: 'purpose', label: '用途说明', minWidth: 180 },
  { prop: 'line_count', label: '明细行', width: 90 },
]

const filters = [
  {
    prop: 'request_type',
    label: '申请类型',
    type: 'select' as const,
    options: meta.options('requisition_types'),
  },
  {
    prop: 'status',
    label: '状态',
    type: 'select' as const,
    options: meta.options('requisition_statuses'),
  },
]

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'remark', label: '备注' },
]

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'approved') return 'success'
  if (status === 'submitted') return 'warning'
  if (status === 'rejected' || status === 'cancelled') return 'danger'
  return 'info'
}

// --- 下拉选项 ---------------------------------------------------------------
const materialChoices = ref<EnumOption[]>([])
const uomChoices = ref<EnumOption[]>([])
const supplierChoices = ref<EnumOption[]>([])
const warehouseChoices = ref<EnumOption[]>([])
const departmentChoices = ref<EnumOption[]>([])
const factoryChoices = ref<EnumOption[]>([])

async function loadChoices(): Promise<void> {
  const loaded = await Promise.all([
    materialOptions(),
    uomOptions(),
    supplierOptions(),
    warehouseOptions(),
    departmentOptions(),
    factoryOptions(),
  ]).catch(() => [[], [], [], [], [], []] as EnumOption[][])
  materialChoices.value = loaded[0]
  uomChoices.value = loaded[1]
  supplierChoices.value = loaded[2]
  warehouseChoices.value = loaded[3]
  departmentChoices.value = loaded[4]
  factoryChoices.value = loaded[5]
}

// --- 新增 / 编辑 ------------------------------------------------------------
interface LineDraft {
  material_id: number | null
  quantity: string
  uom_id: number | null
  suggested_supplier_id: number | null
  remark: string
}

const formVisible = ref(false)
const submitting = ref(false)
const formError = ref('')
const editingId = ref<number | null>(null)
const editingVersion = ref<number | null>(null)
const form = reactive<{
  request_type: string
  needed_date: string
  department_id: number | null
  factory_id: number | null
  purpose: string
  remark: string
  lines: LineDraft[]
}>({
  request_type: 'normal',
  needed_date: '',
  department_id: null,
  factory_id: null,
  purpose: '',
  remark: '',
  lines: [],
})

function emptyLine(): LineDraft {
  return { material_id: null, quantity: '', uom_id: null, suggested_supplier_id: null, remark: '' }
}

function addLine(): void {
  form.lines.push(emptyLine())
}

function openCreate(): void {
  editingId.value = null
  editingVersion.value = null
  form.request_type = 'normal'
  form.needed_date = ''
  form.department_id = null
  form.factory_id = null
  form.purpose = ''
  form.remark = ''
  form.lines = [emptyLine()]
  formError.value = ''
  formVisible.value = true
}

function openEdit(row: PurchaseRequisition): void {
  editingId.value = row.id
  editingVersion.value = row.version
  form.request_type = row.request_type
  form.needed_date = row.needed_date ?? ''
  form.department_id = row.department_id
  form.factory_id = row.factory_id
  form.purpose = row.purpose
  form.remark = row.remark
  form.lines = (row.lines ?? []).map((line: PurchaseRequisitionLine) => ({
    material_id: line.material_id,
    quantity: String(line.quantity),
    uom_id: line.uom_id,
    suggested_supplier_id: line.suggested_supplier_id,
    remark: line.remark,
  }))
  formError.value = ''
  formVisible.value = true
}

function buildLines(): RequisitionInput['lines'] {
  const rows: RequisitionInput['lines'] = []
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
      uom_id: line.uom_id,
      suggested_supplier_id: line.suggested_supplier_id,
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
  let lines: RequisitionInput['lines']
  try {
    lines = buildLines()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '明细不完整'
    return
  }
  submitting.value = true
  try {
    const payload: RequisitionInput = {
      request_type: form.request_type,
      needed_date: form.needed_date || null,
      department_id: form.department_id,
      factory_id: form.factory_id,
      purpose: form.purpose,
      remark: form.remark,
      lines,
    }
    if (editingId.value === null) {
      const created = await requisitionApi.create(payload)
      ElMessage.success(`已保存草稿 ${created.requisition_no}，请提交审批`)
    } else {
      await requisitionApi.update(editingId.value, {
        ...payload,
        expected_version: editingVersion.value,
      } as never)
      ElMessage.success('保存成功')
    }
    formVisible.value = false
    reloadList()
  } catch (error) {
    formError.value = toMessage(error, '保存采购申请失败')
  } finally {
    submitting.value = false
  }
}

// --- 提交 / 取消 / 转单 -----------------------------------------------------
const pageRef = ref<InstanceType<typeof EntityListPage> | null>(null)

function reloadList(): void {
  void pageRef.value?.reload()
}

async function submitRequisition(row: PurchaseRequisition): Promise<void> {
  let comment = ''
  try {
    const result = await ElMessageBox.prompt(
      '提交后进入平台审批中心，审批结果会自动回写本单据状态。',
      `提交 ${row.requisition_no}`,
      { inputPlaceholder: '提交说明（可选）', inputValue: '' },
    )
    comment = result.value ?? ''
  } catch {
    return
  }
  try {
    await requisitionActionApi.submit(row.id, comment)
    ElMessage.success('已提交审批')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '提交审批失败'))
  }
}

async function cancelRequisition(row: PurchaseRequisition): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '已生成采购订单的申请不能取消。',
      `取消 ${row.requisition_no}`,
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
    await requisitionActionApi.cancel(row.id, reason)
    ElMessage.success('已取消')
    reloadList()
  } catch (error) {
    ElMessage.error(toMessage(error, '取消失败'))
  }
}

const convertVisible = ref(false)
const converting = ref(false)
const convertError = ref('')
const convertTarget = ref<PurchaseRequisition | null>(null)
const convertForm = reactive({
  supplier_id: null as number | null,
  warehouse_id: null as number | null,
  expected_date: '',
  tax_rate: '',
  payment_terms: '',
  remark: '',
})

function openConvert(row: PurchaseRequisition): void {
  convertTarget.value = row
  convertForm.supplier_id = null
  convertForm.warehouse_id = null
  convertForm.expected_date = ''
  convertForm.tax_rate = ''
  convertForm.payment_terms = ''
  convertForm.remark = ''
  convertError.value = ''
  convertVisible.value = true
}

async function submitConvert(): Promise<void> {
  convertError.value = ''
  if (!convertTarget.value) {
    return
  }
  if (!convertForm.supplier_id) {
    convertError.value = '请选择供应商'
    return
  }
  converting.value = true
  try {
    const payload: Record<string, unknown> = { supplier_id: convertForm.supplier_id }
    if (convertForm.warehouse_id) payload.warehouse_id = convertForm.warehouse_id
    if (convertForm.expected_date) payload.expected_date = convertForm.expected_date
    if (convertForm.tax_rate.trim()) payload.tax_rate = toApiString(convertForm.tax_rate)
    if (convertForm.payment_terms.trim()) payload.payment_terms = convertForm.payment_terms
    if (convertForm.remark.trim()) payload.remark = convertForm.remark
    const order = await requisitionActionApi.convert(convertTarget.value.id, payload as never)
    ElMessage.success(`已生成采购订单 ${order.order_no}`)
    convertVisible.value = false
    reloadList()
  } catch (error) {
    convertError.value = toMessage(error, '转单失败')
  } finally {
    converting.value = false
  }
}

// --- 详情 -------------------------------------------------------------------
const detailVisible = ref(false)
const detailRow = ref<PurchaseRequisition | null>(null)

async function openDetail(row: Record<string, unknown>): Promise<void> {
  detailRow.value = row as unknown as PurchaseRequisition
  detailVisible.value = true
  try {
    detailRow.value = (await requisitionApi.retrieve(Number(row.id))) as PurchaseRequisition
  } catch (error) {
    ElMessage.error(toMessage(error, '加载详情失败'))
  }
}

onMounted(async () => {
  await loadChoices()
})
</script>