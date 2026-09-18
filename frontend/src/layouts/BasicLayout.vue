<template>
  <div class="ys-layout">
    <aside class="ys-layout__aside" :class="{ 'ys-layout__aside--collapsed': collapsed }">
      <div class="ys-layout__brand">
        <el-icon :size="18"><Shop /></el-icon>
        <span v-if="!collapsed" class="ys-layout__brand-title">意尚智造集成平台</span>
      </div>
      <div class="ys-layout__menu">
        <el-scrollbar>
          <side-menu :nodes="auth.menus" :collapsed="collapsed" :active-path="activePath" />
        </el-scrollbar>
      </div>
    </aside>

    <div class="ys-layout__main">
      <header class="ys-layout__header">
        <div class="ys-layout__header-left">
          <el-button
            link
            class="ys-layout__collapse"
            :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="toggleCollapsed"
          >
            <el-icon :size="18"><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/" class="ys-layout__breadcrumb">
            <el-breadcrumb-item>工作台</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="ys-layout__header-right">
          <el-tooltip content="使用说明（新窗口打开）">
            <el-button link @click="openGuide"><el-icon :size="18"><Reading /></el-icon></el-button>
          </el-tooltip>

          <el-tooltip content="刷新当前页面数据">
            <el-button link @click="refreshCurrent"><el-icon><Refresh /></el-icon></el-button>
          </el-tooltip>

          <el-badge :value="auth.unreadNotifications" :hidden="auth.unreadNotifications === 0">
            <el-button link :disabled="!canViewNotifications" @click="notificationVisible = true">
              <el-icon :size="18"><Bell /></el-icon>
            </el-button>
          </el-badge>

          <el-dropdown>
            <div class="ys-layout__user">
              <span class="ys-layout__avatar">{{ avatarText }}</span>
              <span>{{ auth.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  {{ auth.user?.company_name || '未设置公司' }}
                </el-dropdown-item>
                <el-dropdown-item disabled>
                  角色：{{ auth.roleNames.join('、') || '未分配' }}
                </el-dropdown-item>
                <el-dropdown-item divided @click="passwordVisible = true">修改密码</el-dropdown-item>
                <el-dropdown-item @click="openGuide">使用说明</el-dropdown-item>
                <el-dropdown-item @click="openDocs">接口文档</el-dropdown-item>
                <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <div class="ys-layout__tabs">
        <el-tabs
          :model-value="activePath"
          type="card"
          closable
          @tab-click="onTabClick"
          @tab-remove="closeTab"
        >
          <el-tab-pane
            v-for="tab in tabs"
            :key="tab.path"
            :name="tab.path"
            :label="tab.title"
            :closable="tabs.length > 1"
          />
        </el-tabs>
      </div>

      <main class="ys-layout__content">
        <el-alert
          v-if="auth.mustChangePassword"
          type="warning"
          show-icon
          :closable="false"
          title="当前账号使用初始密码"
          description="为保障账号安全，请尽快通过右上角「修改密码」设置个人密码。"
          class="ys-layout__notice"
        />
        <router-view v-slot="{ Component }">
          <keep-alive :max="12">
            <component :is="Component" :key="`${activePath}#${refreshKey}`" />
          </keep-alive>
        </router-view>
      </main>
    </div>

    <password-dialog v-model="passwordVisible" />
    <notification-drawer v-model="notificationVisible" :can-view="canViewNotifications" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import NotificationDrawer from '@/components/NotificationDrawer.vue'
import PasswordDialog from '@/components/PasswordDialog.vue'
import SideMenu from '@/components/SideMenu.vue'
import { useAutoCollapse } from '@/composables/useAutoCollapse'
import { resetDynamicRoutes } from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import { useTabsStore } from '@/stores/tabs'

const auth = useAuthStore()
const meta = useMetaStore()
const tabsStore = useTabsStore()
const route = useRoute()
const router = useRouter()

/** 窄屏自动折叠侧边栏（断点见 composables/useAutoCollapse.ts） */
const { collapsed, toggle: toggleCollapsed } = useAutoCollapse()
const passwordVisible = ref(false)
const notificationVisible = ref(false)
const refreshKey = ref(0)

const tabs = computed(() => tabsStore.tabs)
const activePath = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string | undefined) ?? '')
const avatarText = computed(() => (auth.displayName || '用户').slice(0, 1))
const canViewNotifications = computed(() => auth.hasPermission('core.notification.view'))

onMounted(async () => {
  await meta.ensureLoaded().catch(() => undefined)
  if (canViewNotifications.value) {
    await auth.refreshUnreadCount().catch(() => undefined)
  }
  tabsStore.open({ path: route.path, title: currentTitle.value || '工作台' })
})

watch(
  () => route.path,
  () => {
    tabsStore.open({ path: route.path, title: currentTitle.value || '工作台' })
  },
)

function onTabClick(pane: { paneName?: string | number }): void {
  const target = String(pane.paneName ?? '')
  if (target && target !== route.path) {
    void router.push(target)
  }
}

function closeTab(path: string | number): void {
  const next = tabsStore.close(String(path))
  if (String(path) === route.path && next) {
    void router.push(next)
  }
}

/**
 * 刷新当前页面：递增 key 让页面组件重新挂载并重新拉取数据。
 * 不通过整页 reload，避免丢失其它标签页状态。
 */
function refreshCurrent(): void {
  refreshKey.value += 1
}

function openDocs(): void {
  window.open('/api/v1/docs/', '_blank', 'noopener')
}

/** 使用说明网页版：由 scripts/build_user_guide.py 从 docs/user-guide.md 生成 */
function openGuide(): void {
  window.open('/guide.html', '_blank', 'noopener')
}

async function logout(): Promise<void> {
  await auth.logout()
  resetDynamicRoutes()
  tabsStore.reset()
  meta.reset()
  await router.replace({ name: 'login' })
}
</script>

<style scoped>
.ys-layout__notice {
  margin: 12px 16px 0;
}
</style>