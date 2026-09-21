import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import PermissionList from '@/views/system/PermissionList.vue'
import type { PermissionGroup } from '@/types/models'
import { moduleDisplayName, permissionModuleNodeLabel } from '@/utils/permissionLabels'

/**
 * 权限模块一级分组的中文名。
 *
 * 背景（真实反馈）：角色配置与「权限与菜单」页面的一级分组只显示英文模块编码
 * （core / identity / masterdata …），业务人员看不懂该勾哪一组。
 * 后端 `MODULE_LABELS` 提供中文名，前端统一显示为「英文模块（中文名）」。
 */

vi.mock('@/api/identity', () => ({
  identityApi: {
    permissionGroups: vi.fn(),
    menuTree: vi.fn(),
  },
}))

const groups: PermissionGroup[] = [
  {
    module: 'core',
    module_name: '公共基础',
    permissions: [
      {
        code: 'core.user.view',
        name: '查看用户',
        resource: 'user',
        action: 'view',
        permission_type: 'action',
      },
    ],
  },
  {
    module: 'identity',
    module_name: '用户与权限',
    permissions: [
      {
        code: 'identity.role.view',
        name: '查看角色',
        resource: 'role',
        action: 'view',
        permission_type: 'action',
      },
      {
        code: 'identity.menu.view',
        name: '查看菜单',
        resource: 'menu',
        action: 'view',
        permission_type: 'action',
      },
    ],
  },
]

describe('权限模块显示文案', () => {
  it('一级分组显示「英文模块（中文名）」', () => {
    expect(moduleDisplayName('core', '公共基础')).toBe('core（公共基础）')
  })

  it('没有中文名时只显示模块编码，不出现空括号', () => {
    expect(moduleDisplayName('unknown', '')).toBe('unknown')
  })

  it('角色权限树的一级节点带权限点数量', () => {
    expect(permissionModuleNodeLabel(groups[0])).toBe('core（公共基础） · 1 项')
    expect(permissionModuleNodeLabel(groups[1])).toBe('identity（用户与权限） · 2 项')
  })
})

describe('权限与菜单页面', () => {
  async function mountPage() {
    const { identityApi } = await import('@/api/identity')
    vi.mocked(identityApi.permissionGroups).mockResolvedValue(groups)
    vi.mocked(identityApi.menuTree).mockResolvedValue([])

    const wrapper = mount(PermissionList, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    await nextTick()
    return wrapper
  }

  it('一级分组同时显示英文模块与中文名', async () => {
    const wrapper = await mountPage()
    const text = wrapper.text()

    expect(text).toContain('core（公共基础）')
    expect(text).toContain('identity（用户与权限）')
    // 不能只剩英文模块名
    expect(text).not.toContain('core（1）')
  })

  it('按关键字过滤后中文名仍然保留', async () => {
    const wrapper = await mountPage()

    await wrapper.find('input').setValue('core')
    await nextTick()

    const text = wrapper.text()
    expect(text).toContain('core（公共基础）')
    expect(text).not.toContain('identity（用户与权限）')
  })
})
