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
  --> MrpSuggestion(production) --convert_suggestion--> 明确拒绝 PRODUCTION_ORDER_NOT_IMPLEMENTED（等 MES）
```

MRP 的口径：需求来源为销售订单未发货数量；供给只认**可用库存**（`on_hand − frozen − reserved`，且只认合格质量状态）
与**采购未收货在途**；展开按生效版本 BOM 的含损耗用量（`gross_quantity`），同一物料按低层码只净算一次；
**在制供给恒为 0**（MES 未实现），**不冒充**已有在制数据。

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

**仍未打通的部分**：MRP（阶段 3）、生产领料 / 工序报工 / 成品检验 / 成品入库（阶段 3 MES + QMS）。
因此「订单到交付」整条链路仍**未打通**；但销售侧的**发货出口**与**退货入口**已经可用，
生产侧入库落地时只需调用同一库存服务，不新增第二套库存逻辑。

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

**当前状态**：**未实现**（阶段 4）。备件主数据与库存能力由共享模块（`masterdata` + `wms`）提供，
阶段 4 **不再重复创建**库存体系。

## 12.3 能源告警

```text
采集 → 校验 → 汇总 → 阈值判断 → 报警 → 确认 → 处理 → 关闭
```

**验收要求**：告警可确认、处理、关闭，且不重复产生。

**设计要点**：见 `docs/energy-calculation.md`（计量规则、去重、离线判定、模拟标识）。

**当前状态**：**未实现**（阶段 5）。阶段 0/1 未创建 `iot` / `ems` 模块，也没有任何真实硬件接入。

## 12.4 客诉改善

```text
投诉 → 批次追溯 → 调查 → 纠正措施 → 验证 → 知识库 → 客户反馈
```

**验收要求**：投诉可关联 SKU、订单、批次与质量记录，形成可追溯闭环。

**设计要点**：

- 投诉流程状态机：登记 → 分派 → 调查 → 处理 → 反馈 → 关闭。
- **平台使用评价与产品质量评价分开**，不混为一个评分。
- 追溯依赖 `masterdata.Identifier`（批次码/卷号/箱码分型）与 `DocumentLink`。

**当前状态**：主数据侧的**标识分型**已实现（`masterdata.Identifier` 支持 SKU 条码、
批次码、卷号、箱码、RFID EPC、载具码，各有唯一约束）。业务侧在阶段 2（CRM 基础）/阶段 6（深化）实现。

## 12.5 安全整改

```text
隐患 → 责任分派 → 整改 → 证据 → 复查 → 关闭
```

**验收要求**：复查不合格可退回整改，超期提醒留痕。

**设计要点**：

- 隐患流程：上报 → 分级 → 分派 → 整改 → 复查 → 关闭。
- 附件作为整改证据，走 `core.Attachment`（对象存储私有 + 权限校验）。
- 超期提醒走通知与后台任务。

**当前状态**：**未实现**（阶段 6）。审批与附件基座已就绪，可复用。

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