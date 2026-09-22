<template>
  <entity-list-page
    title="生产报工"
    entity-label="生产报工"
    description="报工台账记录每一次工序报工，原始记录不可回改：单次报工必须满足「合格 + 返工 + 报废 = 报工数量」，同一工序累计报工不能超过工单计划数量，报满即完工该工序。质检点工序报满时会自动生成一张检验单，由质量人员判定。工单的领料、下达与完工在「生产工单」页面操作。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :detail-fields="detailFields"
    search-placeholder="搜索报工单号、工单号或工序"
    default-ordering="-reported_at"
    :page-size="20"
    readonly
    ref="pageRef"
  >
    <template #column-report_type="{ row }">
      {{ row.report_type_display || meta.label('production_report_types', String(row.report_type)) }}
    </template>
    <template #column-step_name="{ row }">
      {{ row.step_sequence ? row.step_sequence + '. ' : '' }}{{ row.step_name }}
    </template>
    <template #toolbar>
      <el-button v-if="canReport" type="primary" :icon="Plus" @click="openReport">
        报工
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="reportVisible" title="生产报工" width="720px" :close-on-click-modal="false">
    <el-alert
      v-if="reportError"
      type="error"
      :closable="false"
      show-icon
      :title="reportError"
      class="ys-form-error"
    />
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="只用「已下达 / 生产中」的工单可以报工；合格 + 返工 + 报废 必须等于报工数量。"
    />
    <el-form :model="reportForm" label-width="120px" class="ys-mt-4">
      <el-form-item label="生产工单" required>
        <el-select
          v-model="reportForm.order_id"
          filterable
          style="width: 100%"
          placeholder="请选择已下达或生产中的工单"
          @change="onOrderChange"
        >
          <el-option
            v-for="option in orderOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="工序" required>
        <el-select
          v-model="reportForm.step_id"
          filterable
          style="width: 100%"
          :disabled="!reportForm.order_id"
          placeholder="请先选择工单"
        >
          <el-option
            v-for="option in stepOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <div v-if="gateHint" class="ys-muted">{{ gateHint }}</div>
      </el-form-item>
      <el-form-item label="报工类型">
        <el-select v-model="reportForm.report_type" style="width: 100%">
          <el-option
            v-for="option in meta.options('production_report_types')"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="报工数量" required>
        <el-input v-model="reportForm.quantity" placeholder="本次报工数量" />
      </el-form-item>
      <el-form-item label="合格数量">
        <el-input v-model="reportForm.qualified_quantity" placeholder="留空按 0 处理" />
      </el-form-item>
      <el-form-item label="返工数量">
        <el-input v-model="reportForm.rework_quantity" placeholder="留空按 0 处理" />
      </el-form-item>
      <el-form-item label="报废数量">
        <el-input v-model="reportForm.scrap_quantity" placeholder="留空按 0 处理" />
      </el-form-item>
      <el-form-item label="报工人">
        <el-select v-model="reportForm.operator_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in operatorOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="生产设备">
        <el-select v-model="reportForm.equipment_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in equipmentOptionsList"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="实际工时">
        <el-input v-model="reportForm.work_hours" placeholder="小时，留空按 0 处理" />
      </el-form-item>
      <el-form-item label="开工时间">
        <el-date-picker
          v-model="reportForm.started_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="完工时间">
        <el-date-picker
          v-model="reportForm.finished_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="reportForm.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="reportVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitReport">提交报工</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError, get } from '@/api/http'
import { productionOrderApi, productionReportApi } from '@/api/endpoints'
import { companyOptions, employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, ProductionOrderStep } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = productionReportApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canReport = computed(() => auth.hasPermission('mes.report.create'))

const columns: ProTableColumn[] = [
  { prop: 'report_no', label: '报工单号', width: 170, sortable: true },
  { prop: 'order_no', label: '生产工单', width: 160 },
  { prop: 'step_name', label: '工序', minWidth: 140 },
  { prop: 'report_type', label: '报工类型', width: 110 },
  { prop: 'quantity', label: '报工数量', width: 110 },
  { prop: 'qualified_quantity', label: '合格', width: 100 },
  { prop: 'rework_quantity', label: '返工', width: 90 },
  { prop: 'scrap_quantity', label: '报废', width: 90 },
  { prop: 'operator_name', label: '报工人', width: 110 },
  { prop: 'equipment_name', label: '生产设备', width: 140 },
  { prop: 'reported_at', label: '报工时间', width: 170, sortable: true },
]

const orderFilterOptions = ref<EnumOption[]>([])
const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'order_id',
    label: '生产工单',
    type: 'select' as const,
    options: orderFilterOptions.value,
  },
  {
    prop: 'report_type',
    label: '报工类型',
    type: 'select' as const,
    options: meta.options('production_report_types'),
  },
  { prop: 'operator_id', label: '报工人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'work_hours', label: '实际工时' },
  { prop: 'started_at', label: '开工时间' },
  { prop: 'finished_at', label: '完工时间' },
  { prop: 'remark', label: '备注' },
]

const reportVisible = ref(false)
const reportError = ref('')
const submitting = ref(false)
const orderOptions = ref<EnumOption[]>([])
const stepOptions = ref<EnumOption[]>([])
const operatorOptions = ref<EnumOption[]>([])
const equipmentOptionsList = ref<EnumOption[]>([])
const gateHint = ref('')
const reportForm = reactive<Record<string, unknown>>({
  order_id: null,
  step_id: null,
  report_type: 'normal',
  quantity: '',
  qualified_quantity: '',
  rework_quantity: '',
  scrap_quantity: '',
  operator_id: null,
  equipment_id: null,
  work_hours: '',
  started_at: '',
  finished_at: '',
  remark: '',
})

onMounted(async () => {
  const [orders, operators, machines] = await Promise.all([
    loadReportableOrders().catch(() => []),
    employeeOptions().catch(() => []),
    equipmentOptions().catch(() => []),
  ])
  orderOptions.value = orders
  orderFilterOptions.value = orders
  operatorOptions.value = operators
  equipmentOptionsList.value = machines
})

async function loadReportableOrders(): Promise<EnumOption[]> {
  const page = await productionOrderApi.list({ page_size: 200, ordering: '-id' })
  return page.results
    .filter((row) => row.status === 'released' || row.status === 'in_progress')
    .map((row) => {
      const label = [row.order_no, row.style_name, row.quantity + (row.unit || '')]
        .filter((part) => Boolean(part))
        .join(' · ')
      return { value: row.id, label }
    })
}

function openReport(): void {
  reportError.value = ''
  stepOptions.value = []
  gateHint.value = ''
  reportForm.order_id = null
  reportForm.step_id = null
  reportForm.report_type = 'normal'
  reportForm.quantity = ''
  reportForm.qualified_quantity = ''
  reportForm.rework_quantity = ''
  reportForm.scrap_quantity = ''
  reportForm.operator_id = null
  reportForm.equipment_id = null
  reportForm.work_hours = ''
  reportForm.started_at = ''
  reportForm.finished_at = ''
  reportForm.remark = ''
  reportVisible.value = true
}

async function onOrderChange(value: unknown): Promise<void> {
  reportForm.step_id = null
  gateHint.value = ''
  stepOptions.value = []
  if (!value) {
    return
  }
  try {
    const steps = await get<ProductionOrderStep[]>('/mes/orders/' + String(value) + '/steps/')
    stepOptions.value = steps.map((step) => ({
      value: step.id,
      label:
        String(step.sequence) +
        '. ' +
        step.name +
        '（已报 ' +
        step.reported_quantity +
        '）' +
        (step.is_quality_gate ? ' · 质检点' : ''),
    }))
    if (steps.length === 0) {
      gateHint.value = '该工单还没有工序，请先在「生产工单」页面下达。'
    }
  } catch (error) {
    reportError.value = error instanceof ApiError ? error.message : '工序加载失败'
  }
}

async function submitReport(): Promise<void> {
  if (!reportForm.order_id || !reportForm.step_id) {
    reportError.value = '请先选择生产工单与工序。'
    return
  }
  if (!reportForm.quantity) {
    reportError.value = '请填写报工数量。'
    return
  }
  submitting.value = true
  reportError.value = ''
  try {
    await productionReportApi.create({
      order_id: Number(reportForm.order_id),
      step_id: Number(reportForm.step_id),
      report_type: String(reportForm.report_type || 'normal'),
      quantity: String(reportForm.quantity),
      qualified_quantity: String(reportForm.qualified_quantity || '0'),
      rework_quantity: String(reportForm.rework_quantity || '0'),
      scrap_quantity: String(reportForm.scrap_quantity || '0'),
      operator_id: reportForm.operator_id ? Number(reportForm.operator_id) : null,
      equipment_id: reportForm.equipment_id ? Number(reportForm.equipment_id) : null,
      work_hours: String(reportForm.work_hours || '0'),
      started_at: reportForm.started_at || null,
      finished_at: reportForm.finished_at || null,
      remark: String(reportForm.remark || ''),
    } as never)
    ElMessage.success('报工已提交')
    reportVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    reportError.value = error instanceof ApiError ? error.message : '报工失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
