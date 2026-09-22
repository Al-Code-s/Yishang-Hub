<template>
  <div class="ys-page">
    <div class="ys-page__header">
      <div>
        <h2 class="ys-page__title">实施进度</h2>
        <p class="ys-page__description">
          本页说明平台当前已经上线哪些功能，供管理员确认「现在可以用哪些模块」。
          上半部分的计数由系统实时统计，下半部分是各阶段的功能清单，与项目文档保持一致；
          它是功能清单，不是业务报表，不参与业务统计。
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
      title="尚未实现的模块不会出现在菜单里"
    >
      质量、设备、能源、安全环保、厂内物流、工业终端安全等模块将在后续版本上线；
      在功能真正可用之前，它们不会出现在左侧导航中，也不会出现「点进去什么都没有」的空页面。
      这些模块都在本平台内部实现，不是对接外部系统。
    </el-alert>

    <el-alert v-if="errorMessage" type="error" :closable="false" show-icon :title="errorMessage" />

    <h3 class="ys-section-title">当前环境的实时计数</h3>
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

    <h3 class="ys-section-title">各阶段实施状态</h3>
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

    <h3 class="ys-section-title">已完成 / 未完成事项</h3>
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
      说明：页面上能看到某个功能，不等于它已经通过验收。本页状态来自项目文档，
      最终以人工验收结论为准；验收要求功能可操作、数据能保存、权限生效、关键操作可追溯且测试实际执行过。
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
    scope: '需求梳理、架构与数据设计、开发与部署环境搭建',
    status: '已完成',
    note: '本机已验证：数据库、服务与界面都能正常启动；容器化部署配置已编写，但尚未在容器环境实际启动验证。',
  },
  {
    stage: '1',
    scope: '登录、权限、组织、服饰基础资料、仓库储位、基础审批、操作日志与后台界面',
    status: '已完成',
    note: '阶段验收需人工确认；自动化测试已实际执行，结果记录在项目测试报告中。',
  },
  {
    stage: '2',
    scope: '客户、供应商、采购、销售、仓储单据',
    status: '已完成',
    note: '客户与供应商档案、库存（余额 / 流水 / 单据 / 质量放行）、采购（申请 → 订单 → 收货 → 来料检验放行）、销售（订单 → 占用库存 → 发货 → 退货检验）均已上线。尚未完成：供应商寻源与报价、跨仓调拨与盘点、应收与收付款登记。',
  },
  {
    stage: '3',
    scope: '用料清单、工艺路线、物料需求运算、生产执行、质量管理',
    status: '进行中',
    note: '用料清单与工艺路线的版本管理、物料需求运算（净需求计算 / 缺料清单 / 采购与生产建议转草稿单据、在制工单作为供给）、质量管理（检验项目、检验单与结果自动判定、不合格自动报警、质量问题知识库）与生产执行（工单下达、领料、报工、完工与完工入库、质检点自动开检验单）已完成；尚未完成：线体排产、裁剪任务、工位派工、在制品转移、扫码与硬件控制。',
  },
  {
    stage: '4',
    scope: '设备、备件、保养、点检、维修',
    status: '已完成',
    note: '设备台账与类型、设备零部件、备品备件与配件、故障报修、备件库存台账、保养（项目 / 计划 / 任务 / 日历 / 记录）、维修任务与记录、点巡检、异常上报均已上线。备件现存量只读自共享库存能力，不重复建库存体系；备件采购复用采购申请流程。',
  },
  {
    stage: '5',
    scope: '设备数据采集、能源计量、能源报表与告警',
    status: '进行中',
    note: '能源计量与设备数采首版已完成：计量区域与仪表、水电气液价格与阈值、抄表、设备运行记录、报警（越限 / 离线 / 单耗 / 能耗）、能源看板 / 报表 / 统计与导出；数采侧已完成连接与设备、采集测点、设备令牌、HTTP 上报与双重去重、越限 / 离线报警、设备监控与内置模拟器。尚未完成：MQTT / Modbus 协议适配与真实设备联调、采集数据的小时 / 日汇总与原始数据归档；能源数据当前仍以人工抄表为主，仪表的在线 / 离线由抄表超时推断。',
  },
  {
    stage: '6',
    scope: '客户服务深化、安全环保、厂内物流、工业终端安全',
    status: '进行中',
    note: '安全环保管理（安全制度 / 培训 / 隐患 / 应急 / 事故、排污 / 固废危废 / 环保合规、消防设施 / 演练 / 作业许可、特种设备与各类安全检查）、厂内物流（自动化设备、物流任务、操作日志）与客户服务深化（客户投诉、产品评价）已完成。尚未开始：工业终端安全。',
  },
  {
    stage: '7',
    scope: '综合报表、基础成本深化、性能、安全、运维与恢复演练',
    status: '未开始',
    note: '',
  },
]

const doneItems: string[] = [
  '账号与权限基础、密码加密存储、登录失败限流与账号锁定',
  '会话登录与安全校验、退出登录使会话失效、修改本人密码',
  '角色与权限配置（菜单、操作、数据范围），含多角色合并规则',
  '公司、部门、工厂、车间、线体、工位、员工、班次、班组',
  '颜色、尺码、款式、物料分类、物料（含面料属性）、计量单位、SKU（含批量生成）',
  '仓库、库区、储位结构与仓储层级查询',
  '审批流程配置（逐级审批、金额与部门条件）与审批办理（提交 / 通过 / 驳回 / 撤回 / 审批意见）',
  '编号规则与编号预演、数据字典、附件上传下载（含文件类型与权限校验）',
  '操作日志（只增不改）与内部协同事件（自动重试、人工重放）',
  '工作台、我的待办 / 我的申请、用户与角色管理、权限与菜单查询',
  '系统初始化与演示数据初始化命令（可重复执行，生产环境受保护）',
  '客户与供应商档案、库存管理（余额 / 流水 / 单据 / 质量放行）',
  '供应商五维量化评价（质量 / 技术 / 响应 / 交付 / 成本；权重合计必须 100%、改权重只派生新版本；缺数据可选「标注缺失」或「重新分配有效权重」；等级 A~D；只读评价统计）',
  '采购（申请 → 审批 → 订单 → 收货 → 待检 → 来料检验放行，不允许超收）',
  '销售（订单 → 审批 → 占用库存 → 发货出库 → 退货 → 检验判定，必须先占用）',
  '用料清单与工艺路线版本管理（审批后冻结，变更只能派生新版本）',
  '物料需求运算（分时段净需求、多层用料展开、缺料清单、采购与生产建议转草稿单据、在制工单作为供给）',
  '设备台账与类型、零部件、备品备件与配件、故障报修、备件库存台账（只读自库存）',
  '设备保养（项目 / 计划 / 任务 / 日历 / 记录，计划生成到期任务可重复执行不重复生成）与维修、点巡检（异常可转报修）、异常上报',
  '能源计量（区域 / 仪表 / 价格 / 阈值）、抄表、设备运行记录、报警（越限 / 离线 / 单耗 / 能耗，当天去重）与能源看板 / 报表 / 统计（可导出 Excel）',
  '自动化设备与物流任务（下发 → 执行 → 完成 / 取消，故障设备不可下发），任务与设备状态联动并留操作日志',
  '安全环保（制度 / 培训 / 隐患整改验收 / 应急预案 / 事故处理、排污监测自动判达标、固废危废、环保合规、消防设施 / 演练 / 动火作业、特种设备与安全检查）',
  '设备数采与监控（连接与设备、采集测点、设备令牌下发与轮换、HTTP 上报与报文 / 读数双重去重、越限与离线报警、采集日志、设备监控与内置模拟器）',
  '客户投诉（受理 → 处理 → 关闭 + 满意度）与产品评价（评分 1~5、回复与关闭）',
  '采集统计与客户服务统计（数采按「测点 × 时间桶」、投诉与评价按分布实时聚合，只读、不落汇总表）',
  '质量管理（检验项目与判定口径、检验单录入与提交判定关闭、定量项按标准上下限自动判定、不合格自动生成质量报警、质量问题知识库、质量动态监测）',
  '生产执行（工单下达冻结用料与工艺快照、领料与完工入库经统一库存、报工数量守恒与超产拦截、质检点自动开检验单并作为完工硬门）',
]

const todoItems: string[] = [
  '各阶段的最终人工验收签字（自动化测试已执行，验收结论尚未出具）',
  '容器化部署配置已编写，但未在真实容器环境启动验证',
  '后台任务与定时调度尚未实际运行验证（代码与配置已就绪）',
  '端到端自动化测试（Playwright）未执行',
  '本机数据库为 MySQL 8.0.17、缓存为 Redis 3.2，与任务书要求的 MySQL 8.4 / 新版 Redis 存在版本差异',
  '本机缺少编译工具链，开发环境改用纯 Python 数据库驱动；容器镜像仍按标准驱动准备，尚未验证',
  '物料需求运算尚未包含：采购提前期与批量规则、安全库存、替代料展开、',
  '　除销售订单外的需求来源、运算结果导出与定时重算、成本卷算',
  '生产执行尚未包含：线体排产、裁剪任务 / 裁片批次、工位派工、在制品转移与返工工单、扫码 / RFID 与硬件控制、工序良率与 OEE（不伪造设备运行时长）；检验标准的版本快照、返工 / 报废处置工单、检测仪器直连未做；跨仓调拨与盘点尚未开始',
  '内部协同事件仍有待处理项（后台任务未启动，消费侧未验证）',
  '设备数采尚未完成：MQTT / Modbus 协议适配与真实设备联调、原始数据的归档 / 清理（当前只有 HTTP 上报与内置模拟器，能源数据仍以人工抄表为主）',
  '统计只做「按明细现算」，没有定时快照与同环比；统计接口未做性能压测（数据量增长后需先补原始数据归档 / 清理，而不是加一张对不上账的汇总表）',
  '工业终端安全（主机资产、补丁台账等）尚未开始',
  '安全环保只是引用设备台账（只读），安全检查发现问题不会自动生成隐患单，需要人工登记',
  '能源离线报警扫描需要部署侧配置计划任务（平台没有内置调度器），当前未在部署环境配置',
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
        hint: '系统内置的权限项总数',
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
        hint: '左侧导航中的目录与页面数量',
      },
      {
        key: 'outbox',
        label: '待处理事件',
        value: outboxFailed.value === null ? '无权限' : outboxFailed.value,
        hint: '投递失败与超过重试次数的事件合计；没有相应权限时不显示',
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
