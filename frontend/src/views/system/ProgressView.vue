<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">实施进度</h2>
        <p class="ys-page__description">
          本页说明平台当前实际实施到哪一步，供管理员判断「哪些模块现在可以用」。
          页面上的阶段与未完成事项与仓库内 `docs/progress.md`、`docs/requirements-matrix.md` 保持一致；
          上半部分的计数来自后端接口实时计算，下半部分的阶段状态是文档镜像，不是业务报表数据。
        </p>
      </div>
      <div class="ys-page__header-actions">
        <el-button :loading="loading" @click="load">刷新计数</el-button>
      </div>
    </div>

    <el-alert
      class="ys-progress__notice"
      type="warning"
      :closable="false"
      show-icon
      title="未实施的模块不提供菜单与路由"
    >
      任务书要求「未实施的模块不展示伪可用页面」。因此 MES 工单与报工、质量、设备、能源、
      安全环保、厂内物流、终端安全等**尚未实施**的模块不会出现在左侧导航中，也不存在对应可访问路由；
      它们将在后续阶段实现，而不是通过对接外部 ERP / MES / WMS 完成。
    </el-alert>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <h3 class="ys-section-title">实时计数（来自当前环境的后端接口）</h3>
    <div class="ys-stat-cards">
      <el-card
        v-for="item in counters"
        :key="item.key"
        shadow="never"
        class="ys-stat-card"
      >
        <div class="ys-stat__label">{{ item.label }}</div>
        <div class="ys-stat__value">{{ item.value }}</div>
        <div class="ys-stat__hint">{{ item.hint }}</div>
      </el-card>
    </div>

    <h3 class="ys-section-title">阶段实施状态（文档镜像）</h3>
    <el-table :data="stages" border size="small">
      <el-table-column prop="stage" label="阶段" width="70" align="center" />
      <el-table-column prop="scope" label="范围" min-width="240" />
      <el-table-column width="130" label="状态">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)" size="small" effect="light">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="note" label="说明" min-width="300" />
    </el-table>

    <h3 class="ys-section-title">阶段 1 已完成 / 未完成</h3>
    <div class="ys-grid-2">
      <div>
        <el-card shadow="never">
          <template #header>已完成（可操作、已持久化、已加权限）</template>
          <ul class="ys-progress__list">
            <li v-for="item in doneItems" :key="item">{{ item }}</li>
          </ul>
        </el-card>
      </div>
      <div>
        <el-card shadow="never">
          <template #header>未完成 / 待人工确认</template>
          <ul class="ys-progress__list">
            <li v-for="item in todoItems" :key="item">{{ item }}</li>
          </ul>
        </el-card>
      </div>
    </div>

    <p class="ys-muted">
      「页面已存在」不等于「已通过阶段验收」。完成标准见任务书 19.3：页面可操作、API 可访问、数据持久化、
      权限生效、状态迁移正确、异常处理明确、关键操作可审计、自动化测试实际执行、文档已更新。
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiError } from '@/api/http'
import { identityApi } from '@/api/identity'
import { integrationApi } from '@/api/modules'
import type { MenuNode, OutboxHealth, PermissionGroup } from '@/types/models'

interface Counter {
  key: string
  label: string
  value: number | string
  hint: string
}

interface StageRow {
  stage: string
  scope: string
  status: string
  note: string
}

const loading = ref(false)
const errorMessage = ref('')
const counters = ref<Counter[]>([])
const outboxFailed = ref<number | null>(null)

const stages: StageRow[] = [
  {
    stage: '0',
    scope: '仓库检查、需求追踪矩阵、架构与数据模型文档、环境与部署编排',
    status: '已完成',
    note: '前后端与 MySQL 可启动；Docker 编排文件已编写但当前环境未启动 Docker，因此未验证。',
  },
  {
    stage: '1',
    scope: '登录、权限、组织、服饰主数据、仓库储位、基础审批、审计与后台界面',
    status: '已完成',
    note: '阶段验收需人工确认；自动化测试已实际执行，结果见 docs/test-report.md。',
  },
  {
    stage: '2',
    scope: '客户、供应商、采购、销售、WMS 单据',
    status: '已完成',
    note: '客户与供应商主数据、统一库存服务（余额/流水/单据/质量放行）、采购（申请→订单→收货→来料检验放行）、销售（订单→占用→发货→退货检验）均已落地。剩余：寻源报价评分、跨仓调拨在途与盘点、应收/收付款登记。',
  },
  {
    stage: '3',
    scope: 'BOM、工艺、MRP、MES、QMS',
    status: '进行中',
    note: 'BOM 与工艺路线版本快照、MRP（净算 / 缺料建议 / 采购建议转草稿采购申请）已完成；MES 工单与报工、QMS 检验单未开始。',
  },
  {
    stage: '4',
    scope: '设备、备件、保养、点检、维修',
    status: '未开始',
    note: '备件库存复用共享库存能力，不再重复建库存体系。',
  },
  {
    stage: '5',
    scope: '采集、EMS、能源报表与告警',
    status: '未开始',
    note: '模拟采集器与真实硬件接入均在本阶段实施。',
  },
  {
    stage: '6',
    scope: 'CRM 深化、EHS、厂内物流、工业终端安全',
    status: '未开始',
    note: '',
  },
  {
    stage: '7',
    scope: '综合报表、基础成本深化、性能、安全、运维与恢复演练',
    status: '未开始',
    note: '',
  },
]

const doneItems: string[] = [
  '自定义用户模型（首次迁移即生效）、Argon2 密码哈希、登录限流与失败锁定',
  '会话登录、CSRF 校验、退出登录使服务端会话失效、修改本人密码',
  '角色、权限点、菜单、数据范围四层权限，含并集与最宽范围合并规则',
  '公司、部门（树）、工厂、车间、线体、工位、员工、班次、班组与班组人员快照',
  '颜色、尺码、款式、物料分类、物料（含面料属性）、计量单位、SKU 与 SKU 批量生成',
  '仓库、库区、储位主数据与仓储树查询',
  '审批模板（顺序多级、金额与部门条件路由）与审批实例（提交/通过/驳回/撤回/意见）',
  '编码规则与编号预演、数据字典、附件上传下载（含魔数与权限校验）',
  '审计日志（只写不改）与内部协同发件箱（至少一次投递、人工重放）',
  '工作台指标、我的待办/我的申请、用户与角色管理、权限与菜单查询页面',
  'bootstrap_system 与 seed_demo 管理命令（幂等、生产环境保护）',
  '阶段 2：客户与供应商主数据、统一库存服务（余额/流水/单据/质量放行/幂等/并发安全）',
  '阶段 2：采购模块（申请→审批→订单→收货→待检→来料检验放行，不允许超收）',
  '阶段 2：销售模块（订单→审批→库存占用→发货出库→退货→检验判定，必须先占用）',
  '阶段 3：BOM 与工艺路线版本化（审批后冻结、变更只能派生新版本、快照输出）',
  '阶段 3：MRP（时间分段净算、多层 BOM 展开、缺料清单、采购建议转草稿采购申请）',
]

const todoItems: string[] = [
  '阶段 1 的最终人工验收签字（自动化测试已执行，验收结论未出具）',
  'Docker Compose 编排未在本机启动验证（当前环境 Docker 守护进程不可达）',
  'Celery worker / beat 未实际运行验证（代码与配置已就绪）',
  'Playwright 端到端测试未执行',
  '本机 MySQL 为 8.0.17、Redis 为 3.2，与任务书要求的 MySQL 8.4 / 新版 Redis 存在版本差异',
  '开发环境使用 PyMySQL 驱动（本机无 C 编译工具链），Docker 镜像仍以 mysqlclient 为目标但未验证',
  'MRP 未做：采购提前期与批量规则、安全库存、在制供给（依赖 MES）、替代料展开、',
  '　除销售订单外的需求来源、生产建议转 MES 工单、MRP 导出与定时重算、MRP 成本卷算',
  'MES 工单与报工、QMS 检验单未开始；跨仓调拨在途、盘点范围冻结未开始',
  'Outbox 事件仍为 pending（Celery worker / beat 未启动，未验证消费侧）',
]

function statusTag(status: string): 'success' | 'info' | 'warning' {
  if (status === '已完成') {
    return 'success'
  }
  if (status === '进行中') {
    return 'warning'
  }
  return 'info'
}

function countMenus(nodes: MenuNode[]): number {
  let total = 0
  for (const node of nodes) {
    total += 1
    if (node.children && node.children.length > 0) {
      total += countMenus(node.children)
    }
  }
  return total
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [groups, menus] = await Promise.all([
      identityApi.permissionGroups(),
      identityApi.menuTree(),
    ])
    const permissionCount = sumPermissions(groups)
    counters.value = [
      {
        key: 'permissions',
        label: '已登记权限点',
        value: permissionCount,
        hint: '由 permissions_registry 统一登记，启动检查校验代码中声明的编码',
      },
      {
        key: 'modules',
        label: '涉及业务模块',
        value: groups.length,
        hint: '权限点按模块分组后的数量',
      },
      {
        key: 'menus',
        label: '已登记菜单',
        value: countMenus(menus),
        hint: '含目录与页面；组件路径必须与前端文件一一对应',
      },
      {
        key: 'outbox',
        label: '发件箱失败待处理',
        value: outboxFailed.value === null ? '无权限' : outboxFailed.value,
        hint: '失败与超限事件合计；无 integration.outbox.view 权限时不返回',
      },
    ]
  } catch (error) {
    errorMessage.value = error instanceof ApiError ? error.message : '加载实施进度计数失败'
  } finally {
    loading.value = false
  }
}

function sumPermissions(groups: PermissionGroup[]): number {
  return groups.reduce((sum, group) => sum + group.permissions.length, 0)
}

onMounted(async () => {
  try {
    const health: OutboxHealth = await integrationApi.outboxHealth()
    outboxFailed.value = health.failed + health.dead
  } catch {
    outboxFailed.value = null
  }
  await load()
})
</script>

<style scoped>
.ys-progress__notice {
  margin-bottom: 12px;
}

.ys-progress__list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.9;
  color: var(--ys-gray-700);
}
</style>