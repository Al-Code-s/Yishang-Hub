import type { PermissionGroup } from '@/types/models'

/**
 * 权限模块一级分组的显示文案。
 *
 * 权限编码的第一段是模块（`core.user.view` → `core`），它是英文的。
 * 配置角色权限时只看到 `core`、`identity` 这类模块名，业务人员无法判断该勾哪一组，
 * 因此统一显示成「英文模块（中文名）」：`core（公共基础）`。
 *
 * 中文名来自后端 `MODULE_LABELS`（`apps/identity/permissions_registry.py`），
 * 前端不硬编码映射，避免后端新增模块时两边不一致。
 */

/** `core` + `公共基础` → `core（公共基础）`；没有中文名时只返回模块编码。 */
export function moduleDisplayName(module: string, moduleName: string): string {
  return moduleName ? `${module}（${moduleName}）` : module
}

/**
 * 角色权限树的一级节点文案：`core（公共基础）· 12 项`。
 *
 * 结尾带权限点数量，便于一眼看出该模块授权规模。
 */
export function permissionModuleNodeLabel(group: PermissionGroup): string {
  const base = moduleDisplayName(group.module, group.module_name)
  return group.permissions.length > 0 ? `${base} · ${group.permissions.length} 项` : base
}
