<template>
  <el-menu
    :default-active="activePath"
    :collapse="collapsed"
    :collapse-transition="false"
    unique-opened
    router
    background-color="transparent"
  >
    <template v-for="node in nodes" :key="node.id">
      <el-sub-menu v-if="node.children && node.children.length > 0" :index="node.path || node.code">
        <template #title>
          <el-icon v-if="node.icon"><component :is="node.icon" /></el-icon>
          <span>{{ node.name }}</span>
        </template>
        <side-menu :nodes="node.children" :collapsed="collapsed" :active-path="activePath" />
      </el-sub-menu>

      <el-menu-item v-else :index="node.path">
        <el-icon v-if="node.icon"><component :is="node.icon" /></el-icon>
        <template #title>{{ node.name }}</template>
      </el-menu-item>
    </template>
  </el-menu>
</template>

<script setup lang="ts">
import type { MenuNode } from '@/types/models'

// 菜单完全由后端按权限返回（/api/v1/identity/auth/session/ 的 menus），
// 前端不做二次筛选，避免出现「菜单藏了但路由还能进」的假安全。
defineOptions({ name: 'SideMenu' })

defineProps<{
  nodes: MenuNode[]
  collapsed: boolean
  activePath: string
}>()
</script>