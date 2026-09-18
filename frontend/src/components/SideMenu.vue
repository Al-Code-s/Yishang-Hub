<template>
  <el-menu
    :default-active="activePath"
    :collapse="collapsed"
    :collapse-transition="false"
    unique-opened
    router
    background-color="transparent"
    :class="`ys-menu--d${depth}`"
  >
    <template v-for="node in nodes" :key="node.id">
      <el-sub-menu
        v-if="node.children && node.children.length > 0"
        :index="node.path || node.code"
        class="ys-menu-group"
        :class="`ys-menu-group--d${depth}`"
      >
        <template #title>
          <el-icon v-if="node.icon"><component :is="node.icon" /></el-icon>
          <span>{{ node.name }}</span>
        </template>
        <side-menu
          :nodes="node.children"
          :collapsed="collapsed"
          :active-path="activePath"
          :depth="depth + 1"
        />
      </el-sub-menu>

      <el-menu-item
        v-else
        :index="node.path"
        class="ys-menu-node"
        :class="`ys-menu-node--d${depth}`"
      >
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
//
// depth 用于区分层级样式：0 = 一级目录（分组），1 = 二级页面。
// 样式定义在 src/styles/index.css 的「侧边导航」小节。
defineOptions({ name: 'SideMenu' })

withDefaults(
  defineProps<{
    nodes: MenuNode[]
    collapsed: boolean
    activePath: string
    depth?: number
  }>(),
  { depth: 0 },
)
</script>