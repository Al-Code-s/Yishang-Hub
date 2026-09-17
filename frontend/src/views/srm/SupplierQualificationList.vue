<template>
  <entity-list-page
    title="供应商资质"
    entity-label="资质"
    description="登记供应商资质证书及有效期，为后续「资质到期提醒」提供数据依据。未填写到期日时显示「未登记到期日」，不会当成未过期。证书编号留空不参与去重。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'srm.supplier_qualification.create', update: 'srm.supplier_qualification.update' }"
    search-placeholder="搜索证书编号或发证机构"
    default-ordering="expiry_date"
    :page-size="20"
  >
    <template #column-qualification_type="{ row }">
      {{ meta.label('qualification_types', String(row.qualification_type)) }}
    </template>
    <template #column-expiry_date="{ row }">
      <span v-if="!row.expiry_date" class="ys-muted">未登记到期日</span>
      <template v-else>
        <span>{{ row.expiry_date }}</span>
        <el-tag
          v-if="row.is_expired"
          type="danger"
          size="small"
          effect="light"
          style="margin-left: 6px"
        >
          已过期 {{ Math.abs(Number(row.days_to_expiry)) }} 天
        </el-tag>
        <el-tag v-else type="success" size="small" effect="plain" style="margin-left: 6px">
          剩余 {{ row.days_to_expiry }} 天
        </el-tag>
      </template>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { supplierApi, supplierQualificationApi } from '@/api/endpoints'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption } from '@/types/models'

const meta = useMetaStore()
const api = supplierQualificationApi as never

async function supplierOptions(): Promise<EnumOption[]> {
  const page = await supplierApi.list({ page_size: 200, is_active: true, ordering: 'code' })
  return page.results.map((row) => ({
    value: row.id,
    label: `${row.code} ${row.name}`,
  }))
}

const columns: ProTableColumn[] = [
  { prop: 'supplier_name', label: '所属供应商', minWidth: 180 },
  { prop: 'qualification_type', label: '资质类型', width: 140 },
  { prop: 'certificate_no', label: '证书编号', width: 170 },
  { prop: 'issued_by', label: '发证机构', minWidth: 160 },
  { prop: 'issued_date', label: '发证日期', width: 120 },
  { prop: 'expiry_date', label: '到期日期', width: 220 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'supplier_id',
    label: '所属供应商',
    type: 'select' as const,
    optionsLoader: supplierOptions,
  },
  {
    prop: 'qualification_type',
    label: '资质类型',
    type: 'select' as const,
    options: meta.options('qualification_types'),
  },
])

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'supplier_id',
    label: '所属供应商',
    type: 'select',
    required: true,
    optionsLoader: supplierOptions,
  },
  {
    prop: 'qualification_type',
    label: '资质类型',
    type: 'select',
    required: true,
    options: meta.options('qualification_types'),
  },
  {
    prop: 'certificate_no',
    label: '证书编号',
    help: '同一供应商+同类型下不允许重复；留空表示暂未登记，可多条并存',
  },
  { prop: 'issued_by', label: '发证机构' },
  { prop: 'issued_date', label: '发证日期', type: 'date' },
  { prop: 'expiry_date', label: '到期日期', type: 'date', help: '不得早于发证日期' },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>