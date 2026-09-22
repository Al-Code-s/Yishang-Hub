<template>
  <entity-list-page
    title="设备运行记录"
    entity-label="运行记录"
    description="记录设备一段运行区间：开始运行时登记，结束时填产量与能耗，系统自动算出运行时长与单位产量能耗，并对超限的单耗自动报警。记录只能由服务层推进状态，不提供直接编辑，避免事后修改历史口径。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :permissions="{ create: 'ems.run_record.create', update: 'ems.run_record.execute' }"
    search-placeholder="搜索记录编号、仪表或产量说明"
    default-ordering="-started_at"
    :toggleable="false"
    readonly
    :page-size="20"
    :action-width="240"
    ref="pageRef"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('run_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #toolbar="{ reload }">
      <el-button v-if="canStart" type="primary" @click="openStart">开始运行记录</el-button>
      <el-button @click="reload">刷新</el-button>
    </template>
    <template #row-actions="{ row, reload }">
      <el-button
        v-if="canFinish && row.status === 'running'"
        link
        type="success"
        size="small"
        @click="openFinish(row)"
      >
        结束并计算单耗
      </el-button>
      <el-button
        v-if="canFinish && row.status === 'running'"
        link
        type="danger"
        size="small"
        @click="cancelRecord(row, reload)"
      >
        取消
      </el-button>
    </template>
  </entity-list-page>

  <el-dialog v-model="startVisible" title="开始运行记录" width="640px" :close-on-click-modal="false">
    <el-alert v-if="startError" type="error" :closable="false" show-icon :title="startError" class="ys-form-error" />
    <el-form :model="startForm" label-width="120px">
      <el-form-item label="计量设备" required>
        <el-select v-model="startForm.meter_id" filterable style="width: 100%">
          <el-option
            v-for="option in meterOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="设备">
        <el-select v-model="startForm.equipment_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in equipmentOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="操作人">
        <el-select v-model="startForm.operator_id" clearable filterable style="width: 100%">
          <el-option
            v-for="option in operatorOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="开始时间">
        <el-date-picker
          v-model="startForm.started_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="产量说明">
        <el-input v-model="startForm.output_desc" placeholder="例如：3 号线 A 产品" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="startForm.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="startVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitStart">确认开始</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="finishVisible" title="结束运行记录" width="640px" :close-on-click-modal="false">
    <el-alert v-if="finishError" type="error" :closable="false" show-icon :title="finishError" class="ys-form-error" />
    <el-form :model="finishForm" label-width="140px">
      <el-form-item label="结束时间">
        <el-date-picker
          v-model="finishForm.finished_at"
          type="datetime"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="产量">
        <el-input v-model="finishForm.output_qty" placeholder="留空表示不统计单耗" />
      </el-form-item>
      <el-form-item label="产量说明">
        <el-input v-model="finishForm.output_desc" />
      </el-form-item>
      <el-form-item label="能耗用量">
        <el-input v-model="finishForm.energy_consumption" placeholder="留空时按抄表区间自动汇总" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="finishVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitFinish">确认结束</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { energyActions } from '@/api/energy'
import { energyRunRecordApi } from '@/api/endpoints'
import {
  companyOptions,
  employeeOptions,
  energyMeterOptions,
  equipmentOptions as loadEquipmentOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'
import type { EnumOption } from '@/types/models'

const auth = useAuthStore()
const meta = useMetaStore()
const api = energyRunRecordApi as never
const pageRef = ref<{ reload: () => Promise<void> } | null>(null)

const canStart = computed(() => auth.hasPermission('ems.run_record.create'))
const canFinish = computed(() => auth.hasPermission('ems.run_record.execute'))

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (status === 'finished') return 'success'
  if (status === 'running') return 'primary'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'record_no', label: '记录编号', width: 160, sortable: true },
  { prop: 'meter_name', label: '计量设备', minWidth: 150 },
  { prop: 'equipment_name', label: '设备', width: 140 },
  { prop: 'status', label: '状态', width: 100 },
  {
    prop: 'started_at',
    label: '开始时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.started_at ?? '')),
  },
  {
    prop: 'finished_at',
    label: '结束时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.finished_at ?? '')),
  },
  { prop: 'run_minutes', label: '运行时长（分钟）', width: 140 },
  { prop: 'output_qty', label: '产量', width: 110, formatter: (row) => formatDecimal(row.output_qty as string) },
  {
    prop: 'energy_consumption',
    label: '能耗用量',
    width: 120,
    formatter: (row) => formatDecimal(row.energy_consumption as string),
  },
  {
    prop: 'unit_consumption',
    label: '单位产量能耗',
    width: 130,
    formatter: (row) => formatDecimal(row.unit_consumption as string),
  },
  { prop: 'operator_name', label: '操作人', width: 110 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'meter_id', label: '计量设备', type: 'select' as const, optionsLoader: energyMeterOptions },
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: loadEquipmentOptions },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('run_statuses') },
])

const startVisible = ref(false)
const startError = ref('')
const finishVisible = ref(false)
const finishError = ref('')
const submitting = ref(false)
const finishTarget = ref<Record<string, unknown> | null>(null)
const meterOptions = ref<EnumOption[]>([])
const equipmentOptions = ref<EnumOption[]>([])
const operatorOptions = ref<EnumOption[]>([])

const startForm = reactive<Record<string, unknown>>({
  meter_id: null,
  equipment_id: null,
  operator_id: null,
  started_at: '',
  output_desc: '',
  remark: '',
})
const finishForm = reactive<Record<string, unknown>>({
  finished_at: '',
  output_qty: '',
  output_desc: '',
  energy_consumption: '',
})

onMounted(async () => {
  meterOptions.value = await energyMeterOptions().catch(() => [])
  equipmentOptions.value = await loadEquipmentOptions().catch(() => [])
  operatorOptions.value = await employeeOptions().catch(() => [])
})

function openStart(): void {
  startError.value = ''
  startForm.meter_id = null
  startForm.equipment_id = null
  startForm.operator_id = null
  startForm.started_at = ''
  startForm.output_desc = ''
  startForm.remark = ''
  startVisible.value = true
}

async function submitStart(): Promise<void> {
  if (!startForm.meter_id) {
    startError.value = '请选择计量设备。'
    return
  }
  submitting.value = true
  startError.value = ''
  try {
    await energyActions.startRun({
      meter_id: startForm.meter_id,
      equipment_id: startForm.equipment_id || null,
      operator_id: startForm.operator_id || null,
      started_at: startForm.started_at || null,
      output_desc: startForm.output_desc,
      remark: startForm.remark,
    })
    ElMessage.success('已开始运行记录')
    startVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    startError.value = error instanceof ApiError ? error.message : '操作失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

function openFinish(row: Record<string, unknown>): void {
  finishTarget.value = row
  finishError.value = ''
  finishForm.finished_at = ''
  finishForm.output_qty = ''
  finishForm.output_desc = String(row.output_desc ?? '')
  finishForm.energy_consumption = ''
  finishVisible.value = true
}

async function submitFinish(): Promise<void> {
  const target = finishTarget.value
  if (!target) {
    return
  }
  submitting.value = true
  finishError.value = ''
  try {
    await energyRunRecordApi.action(Number(target.id), 'finish', {
      finished_at: finishForm.finished_at || null,
      output_qty: finishForm.output_qty || null,
      output_desc: finishForm.output_desc || '',
      energy_consumption: finishForm.energy_consumption || null,
    })
    ElMessage.success('运行记录已结束')
    finishVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    finishError.value = error instanceof ApiError ? error.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function cancelRecord(row: Record<string, unknown>, reload: () => Promise<void>): Promise<void> {
  const confirmed = await ElMessageBox.confirm(
    '取消后该次运行记录不再参与单耗统计。确认取消？',
    '取消确认',
    { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '再想想' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await energyRunRecordApi.action(Number(row.id), 'cancel', { reason: '界面取消' })
    ElMessage.success('已取消')
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}
</script>
