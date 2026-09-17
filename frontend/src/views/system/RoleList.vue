<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">角色与权限</h2>
        <p class="ys-page__description">
          权限分四层：菜单、操作、接口、数据范围。用户拥有多个角色时，操作权限取并集，
          数据范围取最宽的一档，并且始终先受公司边界限制；单一维度范围配置不完整时按最小范围（fail-closed）处理。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button v-if="canCreate" type="primary" :icon="Plus" @click="openCreate">新增角色</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="ys-filter-bar">
      <el-input
        v-model="filters.search"
        placeholder="搜索角色编码或名称"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
      />
      <el-select v-model="filters.data_scope_type" placeholder="数据范围" clearable style="width: 180px">
        <el-option
          v-for="item in scopeTypeOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <el-button type="primary" @click="reload">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="角色编码" width="160" />
      <el-table-column prop="name" label="角色名称" min-width="150" />
      <el-table-column prop="company_name" label="所属公司" width="140" />
      <el-table-column label="数据范围" width="140">
        <template #default="{ row }">{{ scopeLabel(row.data_scope_type) }}</template>
      </el-table-column>
      <el-table-column label="权限点" width="90" align="center">
        <template #default="{ row }">{{ row.permission_codes.length }}</template>
      </el-table-column>
      <el-table-column label="菜单" width="80" align="center">
        <template #default="{ row }">{{ row.menu_codes.length }}</template>
      </el-table-column>
      <el-table-column label="用户数" width="90" align="center">
        <template #default="{ row }">{{ row.user_count }}</template>
      </el-table-column>
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
          <el-tag v-if="row.is_system" type="warning" size="small" effect="plain" class="ys-ml-4">
            内置
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
          <el-button v-if="canUpdate" link type="primary" size="small" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button v-if="canAssign" link type="primary" size="small" @click="openPermissions(row)">
            权限
          </el-button>
          <el-button v-if="canAssign" link type="primary" size="small" @click="openMenus(row)">
            菜单
          </el-button>
          <el-button v-if="canAssign" link type="primary" size="small" @click="openScope(row)">
            数据范围
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无角色" />
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
      :title="editingId === null ? '新增角色' : '编辑角色'"
      width="640px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-alert v-if="formError" type="error" :closable="false" show-icon :title="formError" />
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="form.code" :disabled="editingId !== null" placeholder="如 sales_manager" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
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
        <el-form-item label="数据范围">
          <el-select v-model="form.data_scope_type" style="width: 100%">
            <el-option
              v-for="item in scopeTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <span class="ys-muted">
            选择「指定工厂 / 部门 / 仓库」或「自定义组织范围」后，还需要在「数据范围」对话框里选择具体对象。
          </span>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :controls="false" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="permissionsVisible" title="分配操作权限" width="720px" :close-on-click-modal="false">
      <el-alert v-if="permissionsError" type="error" :closable="false" show-icon :title="permissionsError" />
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="保存后该角色下所有用户的权限缓存立即失效，无需重新登录即可生效。"
      />
      <div class="ys-role__tree">
        <el-tree
          ref="permissionTreeRef"
          :data="permissionTree"
          show-checkbox
          node-key="key"
          :default-checked-keys="checkedPermissionKeys"
          :props="{ label: 'label', children: 'children' }"
        />
      </div>
      <template #footer>
        <el-button @click="permissionsVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitPermissions">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="menusVisible" title="分配菜单" width="640px" :close-on-click-modal="false">
      <el-alert v-if="menusError" type="error" :closable="false" show-icon :title="menusError" />
      <p class="ys-muted">
        菜单只控制导航可见性；隐藏菜单不等于禁止访问，接口权限仍需在「权限」中单独授予。
      </p>
      <div class="ys-role__tree">
        <el-tree
          ref="menuTreeRef"
          :data="menuTreeData"
          show-checkbox
          node-key="key"
          :default-checked-keys="checkedMenuKeys"
          :props="{ label: 'label', children: 'children' }"
        />
      </div>
      <template #footer>
        <el-button @click="menusVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitMenus">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="scopeVisible" title="设置数据范围" width="720px" :close-on-click-modal="false">
      <el-alert v-if="scopeError" type="error" :closable="false" show-icon :title="scopeError" />
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="后端对每个维度都会校验对象是否存在及其公司归属，不能通过传入任意 ID 越权。"
      />
      <el-form label-width="120px">
        <el-form-item label="范围类型">
          <el-select v-model="scopeForm.data_scope_type" style="width: 100%">
            <el-option
              v-for="item in scopeTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="公司">
          <el-select v-model="scopeForm.company_ids" multiple clearable filterable style="width: 100%">
            <el-option
              v-for="item in companySelectOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工厂">
          <el-select v-model="scopeForm.factory_ids" multiple clearable filterable style="width: 100%">
            <el-option
              v-for="item in factorySelectOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="scopeForm.department_ids" multiple clearable filterable style="width: 100%">
            <el-option
              v-for="item in departmentSelectOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="scopeForm.warehouse_ids" multiple clearable filterable style="width: 100%">
            <el-option
              v-for="item in warehouseSelectOptions"
              :key="String(item.value)"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scopeVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitScope">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="角色详情" size="520px">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="角色编码">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="角色名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="所属公司">{{ detail.company_name || '不限' }}</el-descriptions-item>
          <el-descriptions-item label="数据范围">{{ scopeLabel(detail.data_scope_type) }}</el-descriptions-item>
          <el-descriptions-item label="用户数">{{ detail.user_count }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="ys-section-title">已授权限点（{{ detail.permission_codes.length }}）</h4>
        <div class="ys-role__codes">
          <el-tag v-for="code in detail.permission_codes" :key="code" size="small" effect="plain">
            {{ code }}
          </el-tag>
          <span v-if="detail.permission_codes.length === 0" class="ys-muted">未授权任何权限点</span>
        </div>

        <h4 class="ys-section-title">数据范围明细</h4>
        <el-table :data="detail.scope_grants" border size="small">
          <el-table-column prop="dimension" label="维度" width="120" />
          <el-table-column prop="object_id" label="对象 ID" />
          <template #empty>
            <el-empty description="未配置自定义范围明细" :image-size="60" />
          </template>
        </el-table>
      </template>
      <el-empty v-else description="未加载到角色详情" />
    </el-drawer>
  </div>
</template><script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElTree, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { ApiError } from '@/api/http'
import { identityApi, roleApi } from '@/api/identity'
import {
  companyOptions,
  departmentOptions,
  factoryOptions,
  warehouseOptions,
} from '@/composables/optionLoaders'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import type { EnumOption, MenuNode, PermissionGroup, Role } from '@/types/models'

interface TreeNode {
  key: string
  label: string
  children?: TreeNode[]
}

const auth = useAuthStore()
const meta = useMetaStore()

const rows = ref<Role[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const errorMessage = ref('')

const filters = reactive<{ search: string; data_scope_type: string }>({
  search: '',
  data_scope_type: '',
})

const canCreate = computed(() => auth.hasPermission('identity.role.create'))
const canUpdate = computed(() => auth.hasPermission('identity.role.update'))
const canAssign = computed(() => auth.hasPermission('identity.role.assign_permission'))

const companySelectOptions = ref<EnumOption[]>([])
const factorySelectOptions = ref<EnumOption[]>([])
const departmentSelectOptions = ref<EnumOption[]>([])
const warehouseSelectOptions = ref<EnumOption[]>([])

const scopeTypeOptions = computed(() =>
  meta.options('data_scope_types').length > 0
    ? meta.options('data_scope_types')
    : [
        { value: 'all', label: '全部数据' },
        { value: 'company', label: '本公司' },
        { value: 'factory', label: '指定工厂' },
        { value: 'department', label: '指定部门' },
        { value: 'warehouse', label: '指定仓库' },
        { value: 'self', label: '仅本人' },
        { value: 'custom', label: '自定义组织范围' },
      ],
)

function scopeLabel(value: string): string {
  return scopeTypeOptions.value.find((item) => item.value === value)?.label ?? value
}

const formVisible = ref(false)
const formError = ref('')
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  code: '',
  name: '',
  company_id: null as number | null,
  data_scope_type: 'self',
  sort_order: 0,
  remark: '',
})

const formRules: FormRules = {
  code: [{ required: true, message: '请填写角色编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填写角色名称', trigger: 'blur' }],
}

const permissionsVisible = ref(false)
const permissionsError = ref('')
const permissionTreeRef = ref<InstanceType<typeof ElTree>>()
const permissionTree = ref<TreeNode[]>([])
const checkedPermissionKeys = ref<string[]>([])
const permissionsTargetId = ref<number | null>(null)

const menusVisible = ref(false)
const menusError = ref('')
const menuTreeRef = ref<InstanceType<typeof ElTree>>()
const menuTreeData = ref<TreeNode[]>([])
const checkedMenuKeys = ref<string[]>([])
const menusTargetId = ref<number | null>(null)

const scopeVisible = ref(false)
const scopeError = ref('')
const scopeForm = reactive<{
  data_scope_type: string
  company_ids: number[]
  factory_ids: number[]
  department_ids: number[]
  warehouse_ids: number[]
}>({
  data_scope_type: 'self',
  company_ids: [],
  factory_ids: [],
  department_ids: [],
  warehouse_ids: [],
})
const scopeTargetId = ref<number | null>(null)

const detailVisible = ref(false)
const detail = ref<Role | null>(null)

const PERMISSION_NODE_PREFIX = 'permission:'
const MENU_NODE_PREFIX = 'menu:'

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await roleApi.list({
      page: page.value,
      page_size: pageSize.value,
      search: filters.search || undefined,
      data_scope_type: filters.data_scope_type || undefined,
      ordering: 'sort_order',
    })
    rows.value = result.results
    total.value = result.count
  } catch (error) {
    rows.value = []
    total.value = 0
    errorMessage.value = error instanceof ApiError ? error.message : '加载角色列表失败'
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
  filters.data_scope_type = ''
  reload()
}

async function ensureOptions(): Promise<void> {
  if (companySelectOptions.value.length === 0) {
    companySelectOptions.value = await companyOptions().catch(() => [])
  }
  if (factorySelectOptions.value.length === 0) {
    factorySelectOptions.value = await factoryOptions().catch(() => [])
  }
  if (departmentSelectOptions.value.length === 0) {
    departmentSelectOptions.value = await departmentOptions().catch(() => [])
  }
  if (warehouseSelectOptions.value.length === 0) {
    warehouseSelectOptions.value = await warehouseOptions().catch(() => [])
  }
}

function openCreate(): void {
  editingId.value = null
  formError.value = ''
  form.code = ''
  form.name = ''
  form.company_id = null
  form.data_scope_type = 'self'
  form.sort_order = 0
  form.remark = ''
  formVisible.value = true
  void ensureOptions()
}

function openEdit(row: Role): void {
  editingId.value = row.id
  formError.value = ''
  form.code = row.code
  form.name = row.name
  form.company_id = row.company_id
  form.data_scope_type = row.data_scope_type
  form.sort_order = row.sort_order
  form.remark = row.remark
  formVisible.value = true
  void ensureOptions()
}

function openDetail(row: Role): void {
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
      await identityApi.createRole({
        code: form.code.trim(),
        name: form.name.trim(),
        company_id: form.company_id,
        data_scope_type: form.data_scope_type,
        sort_order: form.sort_order,
        remark: form.remark,
      })
      ElMessage.success('角色已创建，请继续分配权限与菜单')
    } else {
      await identityApi.updateRole(editingId.value, {
        name: form.name.trim(),
        company_id: form.company_id,
        data_scope_type: form.data_scope_type,
        sort_order: form.sort_order,
        remark: form.remark,
      })
      ElMessage.success('角色已保存')
    }
    formVisible.value = false
    await load()
  } catch (error) {
    formError.value =
      error instanceof ApiError ? error.fieldErrorMessage || error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

function buildPermissionTree(groups: PermissionGroup[]): TreeNode[] {
  return groups.map((group) => ({
    key: `module:${group.module}`,
    label: `${group.module}（${group.permissions.length}）`,
    children: group.permissions.map((permission) => ({
      key: `${PERMISSION_NODE_PREFIX}${permission.code}`,
      label: `${permission.name}（${permission.code}）`,
    })),
  }))
}

function buildMenuTree(nodes: MenuNode[]): TreeNode[] {
  return nodes.map((node) => ({
    key: `${MENU_NODE_PREFIX}${node.code}`,
    label: node.name,
    children: node.children && node.children.length > 0 ? buildMenuTree(node.children) : undefined,
  }))
}

async function openPermissions(row: Role): Promise<void> {
  permissionsTargetId.value = row.id
  permissionsError.value = ''
  checkedPermissionKeys.value = row.permission_codes.map(
    (code) => `${PERMISSION_NODE_PREFIX}${code}`,
  )
  permissionsVisible.value = true
  try {
    const groups = await identityApi.permissionGroups()
    permissionTree.value = buildPermissionTree(groups)
  } catch (error) {
    permissionsError.value = error instanceof ApiError ? error.message : '加载权限列表失败'
  }
}

async function submitPermissions(): Promise<void> {
  if (permissionsTargetId.value === null) {
    return
  }
  const tree = permissionTreeRef.value
  if (!tree) {
    return
  }
  const keys = [
    ...(tree.getCheckedKeys() as string[]),
    ...(tree.getHalfCheckedKeys() as string[]),
  ]
  const codes = keys
    .filter((key) => key.startsWith(PERMISSION_NODE_PREFIX))
    .map((key) => key.slice(PERMISSION_NODE_PREFIX.length))
  submitting.value = true
  permissionsError.value = ''
  try {
    await identityApi.setRolePermissions(permissionsTargetId.value, codes)
    ElMessage.success(`已保存 ${codes.length} 个权限点`)
    permissionsVisible.value = false
    await load()
  } catch (error) {
    permissionsError.value = error instanceof ApiError ? error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

async function openMenus(row: Role): Promise<void> {
  menusTargetId.value = row.id
  menusError.value = ''
  checkedMenuKeys.value = row.menu_codes.map((code) => `${MENU_NODE_PREFIX}${code}`)
  menusVisible.value = true
  try {
    menuTreeData.value = buildMenuTree(await identityApi.menuTree())
  } catch (error) {
    menusError.value = error instanceof ApiError ? error.message : '加载菜单失败'
  }
}

async function submitMenus(): Promise<void> {
  if (menusTargetId.value === null) {
    return
  }
  const tree = menuTreeRef.value
  if (!tree) {
    return
  }
  const keys = [
    ...(tree.getCheckedKeys() as string[]),
    ...(tree.getHalfCheckedKeys() as string[]),
  ]
  const codes = keys
    .filter((key) => key.startsWith(MENU_NODE_PREFIX))
    .map((key) => key.slice(MENU_NODE_PREFIX.length))
  submitting.value = true
  menusError.value = ''
  try {
    await identityApi.setRoleMenus(menusTargetId.value, codes)
    ElMessage.success(`已保存 ${codes.length} 个菜单`)
    menusVisible.value = false
    await load()
  } catch (error) {
    menusError.value = error instanceof ApiError ? error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

async function openScope(row: Role): Promise<void> {
  scopeTargetId.value = row.id
  scopeError.value = ''
  scopeForm.data_scope_type = row.data_scope_type
  scopeForm.company_ids = row.scope_grants
    .filter((grant) => grant.dimension === 'company')
    .map((grant) => grant.object_id)
  scopeForm.factory_ids = row.scope_grants
    .filter((grant) => grant.dimension === 'factory')
    .map((grant) => grant.object_id)
  scopeForm.department_ids = row.scope_grants
    .filter((grant) => grant.dimension === 'department')
    .map((grant) => grant.object_id)
  scopeForm.warehouse_ids = row.scope_grants
    .filter((grant) => grant.dimension === 'warehouse')
    .map((grant) => grant.object_id)
  scopeVisible.value = true
  await ensureOptions()
}

async function submitScope(): Promise<void> {
  if (scopeTargetId.value === null) {
    return
  }
  submitting.value = true
  scopeError.value = ''
  try {
    await identityApi.setRoleScope(scopeTargetId.value, {
      data_scope_type: scopeForm.data_scope_type,
      company_ids: scopeForm.company_ids,
      factory_ids: scopeForm.factory_ids,
      department_ids: scopeForm.department_ids,
      warehouse_ids: scopeForm.warehouse_ids,
    })
    ElMessage.success('数据范围已保存')
    scopeVisible.value = false
    await load()
  } catch (error) {
    scopeError.value =
      error instanceof ApiError ? error.fieldErrorMessage || error.message : '保存失败'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await meta.ensureLoaded().catch(() => undefined)
  await ensureOptions()
  await load()
})
</script>

<style scoped>
.ys-role__tree {
  max-height: 420px;
  padding: 8px;
  margin-top: 12px;
  overflow: auto;
  border: 1px solid var(--ys-gray-200);
  border-radius: 4px;
}

.ys-section-title {
  margin: 16px 0 12px;
  font-size: 14px;
  color: var(--ys-navy-900);
}

.ys-role__codes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ys-ml-4 {
  margin-left: 4px;
}
</style>