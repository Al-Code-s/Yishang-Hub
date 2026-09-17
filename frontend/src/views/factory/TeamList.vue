<template>
  <div>
    <entity-list-page
      ref="pageRef"
      title="班组"
      entity-label="班组"
      description="班组绑定车间与默认班次。成员变更整体替换；班组排班展开为人员执行记录时会保留成员快照。"
      :api="api"
      :columns="columns"
      :filters="filters"
      :form-fields="formFields"
      :permissions="{ create: 'factory.team.create', update: 'factory.team.update' }"
      search-placeholder="搜索班组编码或名称"
    >
      <template #actions="{ row }">
        <el-button link type="primary" size="small" @click="openMembers(row)">成员维护</el-button>
      </template>
    </entity-list-page>

    <el-dialog
      v-model="memberVisible"
      :title="`成员维护 · ${currentTeam?.name ?? ''}`"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-alert
        v-if="memberError"
        type="error"
        :closable="false"
        show-icon
        :title="memberError"
        class="ys-form-error"
      />
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="整体替换"
        description="保存后会以当前列表整体替换班组原有成员；被移除的成员不影响历史报工记录。"
        class="ys-form-error"
      />

      <div class="ys-toolbar">
        <el-select
          v-model="pendingEmployeeId"
          filterable
          placeholder="选择员工后点击添加"
          style="width: 260px"
        >
          <el-option
            v-for="option in employeeSelectOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button :icon="Plus" @click="addMember">添加</el-button>
      </div>

      <el-table :data="memberRows" border size="small">
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column prop="employee_name" label="姓名" width="120" />
        <el-table-column label="班组角色" min-width="140">
          <template #default="{ row }">
            <el-input v-model="row.role_in_team" size="small" placeholder="例如 组长" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ $index }">
            <el-button link type="danger" size="small" @click="removeMember($index)">移除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="尚未添加成员" />
        </template>
      </el-table>

      <template #footer>
        <el-button @click="memberVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingMembers" @click="saveMembers">保存成员</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { ApiError } from '@/api/http'
import { teamApi } from '@/api/endpoints'
import { factoryApi } from '@/api/modules'
import { employeeOptions, shiftOptions, workshopOptions } from '@/composables/optionLoaders'
import type { EnumOption, TeamMemberRow } from '@/types/models'

interface EditableMember {
  employee_id: number
  employee_no: string
  employee_name: string
  role_in_team: string
}

const pageRef = ref<InstanceType<typeof EntityListPage>>()
const api = teamApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '班组编码', width: 120, sortable: true },
  { prop: 'name', label: '班组名称', minWidth: 140 },
  { prop: 'workshop_name', label: '所属车间', width: 150 },
  { prop: 'leader_name', label: '班组长', width: 110 },
  { prop: 'shift_name', label: '默认班次', width: 130 },
  { prop: 'members', label: '成员', minWidth: 200 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = [
  { prop: 'workshop_id', label: '所属车间', type: 'select' as const, optionsLoader: workshopOptions },
  { prop: 'shift_id', label: '默认班次', type: 'select' as const, optionsLoader: shiftOptions },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '班组编码', required: true },
  { prop: 'name', label: '班组名称', required: true },
  { prop: 'workshop_id', label: '所属车间', type: 'select', optionsLoader: workshopOptions },
  { prop: 'leader_id', label: '班组长', type: 'select', optionsLoader: employeeOptions },
  { prop: 'shift_id', label: '默认班次', type: 'select', optionsLoader: shiftOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])

const memberVisible = ref(false)
const savingMembers = ref(false)
const memberError = ref('')
const memberRows = ref<EditableMember[]>([])
const pendingEmployeeId = ref<number | null>(null)
const employeeSelectOptions = ref<EnumOption[]>([])
const currentTeam = ref<Record<string, unknown> | null>(null)

onMounted(async () => {
  employeeSelectOptions.value = await employeeOptions().catch(() => [])
})

function openMembers(row: Record<string, unknown>): void {
  currentTeam.value = row
  memberError.value = ''
  pendingEmployeeId.value = null
  const existing = (row.members ?? []) as TeamMemberRow[]
  memberRows.value = existing.map((member) => ({
    employee_id: member.employee_id,
    employee_no: member.employee_no,
    employee_name: member.name,
    role_in_team: member.role_in_team,
  }))
  memberVisible.value = true
}

function addMember(): void {
  if (!pendingEmployeeId.value) {
    ElMessage.warning('请先选择员工')
    return
  }
  if (memberRows.value.some((item) => item.employee_id === pendingEmployeeId.value)) {
    ElMessage.warning('该员工已在班组中')
    return
  }
  const option = employeeSelectOptions.value.find((item) => item.value === pendingEmployeeId.value)
  const label = String(option?.label ?? '')
  const [employeeNo, employeeName] = label.split(' ')
  memberRows.value.push({
    employee_id: pendingEmployeeId.value,
    employee_no: employeeNo ?? '',
    employee_name: employeeName ?? label,
    role_in_team: '',
  })
  pendingEmployeeId.value = null
}

function removeMember(index: number): void {
  memberRows.value.splice(index, 1)
}

async function saveMembers(): Promise<void> {
  const teamId = Number(currentTeam.value?.id ?? 0)
  if (!teamId) {
    return
  }
  savingMembers.value = true
  memberError.value = ''
  try {
    await factoryApi.teamMembers(
      teamId,
      memberRows.value.map((member) => ({
        employee_id: member.employee_id,
        role_in_team: member.role_in_team,
      })),
    )
    ElMessage.success('班组成员已更新')
    memberVisible.value = false
    await pageRef.value?.reload()
  } catch (error) {
    memberError.value = error instanceof ApiError ? error.fieldErrorMessage || error.message : '保存失败'
  } finally {
    savingMembers.value = false
  }
}
</script>