# 业务闭环设计（docs/business-flows.md）

> 本文件描述任务书第十二章要求的**五条必须打通的业务闭环**，以及每条闭环的**当前实现状态**。
> 阶段 0/1 只实现了这些闭环的**平台基座**（权限、审批、审计、主数据、单据关系），
> 业务单据本身在阶段 2–6 落地。

## 通用机制：单据关系（`integration.DocumentLink`）

所有跨模块链路依赖统一的关系表，避免各模块各自发明关联方式：

```text
source_type / source_id / source_no   源单据
target_type / target_id / target_no   目标单据
relation                              关系类型（derived/fulfilled/consumed/reworked/...）
quantity                              该关系涉及的**数量**（Decimal）
+ uq_document_link 唯一约束
```

这样「从订单查看所有关联单据与数量」（任务书 12.1）成为一次查询，
而不是每个模块写一套 join 逻辑。**数量放在关系上**，使部分满足、分批执行可被准确表达。

## 12.1 订单到交付

```text
客户 → 销售订单 → MRP → 采购/生产建议 → 正式采购单/工单
     → 到货及检验 → 合格库存 → 生产领料 → 工序报工
     → 成品检验 → 成品入库 → 销售发货
```

**验收要求**：可从订单查看所有关联单据与数量。

**设计要点**：

- 销售订单与派生生产需求**不得重复计算**（`docs/data-model.md` / MRP 规则）。
- 实物到货、库存记账与质量放行是**三个不同动作**：
  到货 ≠ 可入库，入库 ≠ 可放行。避免重复增加库存。
- 销售退货**先验收**再决定质量状态。

**当前状态**：基座已就绪（`DocumentLink` 表、审批、审计、主数据、仓库储位）。
**MRP 段已打通**（阶段 3 第二步，`apps/planning/mrp.py`，用例见 `tests/test_mrp.py`，真实链路见 `docs/test-report.md` §16.5）：

```text
SalesOrder(approved 未发货) --run_mrp--> MrpRun + MrpDemandLine（含 BOM 展开）+ MrpSupplyLine
  --> MrpSuggestion(purchase) --convert_suggestion--> PurchaseRequisition(draft)  ← 只到草稿，仍走采购审批
  --> MrpSuggestion(production) --convert_suggestion--> ProductionOrder(draft)  ← 只到草稿，下达仍需生产角色确认
```

MRP 的口径：需求来源为销售订单未发货数量；供给只认**可用库存**（`on_hand − frozen − reserved`，且只认合格质量状态）
与**采购未收货在途**；展开按生效版本 BOM 的含损耗用量（`gross_quantity`），同一物料按低层码只净算一次；
**在制供给取 MES 已下达 / 生产中工单的未完工数量**（阶段 3 第三步起，草稿工单不计入）。

**采购侧已打通**（阶段 2 第三步，`apps/procurement/services.py`，端到端用例见 `tests/test_procurement.py`）：

```text
PurchaseRequisition(draft) --submit--> 审批 --> approved
  --convert--> PurchaseOrder(draft) --submit--> 审批 --> approved
  --GoodsReceipt.create--> (draft) --post--> 库存 quarantine + 订单行 received_quantity
  --inspect(qualified)--> 库存 qualified（可领用 / 可销售）
  --inspect(rejected) --> 库存 rejected（留在仓内，不可动用；退货走库存出库，尚未实现）
```

数量口径：订单行的 `quantity - received_quantity - 草稿收货量` 是可收上限，**不允许超收**；
订单状态随收货推进 `approved → partially_received → received`，未收完可 `close`。
来料检验是**人工录入判定**（未接入检测设备），结论、判定人、说明与依据单据一并留痕。

**销售侧已打通到「发货出库 + 退货检验」**（阶段 2 第四步，`apps/sales/services.py`，
端到端用例见 `tests/test_sales.py`）：

```text
SalesOrder(draft) --submit--> 审批 --> approved
  --reserve--> StockReservation(active)  占用只减可用量，不动实存量
  --SalesShipment.create--> (draft) --post--> 库存 qualified 出库 + 订单行 shipped_quantity
  --SalesReturn.create--> (draft) --post--> 库存 quarantine（先验收，不可直接再销售）
  --inspect(qualified)--> 库存 qualified（可再销售）
  --inspect(rejected) --> 库存 rejected（留在仓内，不可动用）
```

数量口径：发货上限 = 订单行 `quantity - shipped_quantity`，且**出库数量必须由本订单的占用覆盖**
（`RESERVATION_REQUIRED`，未占用不允许发货，也不会挪用其他订单的占用）；
可退数量 = 已发货 − 已退货，超出即 `OVER_RETURN`；退货行留空的储位/批次/卷号
**继承原发货出库单据**并写回退货行，检验放行复用同一维度，批次追溯不断链。

占用口径：占用**不写库存流水**（流水只记实存量增减），一致性口径为
`InventoryBalance.reserved == 该维度未结占用之和`，详见 `docs/inventory-rules.md` 第十节。

**工程数据（BOM / 工艺路线）已就绪**（阶段 3 第一步，`apps/planning`，用例见 `tests/test_planning.py`）：

```text
Bom(draft) --submit--> 审批 --> approved（同「款式/SKU 范围」旧版本自动 obsolete）
Routing(draft) --submit--> 审批 --> approved
  --new-version--> v2 草稿（复制明细 / 工序；v1 内容与快照保持不变）
```

- MRP 用 `services.get_effective_bom(company, style, sku)` 取**唯一生效版本**展开多层 BOM，
  用料数量取 `BomLine.gross_quantity`（净用量 ×(1+损耗率)，后端按 6 位小数 `ROUND_HALF_UP` 舍入）。
- MES 工单下达时保存 `build_bom_snapshot()` / `build_routing_snapshot()` 的结果，
  并把工艺路线中 `is_quality_gate=True` 的工序作为**质检点**交给 QMS。
- 工艺路线的默认工艺（裁剪 → 缝制 → 整烫 → 检验 → 包装）已在种子里生效，「检验」即质检点。

**生产领料 / 工序报工 / 成品入库已打通**（阶段 3 第三步，`apps/mes`）；
质量侧的**检验能力**（QMS）也已可用——检验项目、检验单与结果自动判定、
不合格自动报警、质量问题知识库均已落地，且**质检点已接到工艺路线上**：
工序报满时自动开一张 QMS 检验单（详见 §十六）。因此「订单到交付」端到端链路已打通（见 §十六）；
仍未实现的是裁剪任务 / 分派到工位 / 在制品转移与扫码控制硬件等环节。

任务书 12.1 的「可从订单查看所有关联单据与数量」已由
`GET /api/v1/sales/orders/{id}/chain/` 提供（返回订单行交付进度、发货单、退货单与关联库存单据）。

## 12.2 设备维修

```text
告警或点检异常 → 报修 → 派工 → 备件领用 → 维修 → 验收 → 关闭
```

**验收要求**：设备停机、备件库存和维修记录一致。

**设计要点**：

- 备件领用**经由统一库存服务**，不直接改库存。
- 告警与工单**去重**，避免同一故障重复开工单。
- 设备档案与点检、保养、维修共用一套设备主数据。

**当前状态**：**已实现**（`apps/equipment`）。实际落地为
「报修 → 派工生成维修任务 → 开始维修 → 完成维修（填故障原因 / 措施 / 停机时长）」，
维修完成时生成维修记录并自动关闭来源报修单；点巡检发现异常可**一键转报修**，
`equipment.abnormal-*` 覆盖异常分级与处置。备件领用**仍走统一库存服务**（`wms`），
设备模块**不直接扣库存**，维修记录里的「领用备件说明」只是文字留痕。
用例见 `backend/tests/test_equipment_api.py::test_fault_report_dispatch_and_repair_completion_closes_report`。

## 12.3 能源告警

```text
采集 → 校验 → 汇总 → 阈值判断 → 报警 → 确认 → 处理 → 关闭
```

**验收要求**：告警可确认、处理、关闭，且不重复产生。

**设计要点**：见 `docs/energy-calculation.md`（计量规则、去重、离线判定、模拟标识）。

**当前状态**：**已实现**（`apps/ems` + `apps/iot`）。报警来源有两条：人工抄表 / 离线扫描（`ems`），
以及数采测点越限与数采设备离线（`iot`）。两条来源**统一调用** `apps/ems/services.py::raise_alarm`
写入同一张能源报警台账，`source_ref` 记录来源测点，使去重窗口细化为
「同仪表 + 同类型 + 同来源 + 同一天」；报警的「处理 → 关闭」走动作接口，关闭必须写处理说明。
用例见 `test_ems_api.py::test_over_limit_alarm_is_raised_once_per_day`、
`test_iot_api.py::test_over_limit_creates_one_alarm_per_point`。

## 12.4 客诉改善

```text
投诉 → 批次追溯 → 调查 → 纠正措施 → 验证 → 知识库 → 客户反馈
```

**验收要求**：投诉可关联 SKU、订单、批次与质量记录，形成可追溯闭环。

**设计要点**：

- 投诉流程状态机：登记 → 分派 → 调查 → 处理 → 反馈 → 关闭。
- **平台使用评价与产品质量评价分开**，不混为一个评分。
- 追溯依赖 `masterdata.Identifier`（批次码/卷号/箱码分型）与 `DocumentLink`。

**当前状态**：**已实现（首版）**（`apps/crm`）。实际落地为
「投诉登记 → 受理 → 处理（填处理措施）→ 关闭」，关闭后登记满意度（0 = 未评价，1~5 = 评分）；
产品评价与**平台使用评价分开**：`ProductReview` 记录客户对产品的评分（1~5）与官方回复，
`CustomerComplaint.satisfaction` 记录客户对投诉处理结果的满意度，两者不混为一个分数。
主数据侧的**标识分型**（`masterdata.Identifier`）仍为批次追溯的载体。
**未做**：投诉外部渠道（电话 / 网站在线表单）自动接入、投诉自动分派、
按批次 / 订单 / 质量记录的一键追溯与投诉统计报表。
用例见 `backend/tests/test_crm_api.py::test_complaint_full_lifecycle_writes_audit`。

## 12.5 安全整改

```text
隐患 → 责任分派 → 整改 → 证据 → 复查 → 关闭
```

**验收要求**：复查不合格可退回整改，超期提醒留痕。

**设计要点**：

- 隐患流程：上报 → 分级 → 分派 → 整改 → 复查 → 关闭。
- 附件作为整改证据，走 `core.Attachment`（对象存储私有 + 权限校验）。
- 超期提醒走通知与后台任务。

**当前状态**：**已实现**（`apps/ehs` 的隐患流程）。实际落地为
「上报（待整改）→ 整改（填写整改措施）→ 提交验收 → 验收」，
**验收不通过退回「整改中」**，不允许把不合格隐患直接销账；每次流转写 `EhsOperationLog`。
附件（整改证据）走 `core.Attachment`，超期提醒走通知与后台任务（**未接入调度器**）。
用例见 `backend/tests/test_ehs_api.py::test_hazard_rectify_verify_loop`。

## 十三、设备保养与维修闭环（阶段 4，本轮实现）

```text
设备台账 → 保养项目 → 保养计划 ──生成到期任务──> 保养任务 ──开始/完成──> 保养记录
                                        └─────────> 推进下次保养日期

点巡检任务 → 点巡检记录（发现异常）──转报修──> 故障报修单 ──派工──> 维修任务 ──完成──> 维修记录
                                                                          └──> 报修单自动关闭
```

**验收要求**：

- 同一计划同一天只生成一条任务（重复点「生成到期任务」不重复）；生成后 `next_date` 前移一个周期。
- 保养 / 维修任务完成时，**在同一事务内**生成对应记录；维修完成同时把来源报修单推进到「已关闭」。
- 点巡检记录标为异常后，可以一键转成报修单，形成「发现 → 报修 → 维修」闭环。
- 备件消耗只登记在记录里（`parts_used`），**不直接改库存**；真正扣减要经仓储的库存单据。

**设计要点**：

- 状态只能由服务层推进（任务 `status` 在序列化器里只读），跳步 / 逆序一律 `409`。
- 编号按编码规则取号（`MP` / `MT` / `MR` / `FR` / `RT` / `RR` / `IT` / `IR` / `AT` / `AR`）。
- 公司由服务端从当前用户推导，前端不传 `company_id`；越权写返回 `OUT_OF_DATA_SCOPE`。

**当前状态**：**已实现**（`apps/equipment`）。

## 十四、能源计量与报警闭环（阶段 5，本轮实现）

```text
计量区域 / 计量设备 / 价格 / 阈值（基础管理）
        │
        ├──抄表──> 抄表读数 ──评估阈值──> 越限报警
        ├──运行记录 开始/结束──> 运行时长 · 能耗 · 单耗 ──单耗超阈值──> 单耗报警
        └──离线扫描（抄表超时）──> 离线报警 + 仪表置为离线

抄表读数 ──按维度聚合──> 能源首页 / 设备监控 / 能源看板 / 能耗统计 / 能耗报表（可导出 Excel）
                              └── 按「介质 + 时段 + 生效区间」解析单价 → 费用
```

**验收要求**：

- 报警必须由**真实路径**触发（抄表写入 / 运行结束 / 离线扫描），不允许「点一下页面才生成报警」。
- 同仪表同类型同一天去重，跨天重新报警；关闭报警必须写处理说明。
- 未维护单价时费用记 0 并明确标记「未维护单价」，**不猜价格**。
- 报表导出的 xlsx 由 openpyxl 真实生成（不是改后缀的 CSV），并把导出行为写入审计日志。

**设计要点**：

- 统计 / 报表 / 首页 / 看板都是**只读聚合**，直接读抄表明细，不读汇总缓存（避免口径漂移）。
- 用水 / 用电 / 用气 / 用液四条菜单共用同一聚合接口，只固定 `medium` 参数。
- 详见 `docs/energy-calculation.md`。

**当前状态**：**已实现**（`apps/ems`）。**人工抄表与 HTTP 数采并行**：`ems` 的仪表在线 / 离线
仍是抄表超时推断，数采设备另有一套基于 `last_seen_at` 的在线状态；数采读数**不写抄表**，
只把越限 / 离线报警写入同一报警台账（见 §十五）。


## 十五、设备数采闭环（阶段 5 首版，本轮实现）

```text
连接配置（协议 / 地址 / 限流 / 批次上限）
        │
        └── 数采设备（网关 / 传感器 / 水表 / 电表）── 下发设备令牌（明文只显示一次）
                    │
                    ├── 测点（物理量 / 单位 / 精度 / 越限上下限）
                    │
            设备 POST /api/v1/iot/ingest/（X-Device-Token）
                    │
                    ├── 限流 / 批次上限不足 ──> 429 / 400（不静默丢弃）
                    ├── 消息 ID 重复 ──> 记 `duplicated` 报文，不再入账
                    └── 逐点入账 ──> 标准化读数（测点 + 设备时间唯一）
                                        ├── 越过上下限 ──> 越限报警（ems 报警台账）
                                        └── 关联能源仪表 ──> 仅作对照线索，**不写抄表**

设备监控（在线 / 离线 / 未知、近 24h 读数与失败报文、测点最新读数与超限标记）
后台扫描 `manage.py iot_offline_check` ──> 离线报警（**跳过模拟设备**）
```

**验收要求**：

- 设备上报**必须用设备令牌**，不复用员工登录会话；令牌轮换后旧令牌立即失效。
- 失败与重复的报文**必须留痕**，可在「采集日志」里查到原因——不允许静默丢数据。
- 模拟数据全程带「模拟」标识，**模拟设备不参与离线判定**，也不计入真实产量与能耗。
- 采集读数**不写能源抄表**，避免与人工抄表重复计量；报警统一落到能源报警台账。

**当前状态**：**已实现**（`apps/iot`，HTTP 上报 + 内置模拟器）。
**未实现**：MQTT / Modbus 协议适配（连接配置可登记，采集入口显式拒绝）、真实设备联调、
分钟 / 小时 / 日汇总表与原始数据归档清理、工业终端安全。详见 `docs/hardware-integration.md` §六。

## 十六、生产执行闭环（阶段 3 第三步，本轮实现）

```text
生产建议 --convert_suggestion--> ProductionOrder(draft)      手工建单也可 draft
        │
        └── release（下达）
                ├── 取生效 BOM / 工艺路线 → 冻结快照 bom_snapshot / routing_snapshot
                ├── 沿 BOM 展开工单用料（含损耗用量）
                └── 沿工艺路线生成工单工序（记录 is_quality_gate）
        │
        ├── issue-materials（领料）→ 经统一库存服务过账出库单（issue_document）
        │
        ├── report（报工）───合格 + 返工 + 报废 = 报工量（守恒），同一工序累计不得超计划
        │                 └── 质检点工序报满 → 自动开 QMS 检验单（QUALITY_GATE）
        │
        ├── complete（完工）─── 要求全部工序完成、全部质检点已判定合格 / 让步接收
        │
        ├── receipt（完工入库）→ 经统一库存服务过账入库单（receipt_document，待检 / 合格）
        │
        └── close（关闭）/ cancel（取消，必填原因）
```

**验收要求**：

- 工单下达即冻结 BOM / 工艺快照，之后工程数据出新版本**不影响已下达工单**（任务书 9.5、14.2 案例 13）。
- 报工**守恒**：单次报工「合格 + 返工 + 报废 = 报工量」，同一工序累计报工不得超计划；
  报工**不可回改**，填错了补一条返工报工。
- **库存只能经统一库存服务**：领料与完工入库均生成并过账 `wms` 库存单据，MES 不写库存余额；
  重复提交靠 `Idempotency-Key` 保平，已领 / 已入库再次请求会被拒绝。
- **质检点是硬门槛**：质检点工序报满自动开 QMS 检验单；
  工单完工前，全部质检点的检验单必须已判定为「合格」或「让步接收」，否则 `QUALITY_GATE_NOT_PASSED`。
- 非草稿工单的**表头字段冻结**：`PATCH` 返回 **409 `STATE_CONFLICT`**（只能改草稿）。

**当前状态**：**已实现**（`apps/mes`，4 张表，32 条用例）。
**未实现**：线体排产、裁剪任务 / 裁片批次、工位派工、在制品转移、报工扫码 / RFID 控制硬件、
按工序核算良率 / OEE。详见 `docs/requirements-matrix.md` §10.7 与 `docs/test-report.md` §三十一。

## 附：通用流程能力（阶段 1 已实现）

| 能力 | 实现位置 | 说明 |
| --- | --- | --- |
| 顺序多级审批 | `workflow.ApprovalTemplateNode.seq` | 按 `seq` 顺序推进，`current_seq` 记录当前节点 |
| 条件路由 | `amount_min/amount_max`、`department_ids` | 按金额区间与部门条件匹配审批人 |
| 模板版本快照 | `ApprovalInstance.template_version` + `template_snapshot` | 模板后续修改**不影响**在途单据 |
| 提交/通过/驳回/撤回 | `workflow` 服务层动作接口 | 每次动作写 `ApprovalLog`，只写不改 |
| 审批意见与代理 | `ApprovalStep.comment`、`allow_self_approval` | 代理审批需显式授权并留痕；可限制申请人审批自己的单据 |
| 审批轨迹 | `ApprovalLog` | 前端展示「审批轨迹」 |
| 待办/我的申请/参与 | `workflow/instances/{todo,mine,participated,pending-summary}/` | 基于**单次组合 `Q()` 过滤**，避免多 join 泄露范围外数据 |

**重要边界**：**审批通过与库存过账是两个不同动作**，不混为一谈
（审批通过不代表库存已变动，反之亦然）。
