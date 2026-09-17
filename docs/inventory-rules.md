# 库存规则（docs/inventory-rules.md）

> **状态：核心已实现（阶段 2 增量）。** 本文件是库存服务的强制契约，已按本文落地代码：
>
> - 服务：`backend/apps/wms/services/stock.py`
> - 模型：`backend/apps/wms/models/inventory.py`（迁移 `wms/0002`）
> - 测试：`backend/tests/test_wms_inventory.py`（36 个用例，含真实并发用例）
>
> 任何模块不得绕过统一库存服务直接改库存。
> **尚未实现**：跨仓调拨在途状态、盘点范围冻结、库位推荐、标签打印（见 §八）。

## 一、库存维度

```text
公司 company + 物料/SKU material + 仓库 warehouse + 储位 location
+ 批次 batch_no + 卷号 roll_no + 质量状态 quality_status
```

### 规范化维度键（防重关键）

上述维度中 `batch_no`、`roll_no` 可为空。MySQL 唯一索引**不把两个 NULL 视为相等**，
若直接建多列联合唯一索引，会出现重复余额行。因此：

- 余额表增加 `dimension_key CHAR(64) NOT NULL UNIQUE`；
- 由库存服务按 `sha256(company|material|warehouse|location|normalize(batch)|normalize(roll)|normalize(quality))[:32]` 生成；
- `normalize(None)` 与 `normalize("")` 一律编码为占位符 `"-"`，使「无批次无卷号」成为**确定的一个值**；
- 可读维度列仍保留（可空），但**唯一起作用的是 `dimension_key`**。

详见 `docs/data-model.md` 第六节。

## 二、唯一入口与分层

- **所有库存变更必须经由统一库存服务**（已落在 `backend/apps/wms/services/stock.py`）。
- 服务负责：权限校验 → 加锁 → 事务内更新余额 + 写流水 → 写审计 → 返回结果。
- 其他模块（采购、销售、生产、备件）**只调用该服务**，不直接写库存表。
- 库存流水为**只追加**记录，不提供普通业务接口的修改与删除。

## 三、数量口径（必须区分）

| 口径 | 含义 | 说明 |
| --- | --- | --- |
| 实存量 `on_hand` | 物理在库数量 | 由收发存操作增减 |
| 冻结量 `frozen` | 因盘点/质检/隔离等原因不可动用的部分 | 与「占用」互斥 |
| 占用量 `reserved` | 已被具体单据（销售订单、工单）预留的部分 | 与「冻结」互斥 |
| 可用量 `available` | `on_hand - frozen - reserved` | 可被新的需求使用 |

### 冻结与占用的交叉规则（必须避免重复扣减）

1. 同一数量**不得同时计入**冻结与占用。二者是**互斥数量桶**，不是两个独立减法项。
2. 状态迁移时做**结转**而非叠加：例如质检不合格 → 冻结，
   若该批已存在占用，必须先释放占用再转入冻结，二者之和不超过 `on_hand`。
3. 每次结转都在流水上记录**原因、来源单据、操作人**，保证任意时点的
   `on_hand = 可用 + 冻结 + 占用 + 在途锁定` 可核对。
4. 首版采用**互斥数量桶 + 可追溯分配**的混合口径：
   桶用于汇总校验，分配记录（哪张单据占了哪条余额的多少）用于精确释放。
   该口径写入本文件并在阶段 2 通过并发测试验证。

## 四、硬性规则

1. **统一库存服务**：不允许旁路。
2. **默认禁止负库存**。仓库级 `allow_negative_stock` 默认 false，开启需显式授权并留痕；
   即使开启，也必须有明确的授权依据与审计记录。
3. **待检、不合格库存不能直接领用或销售**：只能通过质量放行改变 `quality_status` 后才可动用。
4. **所有变更生成流水**：数量、维度、前后状态、单据来源、操作人、时间、幂等键。
5. **调拨发出后进入在途**，**不立即计入目标可用库存**；目标仓收货确认后才转为可用。
6. **盘点需处理盘点期间移动**：首版采用**明确的范围冻结方案**（盘点范围内库存冻结变动），
   并在盘点单上标注冻结范围与时长。
7. **冲销不能忽略下游已消耗事实**：若原单据的库存已被下游消耗，不满足冲销条件时**拒绝**，
   并引导用户走退货或更正流程，不做「强行反冲」。

## 五、事务与并发实现要求

```text
1. 先检查操作权限（require_codes）
2. 再锁定需要更新的数据（select_for_update）
3. 按【固定顺序】获取多个库存键的锁（如按 dimension_key 排序），降低死锁风险
4. 在锁内【重新校验】单据状态与可用数量
5. 同一事务内更新【单据 + 余额 + 流水】（并写审计与 Outbox）
6. 提交成功后才对外返回成功
```

关键点：

- 对**尚不存在的余额行**，`select_for_update()` 不提供任何锁保护。
  必须使用「唯一约束 + 并发安全创建」：先查后插，捕获 `IntegrityError` 后回滚保存点重查并加锁。
- 死锁与锁超时**有限重试**，重试必须**重跑完整事务**且**幂等**。
- 幂等键与业务结果**同事务提交**，确保「重复过账不重复扣库存」。

## 六、必测案例（阶段 2 验收门槛）

| 序号 | 案例 | 断言 |
| --- | --- | --- |
| 5 | 重复过账不重复扣库存 | 同一 `Idempotency-Key` 两次过账，余额只减一次 |
| 6 | 并发出库不产生负库存 | N 个并发请求超额出库，成功数 ≤ 可用量，且无负余额 |
| 7 | 新库存余额行并发创建不重复 | 并发创建同一维度，最终**只有一行** |
| 8 | 死锁重试不重复生成单据 | 注入死锁后重试，单据数不变 |
| 9 | 不合格库存不可发货 | 不合格质量状态库存出库被拒 |
| 10 | 已消耗库存不能任意冲销 | 下游已消耗时冲销被拒并给出引导 |
| 11 | 调拨数量守恒 | 发出 + 在途 + 接收 = 原总量，无凭空增减 |

> 并发用例必须使用**真实独立事务与独立数据库连接**，不能依赖测试框架的外层事务掩盖问题
> （任务书 14.2 明确要求）。

## 七、成本口径（阶段 7 深化，此处仅声明边界）

- 库存计价首版可采用**移动加权平均**，但必须**独立保存数量流水与价值流水**。
- 退货冲销必须正确处理成本回转。
- 明确成本范围与会计系统的差异：本平台提供的是**管理用参考成本**，
  **不得描述为已完成完整财务核算**（任务书 2.3.1、10.16）。
- 区分标准成本、实际归集成本、估算分摊成本，报表中不得混用同一名称。
## 八、实现状态对照（阶段 2 增量，如实记录）

### 已实现（可通过 `backend/tests/test_wms_inventory.py` 复现）

| 项 | 实现位置 | 说明 |
| --- | --- | --- |
| 统一库存服务 | `apps/wms/services/stock.py` | `create_document` / `update_draft_document` / `post_document` / `reverse_document` / `release_quality` / `allocate_document_no` |
| 规范化维度键 | `apps/wms/models/inventory.py::build_dimension_key` | 单列 `UNIQUE NOT NULL`，空值编码为 `"-"` |
| 四类数量桶 | `InventoryBalance.on_hand/frozen/reserved` + `available` 计算属性 | 检查约束保证 `frozen + reserved <= on_hand` 且三者非负 |
| 只追加流水 | `InventoryTransaction` | 非 `BaseModel`；`save()` 抛 `ImmutableLedgerError`，`delete()` 永远抛异常 |
| 单据状态机 | `InventoryDocument` | `draft → posted → reversed`；已过账不可编辑（服务层拒绝） |
| 默认禁止负库存 | `_assert_available` | 服务层**始终**拒绝导致负库存的出库；DB 检查约束为第二道硬墙 |
| 待检/不合格不可领用或销售 | `_assert_quality_allowed` | `ISSUE` 类单据要求 `quality_status = qualified` |
| 质量放行 | `release_quality` | 生成并过账一张 `QUALITY` 单据，改变 `quality_status` |
| 幂等 | `post_document` | 幂等键与业务同事务提交；同键同内容返回原单据、同键不同单据冲突 |
| 死锁重试 | `_is_retryable` / `MAX_LOCK_RETRIES` | 仅 1213 / 1205 重试，重跑完整事务；非重试错误不重试 |
| 审计 | `_record_document_audit` | 过账 `AuditAction.POST`、冲销 `AuditAction.REVERSE`，与业务同事务 |
| Outbox | `publish_event` | 事件与业务同事务写入（死锁注入点即在此，用于测试重试幂等） |

### 必测案例对照（任务书 14.2）

| 序号 | 结果 | 证据 |
| --- | --- | --- |
| 5 重复过账不重复扣库存 | **已通过** | `test_same_idempotency_key_posts_once`、`test_api_idempotency_key_deducts_once` |
| 6 并发出库不产生负库存 | **已通过** | `test_concurrent_issue_never_produces_negative_stock`（4 并发出库只成功 2 个，余下报 `InsufficientStock`） |
| 7 新余额行并发创建不重复 | **已通过** | `test_concurrent_balance_creation_yields_single_row`（3 并发入库 → 1 行余额、3 条流水） |
| 8 死锁重试不重复生成单据 | **已通过** | `test_deadlock_retry_does_not_duplicate_ledger`（monkeypatch 注入 MySQL 1213）、`test_non_retryable_error_is_not_retried` |
| 9 不合格库存不可发货 | **已通过** | `test_rejected_stock_cannot_be_issued`、`test_quarantine_stock_cannot_be_issued` |
| 10 已消耗库存不能任意冲销 | **已通过** | `test_reversal_blocked_when_stock_consumed`、`test_reversal_succeeds_after_stock_returned` |
| 11 调拨数量守恒（同仓移库） | **已通过** | `test_concurrent_transfer_keeps_total`、`test_move_conserves_quantity` |
| 11 调拨数量守恒（跨仓在途） | **未执行** | 跨仓调拨尚未实现；当前代码拒绝跨仓（`test_move_to_other_warehouse_is_rejected`） |

### 明确未实现（不得视为完成）

1. **跨仓调拨与在途状态**：当前 `move` 类型仅支持**同仓移库**，`_assert_locations_in_warehouse` 会拒绝跨仓；
   「发出后进入在途、目标仓确认后才转可用」尚未建模。
   必测案例 11 的**同仓移库守恒**部分已通过；**跨仓在途**部分**未执行**。
2. **盘点与范围冻结**：`adjustment` 类型已可用于调整，但盘点单、盘点范围内冻结变动、
   差异审批流程尚未实现。
3. **冻结/解冻与占用/释放的业务入口**：数量桶已建模并有约束，但尚无 `freeze`/`unfreeze`/`reserve`/`release`
   业务服务动作（需由销售订单、工单等调用方驱动，属阶段 2 后续与阶段 3）。
4. **库位推荐与标签打印**：未实现。
5. **库存成本**：`InventoryBalance` 只保存**数量**，未保存金额；移动加权平均属阶段 7 深化。
6. **`allow_negative_stock` 开关**：已建模为仓库字段，但服务层**不考虑**该开关，始终拒绝负库存。
   若后续要支持，必须补充显式授权与审计，不能仅靠字段放行。

## 九、调用方对照：采购模块（阶段 2 采购增量）

采购模块是**第一个接入统一库存服务的业务模块**，可作为后续销售/生产接入的样板。

| 业务动作 | 调用的库存服务 | 结果 |
| --- | --- | --- |
| 采购收货过账 | `stock.create_document(type=receipt)` + `post_document` | 本批次变为 `quarantine`；`GoodsReceipt.receipt_document_id` 记录单据 |
| 来料检验判定 | `stock.release_quality(from=quarantine, to=qualified / rejected)` | 生成并过账一张 `QUALITY` 单；`GoodsReceipt.quality_document_id` 记录**最后一行**的放行单据 |

**采购模块不做什么**（与任务书 4.3「禁止直接跨模块修改他人业务表」一致）：

- 不直接写 `InventoryBalance` / `InventoryTransaction`（余额与流水只由库存服务产生）；
- 不在采购表上保存库存数量副本；订单的「已收数量」= 该订单行**已过账**收货量之和，
  草稿收货单只用于**额度校验**，不计入 `received_quantity`；
- 不通过 signals 或前端计算结果决定库存变化。

**多行收货单的放行**：一次检验判定会对**每一行**调用一次 `release_quality`，
服务内部幂等键按 `receipt_id + line_no` 派生，因此传入同一个外部 `Idempotency-Key` 时
不会出现「第二行被判定为重复请求而跳过」的问题（`test_multi_line_receipt_inspect_releases_every_line_once` 已固化）。
`GoodsReceipt.quality_document_id` 记录最后一次放行生成的单据，用于追溯。
