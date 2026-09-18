import { computed, onBeforeUnmount, onMounted, ref, watch, type ComputedRef, type Ref } from 'vue'

/**
 * 窄屏自动折叠侧边栏。
 *
 * 背景：主布局原来不分屏幕宽度，侧边栏恒定 220px；在 1366 及以下的笔记本上，
 * 表格会被挤到只剩很窄的可读宽度。
 *
 * 规则（断点必须与 `src/styles/index.css` 第 9 节的 @media 保持一致）：
 * 1) 视口宽度 ≤ 断点时默认折叠，只保留图标；
 * 2) 用户仍可手动展开/收起，手动操作优先于视口默认值；
 * 3) 视口跨过断点时清除手动偏好，回到「跟随视口」，
 *    避免窗口拉宽后侧边栏仍停留在收起状态。
 */
export const NARROW_BREAKPOINT = 1200

export interface AutoCollapse {
  /** 最终是否折叠：手动偏好优先，其次跟随视口 */
  collapsed: ComputedRef<boolean>
  /** 当前视口是否处于窄屏 */
  narrow: Ref<boolean>
  /** 用户手动切换折叠状态 */
  toggle: () => void
}

function isNarrowViewport(breakpoint: number): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= breakpoint
}

export function useAutoCollapse(breakpoint: number = NARROW_BREAKPOINT): AutoCollapse {
  // 首次渲染前就取一次视口宽度，避免宽屏加载时先渲染成展开态再跳变
  const narrow = ref(isNarrowViewport(breakpoint))
  /** null = 跟随视口；true / false = 用户手动指定 */
  const override = ref<boolean | null>(null)
  const collapsed = computed(() => override.value ?? narrow.value)

  let query: MediaQueryList | null = null

  /**
   * 统一以 window.innerWidth 为准：matchMedia 的 matches 在浏览器缩放
   * 与设备像素比变化时可能与 innerWidth 不同步，只信一个来源更不容易出错。
   */
  function syncFromViewport(): void {
    narrow.value = isNarrowViewport(breakpoint)
  }

  onMounted(() => {
    syncFromViewport()
    window.addEventListener('resize', syncFromViewport)
    if (typeof window.matchMedia === 'function') {
      query = window.matchMedia(`(max-width: ${breakpoint}px)`)
      // 断点跨越时立刻响应，不依赖 resize 事件的节流
      query.addEventListener?.('change', syncFromViewport)
    }
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', syncFromViewport)
    query?.removeEventListener?.('change', syncFromViewport)
    query = null
  })

  // 视口跨过断点后丢弃手动偏好，回到「跟随视口」
  watch(narrow, () => {
    override.value = null
  })

  function toggle(): void {
    override.value = !collapsed.value
  }

  return { collapsed, narrow, toggle }
}
