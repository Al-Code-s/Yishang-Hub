/**
 * 测试环境补丁。
 *
 * 1. jsdom 不实现 ResizeObserver / matchMedia，而 Element Plus 的表格与弹层在挂载时
 *    会用到它们。缺失时组件会静默渲染不出内容，测试会误报成「组件坏了」。
 *    这里提供最小桩实现，保证测试失败反映的是业务逻辑而不是环境能力。
 *
 * 2. Element Plus 表格把重排函数包成 `debounce(doLayout, 50)`，并且在重排时会调用
 *    全局 `requestAnimationFrame`。用例结束后若组件仍留在内存里，这个 50ms 的定时器
 *    会在 jsdom 环境拆除之后才触发，此时 `requestAnimationFrame` 已随环境消失，
 *    vitest 会报 1 条 unhandled error（用例全通过但进程退出码非 0，冒烟脚本因此失败）。
 *    处理方式分两步：
 *      - 每个用例结束后统一卸载组件，让表格的 onBeforeUnmount 取消待触发的重排；
 *      - 文件结束前留出一段静默期，让卸载本身重新排出的那一次重排跑完。
 *    实测：卸载后 50ms 内会有 1 次迟到重排，之后归零，因此 120ms 足够。
 */

import { enableAutoUnmount } from '@vue/test-utils'
import { afterAll, afterEach } from 'vitest'

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

const globalObject = globalThis as unknown as Record<string, unknown>

if (typeof globalObject.ResizeObserver === 'undefined') {
  globalObject.ResizeObserver = ResizeObserverStub
}

if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

if (typeof globalObject.requestAnimationFrame === 'undefined') {
  globalObject.requestAnimationFrame = ((callback: FrameRequestCallback): number =>
    setTimeout(() => callback(Date.now()), 0) as unknown as number) as unknown as typeof requestAnimationFrame
}

if (typeof globalObject.cancelAnimationFrame === 'undefined') {
  globalObject.cancelAnimationFrame = ((handle: number): void => {
    clearTimeout(handle)
  }) as unknown as typeof cancelAnimationFrame
}

enableAutoUnmount((cleanup: () => void) => {
  afterEach(cleanup)
})

afterAll(async () => {
  await new Promise((resolve) => setTimeout(resolve, 120))
})
