<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">权限与菜单</h2>
        <p class="ys-page__description">
          权限点是代码内的唯一契约：后端 `apps/identity/permissions_registry.py` 定义，
          启动检查会校验代码中声明的权限编码是否都已登记，因此这里只读，不允许在界面上临时新增权限。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <el-tabs v-model="activeTab" class="ys-panel ys-panel--flush">
      <el-tab-pane :label="`权限点（${permissionCount}）`" name="permissions">
        <div class="ys-filter-bar">
          <el-input
            v-model="keyword"
            placeholder="按模块、名称或编码过滤"
            clearable
            style="width: 280px"
          />
          <span class="ys-muted">共 {{ permissionCount }} 个权限点，{{ filteredGroups.length }} 个模块</span>
        </div>

        <el-collapse v-model="expandedModules">
          <el-collapse-item
            v-for="group in filteredGroups"
            :key="group.module"
            :name="group.module"
          >
            <template #title>
              <span class="ys-permission__module">{{ group.module }}</span>
              <span class="ys-muted">（{{ group.permissions.length }}）</span>
            </template>
            <el-table :data="group.permissions" border size="small">
              <el-table-column prop="code" label="权限编码" min-width="240" />
              <el-table-column prop="name" label="权限名称" min-width="160" />
              <el-table-column prop="resource" label="资源" width="140" />
              <el-table-column prop="action" label="动作" width="140" />
              <el-table-column label="类型" width="110">
                <template #default="{ row }">
                  <el-tag size="small" effect="plain">{{ typeLabel(row.permission_type) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </el-tab-pane>

      <el-tab-pane :label="`菜单（${menuCount}）`" name="menus">
        <p class="ys-muted">
          菜单组件路径必须与前端 `src/views/**` 下的文件一一对应；路径不匹配时前端不会注册路由，
          并在浏览器控制台给出告警，而不是出现「点进去白屏」的假菜单。
        </p>
        <el-table :data="flatMenus" border size="small" row-key="id">
          <el-table-column prop="name" label="菜单名称" min-width="160" />
          <el-table-column prop="code" label="菜单编码" width="180" />
          <el-table-column prop="path" label="路由" min-width="180" />
          <el-table-column prop="component" label="组件" min-width="240" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">{{ menuTypeLabel(row.menu_type) }}</template>
          </el-table-column>
          <el-table-column prop="permission_code" label="进入所需权限" min-width="200" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.visible ? 'success' : 'info'" size="small" effect="light">
                {{ row.visible ? '显示' : '隐藏' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import type { MenuNode, PermissionGroup } from '@/types/models'

const activeTab = ref('permissions')
const groups = ref<PermissionGroup[]>([])
const menus = ref<MenuNode[]>([])
const keyword = ref('')
const expandedModules = ref<string[]>([])
const loading = ref(false)
const errorMessage = ref('')

const permissionCount = computed(() =>
  groups.value.reduce((sum, group) => sum + group.permissions.length, 0),
)

const filteredGroups = computed(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) {
    return groups.value
  }
  return groups.value
    .map((group) => ({
      module: group.module,
      permissions: group.permissions.filter(
        (item) =>
          item.code.toLowerCase().includes(needle) ||
          item.name.toLowerCase().includes(needle) ||
          group.module.toLowerCase().includes(needle),
      ),
    }))
    .filter((group) => group.permissions.length > 0)
})

const flatMenus = computed(() => {
  const result: MenuNode[] = []
  const walk = (nodes: MenuNode[]): void => {
    for (const node of nodes) {
      result.push(node)
      if (node.children && node.children.length > 0) {
        walk(node.children)
      }
    }
  }
  walk(menus.value)
  return result
})

const menuCount = computed(() => flatMenus.value.length)

function typeLabel(value: string): string {
  const map: Record<string, string> = {
    menu: '菜单权限',
    action: '操作权限',
    api: '接口权限',
    data: '数据范围权限',
  }
  return map[value] ?? value
}

function menuTypeLabel(value: string): string {
  const map: Record<string, string> = { directory: '目录', page: '页面', button: '按钮' }
  return map[value] ?? value
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [grouped, tree] = await Promise.all([
      identityApi.permissionGroups(),
      identityApi.menuTree(),
    ])
    groups.value = grouped
    menus.value = tree
    expandedModules.value = grouped.slice(0, 2).map((group) => group.module)
  } catch (error) {
    groups.value = []
    menus.value = []
    errorMessage.value = error instanceof ApiError ? error.message : '加载权限数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ys-permission__module {
  margin-right: 4px;
  font-weight: 600;
  color: var(--ys-navy-900);
}
</style>