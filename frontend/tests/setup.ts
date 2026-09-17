/**
 * 测试环境补丁。
 *
 * jsdom 不实现 ResizeObserver / matchMedia，而 Element Plus 的表格与弹层在挂载时
 * 会用到它们。缺失时组件会静默渲染不出内容，测试会误报成「组件坏了」。
 * 这里提供最小桩实现，保证测试失败反映的是业务逻辑而不是环境能力。
 */

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