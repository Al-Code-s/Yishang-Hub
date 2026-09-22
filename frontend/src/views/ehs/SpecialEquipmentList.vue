<template>
  <entity-list-page
    title="特种设备检验"
    entity-label="检验记录"
    description="起重机械、压力容器、叉车等特种设备的定期检验记录：使用证编号、检验机构、检验日期、下次检验日期与检验结论。关联设备台账后，检验到期情况可以在设备设施安全里统一查看。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.special_equipment.create', update: 'ehs.special_equipment.update' }"
    search-placeholder="搜索使用证编号、设备名称、检验机构或检验员"
    default-ordering="next_inspection_date"
    :toggleable="false"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { specialEquipmentInspectionApi } from '@/api/endpoints'
import { companyOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const api = specialEquipmentInspectionApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'certificate_no', label: '使用证编号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备名称', minWidth: 160 },
  { prop: 'linked_equipment_name', label: '关联设备台账', width: 160 },
  { prop: 'inspection_org', label: '检验机构', width: 160 },
  { prop: 'inspection_date', label: '检验日期', width: 120, sortable: true },
  { prop: 'next_inspection_date', label: '下次检验日期', width: 140, sortable: true },
  { prop: 'result', label: '检验结论', width: 120 },
  { prop: 'inspector', label: '检验员', width: 110 },
  { prop: 'issue_date', label: '发证日期', width: 120 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'result', label: '检验结论', type: 'select' as const, options: meta.options('special_equipment_results') },
  { prop: 'equipment_id', label: '关联设备', type: 'select' as const, optionsLoader: equipmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'certificate_no', label: '使用证编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'equipment_id', label: '关联设备', type: 'select', optionsLoader: equipmentOptions, help: '从设备台账里选择，便于统一查看检验到期情况' },
  { prop: 'equipment_name', label: '设备名称', help: '台账里没有的设备可以直接填写名称' },
  { prop: 'inspection_org', label: '检验机构', required: true },
  { prop: 'inspection_date', label: '检验日期', type: 'date' },
  { prop: 'next_inspection_date', label: '下次检验日期', type: 'date' },
  { prop: 'result', label: '检验结论', type: 'select', options: meta.options('special_equipment_results'), defaultValue: "qualified" },
  { prop: 'inspector', label: '检验员' },
  { prop: 'issue_date', label: '发证日期', type: 'date' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
