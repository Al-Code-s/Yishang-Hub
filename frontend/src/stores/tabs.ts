import { ref } from 'vue'
import { defineStore } from 'pinia'

export interface TabItem {
  path: string
  title: string
}

/** 顶部标签页。只保留已访问页面，最多 12 个，超出时淘汰最早的。 */
export const useTabsStore = defineStore('tabs', () => {
  const tabs = ref<TabItem[]>([])
  const MAX_TABS = 12

  function open(tab: TabItem): void {
    if (!tab.path || tab.path === '/login') {
      return
    }
    const existing = tabs.value.find((item) => item.path === tab.path)
    if (existing) {
      existing.title = tab.title || existing.title
      return
    }
    tabs.value.push(tab)
    if (tabs.value.length > MAX_TABS) {
      tabs.value.splice(0, tabs.value.length - MAX_TABS)
    }
  }

  /** 关闭标签，返回应当跳转到的相邻标签路径（若关闭的是最后一个则返回空）。 */
  function close(path: string): string {
    const index = tabs.value.findIndex((item) => item.path === path)
    if (index < 0) {
      return ''
    }
    tabs.value.splice(index, 1)
    const next = tabs.value[index] ?? tabs.value[index - 1]
    return next ? next.path : ''
  }

  function reset(): void {
    tabs.value = []
  }

  return { tabs, open, close, reset }
})