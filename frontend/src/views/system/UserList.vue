<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">用户管理</h2>
        <p class="ys-page__description">
          用户负责登录与权限，员工档案负责组织、岗位与排班，两者一对一可选关联。
          平台不提供用户物理删除：账号停用即可，历史操作记录与审计必须保留。
          初始密码由管理员设置，系统不生成也不会在页面上回显明文密码。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索用户名、姓名或手机号"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
      />
      <el-select v-model="filters.company_id" placeholder="所属公司" clearable style="width: 180px">
        <el-option
          v-for="item in companySelectOptions"
          :key="String(item.value)"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-select v-model="filters.is_active" placeholder="状态" clearable style="width: 120px">
        <el-option label="启用" :value="true" />
        <el-option label="停用" :value="false" />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="display_name" label="姓名" width="120" />
      <el-table-column prop="company_name" label="所属公司" width="140" />
      <el-table-column prop="department_name" label="部门" width="130" />
      <el-table-column label="角色" min-width="180">
        <template #default="{ row }">
          <el-tag
            v-for="role in row.roles"
            :key="role.id"
            size="small"
            effect="plain"
            class="ys-user__role"
          >
            {{ role.name }}
          </el-tag>
          <span v-if="row.roles.length === 0" class="ys-muted">未分配角色</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
          <el-tag v-if="row.is_locked" type="danger" size="small" effect="light" class="ys-ml-4">
            已锁定
          </el-tag>
          <el-tag v-if="row.must_change_password" type="warning" size="small" effect="plain" class="ys-ml-4">
            需改密
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" width="170">
        <template #default="{ row }">{{ formatDateTime(row.last_login) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="290" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
          <el-button v-if="canUpdate" link type="primary" size="small" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button
            v-if="canAssignRole"
            link
            type="primary"
            size="small"
            @click="openRoles(row)"
          >
            角色
          </el-button>
          <el-button
            v-if="canResetPassword"
            link
            type="warning"
            size="small"
            @click="openReset(row)"
          >
            重置密码
          </el-button>
          <el-button v-if="canUnlock && row.is_locked" link type="success" size="small" @click="unlock(row)">
            解锁
          </el-button>
          <el-button
            v-if="canDeactivate"
            link
            :type="row.is_active ? 'danger' : 'success'"
            size="small"
            @click="toggleActive(row)"
          >
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无用户" />
      </template>
    </el-table>

    <div class="ys-pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="load"
      />
    </div>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新增用户' : '编辑用户'"
      width="720px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert v-if="formError" type="error" :closable="false" show-icon :title="formError" />
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" :disabled="editingId !== null" autocomplete="off" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item v-if="editingId === null" label="初始密码" prop="password">
              <el-input v-model="form.password" type="password" show-password autocomplete="new-password" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名">
              <el-input v-model="form.display_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属公司">
              <el-select v-model="form.company_id" clearable style="width: 100%">
                <el-option
                  v-for="item in companySelectOptions"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门">
              <el-select v-model="form.department_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in departmentSelectOptions"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="editingId === null" :span="12">
            <el-form-item label="角色">
              <el-select v-model="form.role_ids" multiple filterable style="width: 100%">
                <el-option
                  v-for="item in roleSelectOptions"
                  :key="String(item.value)"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="后台登录">
              <el-switch v-model="form.is_staff" />
              <span class="ys-muted">仅影响 Django Admin 访问，不代表业务权限。</span>
            </el-form-item>
          </el-col>
          <el-col v-if="editingId === null" :span="12">
            <el-form-item label="下次登录改密">
              <el-switch v-model="form.must_change_password" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rolesVisible" title="分配角色" width="520px" :close-on-click-modal="false">
      <el-alert v-if="rolesError" type="error" :closable="false" show-icon :title="rolesError" />
      <p class="ys-muted">
        用户最终权限 = 所有启用角色的权限并集；数据范围取最宽的一档，且始终受公司边界限制。
        收回角色后，前端菜单会在下次刷新会话时同步收敛。
      </p>
      <el-checkbox-group v-model="selectedRoleIds">
        <el-checkbox v-for="item in roleSelectOptions" :key="String(item.value)" :value="item.value">
          {{ item.label }}
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="rolesVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRoles">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="480px" :close-on-click-modal="false">
      <el-alert v-if="resetError" type="error" :closable="false" show-icon :title="resetError" />
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="重置后该用户所有登录会话将失效，且下次登录需要修改密码。"
      />
      <el-form label-width="100px">
        <el-form-item label="新密码" required>
          <el-input v-model="resetForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="重置原因">
          <el-input v-model="resetForm.reason" placeholder="将写入审计日志" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="用户详情" size="480px">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="用户名">{{ detail.username }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ detail.display_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="公司">{{ detail.company_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="部门">{{ detail.department_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            {{ detail.roles.map((role) => role.name).join('、') || '未分配' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            {{ detail.is_active ? '启用' : '停用' }}{{ detail.is_locked ? ' / 已锁定' : '' }}
          </el-descriptions-item>
          <el-descriptions-item label="连续失败次数">{{ detail.failed_login_count }}</el-descriptions-item>
          <el-descriptions-item label="锁定至">
            {{ formatDateTime(detail.locked_until) }}
          </el-descriptions-item>
          <el-descriptions-item label="最后登录">
            {{ formatDateTime(detail.last_login) }}（{{ detail.last_login_ip || '-' }}）
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(detail.date_joined) }}
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>
        <p class="ys-muted">数据版本 v{{ detail.version }}，更新于 {{ formatDateTime(detail.updated_at) }}</p>
      </template>
      <el-empty v-else description="未加载到用户详情" />
    </el-drawer>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { identityApi, userApi } from '@/api/identity'
import { companyOptions, departmentOptions, roleOptions } from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import type { EnumOption, UserRow } from '@/types/models'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

const rows = ref<UserRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')

const filters = reactive<{ search: string; company_id: number | null; is_active: boolean | '' }>({
  search: '',
  company_id: null,
  is_active: '',
})

const companySelectOptions = ref<EnumOption[]>([])
const departmentSelectOptions = ref<EnumOption[]>([])
const roleSelectOptions = ref<EnumOption[]>([])

const canCreate = computed(() => auth.hasPermission('identity.user.create'))
const canUpdate = computed(() => auth.hasPermission('identity.user.update'))
const canDeactivate = computed(() => auth.hasPermission('identity.user.deactivate'))
const canResetPassword = computed(() => auth.hasPermission('identity.user.reset_password'))
const canUnlock = computed(() => auth.hasPermission('identity.user.unlock'))
const canAssignRole = computed(() => auth.hasPermission('identity.user.assign_role'))

const formVisible = ref(false)
const formError = ref('')
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const editingVersion = ref<number | null>(null)

const form = reactive({
  username: '',
  password: '',
  display_name: '',
  phone: '',
  email: '',
  company_id: null as number | null,
  department_id: null as number | null,
  is_staff: false,
  must_change_password: true,
  role_ids: [] as number[],
  remark: '',
})

const formRules: FormRules = {
  username: [{ required: true, message: '请填写用户名', trigger: 'blur' }],
  password: [
    {
      validator: (_rule, value, callback) => {
        if (editingId.value === null && !value) {
          callback(new Error('请填写初始密码'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

const rolesVisible = ref(false)
const rolesError = ref('')
const selectedRoleIds = ref<number[]>([])
const rolesTargetId = ref<number | null>(null)

const resetVisible = ref(false)
const resetError = ref('')
const resetForm = reactive({ new_password: '', reason: '' })
const resetTargetId = ref<number | null>(null)

const detailVisible = ref(false)
const detail = ref<UserRow | null>(null)

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await userApi.list({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      company_id: filters.company_id ?? undefined,
      is_active: filters.is_active === '' ? undefined : filters.is_active,
      ordering: 'username',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载用户列表失败'
  } finally {
    loading.value = false
  }
}

function reload(): void {
  page.value = 1
  void load()
}

function resetFilters(): void {
  filters.search = ''
  filters.company_id = null
  filters.is_active = ''
  reload()
}

async function ensureOptions(): Promise<void> {
  if (companySelectOptions.value.length === 0) {
    companySelectOptions.value = await companyOptions().catch(() => [])
  }
  if (departmentSelectOptions.value.length === 0) {
    departmentSelectOptions.value = await departmentOptions().catch(() => [])
  }
  if (roleSelectOptions.value.length === 0) {
    roleSelectOptions.value = await roleOptions().catch(() => [])
  }
}

function openCreate(): void {
  editingId.value = null
  editingVersion.value = null
  formError.value = ''
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.phone = ''
  form.email = ''
  form.company_id = null
  form.department_id = null
  form.is_staff = false
  form.must_change_password = true
  form.role_ids = []
  form.remark = ''
  formVisible.value = true
  void ensureOptions()
}

function openEdit(row: UserRow): void {
  editingId.value = row.id
  editingVersion.value = row.version
  formError.value = ''
  form.username = row.username
  form.password = ''
  form.display_name = row.display_name
  form.phone = row.phone ?? ''
  form.email = row.email
  form.company_id = row.company_id
  form.department_id = row.department_id
  form.is_staff = row.is_staff
  form.must_change_password = row.must_change_password
  form.remark = row.remark
  formVisible.value = true
  void ensureOptions()
}

function openDetail(row: UserRow): void {
  detail.value = row
  detailVisible.value = true
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  formError.value = ''
  try {
    if (editingId.value === null) {
      await identityApi.createUser({
        username: form.username.trim(),
        password: form.password,
        display_name: form.display_name,
        phone: form.phone || null,
        email: form.email,
        company_id: form.company_id,
        department_id: form.department_id,
        is_staff: form.is_staff,
        must_change_password: form.must_change_password,
        role_ids: form.role_ids,
        remark: form.remark,
      })
      ElMessage.success('用户已创建，请通过安全渠道把初始密码交给本人')
    } else {
      await identityApi.updateUser(editingId.value, {
        display_name: form.display_name,
        phone: form.phone || null,
        email: form.email,
        company_id: form.company_id,
        department_id: form.department_id,
        is_staff: form.is_staff,
        remark: form.remark,
        expected_version: editingVersion.value ?? undefined,
      })
      ElMessage.success('用户已保存')
    }
    formVisible.value = false
    await load()
  } catch (error) {
    if (error instanceof ApiError) {
      formError.value =
        error.code === 'VERSION_CONFLICT'
          ? '数据已被他人修改，请关闭窗口后重新打开再编辑。'
          : error.fieldErrorMessage || error.message
    } else {
      formError.value = '保存失败'
    }
  } finally {
    submitting.value = false
  }
}

async function openRoles(row: UserRow): Promise<void> {
  rolesTargetId.value = row.id
  rolesError.value = ''
  selectedRoleIds.value = row.roles.map((role) => role.id)
  rolesVisible.value = true
  await ensureOptions()
}

async function submitRoles(): Promise<void> {
  if (rolesTargetId.value === null) {
    return
  }
  submitting.value = true
  rolesError.value = ''
  try {
    await identityApi.assignRoles(rolesTargetId.value, selectedRoleIds.value)
    ElMessage.success('角色已更新')
    rolesVisible.value = false
    await load()
  } catch (error) {
    rolesError.value = error instanceof ApiError ? error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

function openReset(row: UserRow): void {
  resetTargetId.value = row.id
  resetError.value = ''
  resetForm.new_password = ''
  resetForm.reason = ''
  resetVisible.value = true
}

async function submitReset(): Promise<void> {
  if (resetTargetId.value === null) {
    return
  }
  if (!resetForm.new_password) {
    resetError.value = '请填写新密码。'
    return
  }
  submitting.value = true
  resetError.value = ''
  try {
    await identityApi.resetUserPassword(resetTargetId.value, resetForm.new_password, resetForm.reason)
    ElMessage.success('密码已重置')
    resetVisible.value = false
    await load()
  } catch (error) {
    resetError.value = error instanceof ApiError ? error.fieldErrorMessage || error.message : '重置失败'
  } finally {
    submitting.value = false
  }
}

async function unlock(row: UserRow): Promise<void> {
  try {
    await identityApi.unlockUser(row.id)
    ElMessage.success('账号已解锁')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '解锁失败')
  }
}

async function toggleActive(row: UserRow): Promise<void> {
  const next = !row.is_active
  const confirmText = next
    ? `确认启用账号「${row.username}」？`
    : `停用后「${row.username}」的现有会话会立即失效，且不能登录。确认停用？`
  const confirmed = await ElMessageBox.confirm(confirmText, next ? '启用确认' : '停用确认', {
    type: 'warning',
    confirmButtonText: next ? '确认启用' : '确认停用',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (!confirmed) {
    return
  }
  try {
    await identityApi.setUserActive(row.id, next)
    ElMessage.success(next ? '已启用' : '已停用')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
  }
}

onMounted(async () => {
  await ensureOptions()
  await load()
})
</script>

<style scoped>
.ys-user__role {
  margin-right: 4px;
}

.ys-ml-4 {
  margin-left: 4px;
}
</style>