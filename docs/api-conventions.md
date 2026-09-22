# 接口规范（docs/api-conventions.md）

> 实现契约：`apps/core/exceptions.py`（错误结构）、`apps/core/pagination.py`（分页）、
> `config/urls.py`（前缀与路由）。**本文档描述的结构已在阶段 0/1 落地并通过测试。**

## 一、前缀与版本

- 统一前缀 `/api/v1/`，由 `YISHANG_API_PREFIX` 配置（默认 `api/v1`），不硬编码到各视图。
- 破坏性变更通过新前缀版本发布；阶段 0/1 只有 `v1`。
- 非 API 端点：`/healthz`（存活）、`/readyz`（就绪，含数据库检查）。

已实现的模块前缀（与 `config/urls.py` 一一对应）：

| 模块 | 前缀 |
| --- | --- |
| 公共 | `/api/v1/meta/`、`/api/v1/dictionaries/`、`/api/v1/audit-logs/`、`/api/v1/attachments/`、`/api/v1/code-rules/` |
| identity | `/api/v1/identity/`（用户、角色、权限、菜单、登录会话、通知） |
| factory | `/api/v1/factory/`（公司、部门、工厂、车间、线体、工位、员工、班次、班组） |
| masterdata | `/api/v1/masterdata/`（物料、分类、款式、颜色、尺码、SKU、计量单位、标识） |
| crm | `/api/v1/crm/customers/`、`/api/v1/crm/customer-contacts/`、`/api/v1/crm/complaints/`、`/api/v1/crm/product-reviews/` |
| srm | `/api/v1/srm/suppliers/`、`/api/v1/srm/supplier-contacts/`、`/api/v1/srm/supplier-qualifications/` |
| wms | `/api/v1/wms/`（仓库、库区、储位、**库存余额、库存流水、库存单据**） |
| procurement | `/api/v1/procurement/`（**采购申请、采购订单、采购收货**） |
| workflow | `/api/v1/workflow/`（审批模板、实例、待办） |
| integration | `/api/v1/integration/`（Outbox 事件、单据关系） |
| analytics | `/api/v1/analytics/`（看板聚合） |
| equipment | `/api/v1/equipment/`（设备台账与类型、设备零部件、备品备件与配件、故障报修、保养、维修、点巡检、异常上报） |
| ems | `/api/v1/ems/`（计量区域与仪表、价格与阈值、抄表、设备运行记录、报警、看板 / 报表 / 统计） |
| iot | `/api/v1/iot/`（连接配置、数采设备、采集测点、采集读数、采集日志、**采集统计**；另有设备侧上报入口 `POST /api/v1/iot/ingest/`） |
| ehs | `/api/v1/ehs/`（安全、环保、消防、设备设施安全） |
| logistics | `/api/v1/logistics/`（自动化设备、物流任务、操作日志） |
| qms | `/api/v1/qms/`（检验项目、检验单与检验结果、质量报警、质量问题知识库；另有只读统计 `GET /api/v1/qms/inspections/statistics/`） |
| mes | `/api/v1/mes/orders/`（生产工单与动作）、`/api/v1/mes/reports/`（报工台账） |
| 文档 | `/api/v1/schema/`（OpenAPI）、`/api/v1/docs/`（Swagger UI） |

主数据资源统一提供 `list / retrieve / create / partial_update / set-active`，**不提供 `DELETE`**
（任务书 5.5：已使用主数据优先停用）。

**例外（库存）**：

- 余额与流水：**仅** `list / retrieve`，无写入路由（写操作返回 405）。
- 库存单据：`list / retrieve / create / partial_update` + `set-active` 不适用；
  状态变更走**动作端点** `post/`、`reverse/`、`release-quality/`，不做普通 PATCH。
- 已过账单据**不可编辑**（`partial_update` 返回 **409 `STATE_CONFLICT`**，见 `test_posted_document_cannot_be_edited`）。

**采购单据（`procurement`）约定**：

- 头表可 `list / retrieve / create / partial_update`（仅草稿），**不提供 `DELETE`**；
  取消走动作端点（`cancel/`，必填 `reason`），不删除已提交的单据。
- 状态迁移一律走**动作端点**：`submit/`、`approve`（由 `workflow` 完成）、`convert/`、`close/`、
  `post/`、`inspect/`，不做普通 PATCH。
- **金额与 `received_quantity` 是只读字段**：请求里携带它们会被忽略，
  金额由后端按明细重算，`received_quantity` 只能由库存过账推进。
- **跨模块动作按「与」语义声明权限**：`required_permissions` 可以是列表，
  表示**同时**需要这些权限码（`apps/core/permissions.py::require_codes` 为 AND 语义）。
  例：采购收货过账同时要求 `procurement.receipt.post` **与** `wms.document.create`、`wms.document.post`；
  来料检验放行同时要求 `procurement.receipt.inspect` **与** `wms.quality.release`。
  这样**持有采购权限不会绕过库存授权**，反之亦然。

**只读统计接口（阶段 5 / CRM 深化 / 质量管理增补）**：

- `GET /api/v1/iot/statistics/`（权限 `iot.reading.view`）：按「测点 × 时间桶」聚合采集读数；
  参数 `granularity`（`hour` / `day`，默认 `day`）、`since`、`until`（**含当天**）、`company_id`、
  `gateway_id`、`point_id`、`is_simulated`、`limit`；返回 `rows` / `buckets` / `totals` / `truncated` / `row_limit`。
- `GET /api/v1/crm/complaints/statistics/`（权限 `crm.complaint.view`）、
  `GET /api/v1/crm/product-reviews/statistics/`（权限 `crm.product_review.view`）：
  参数 `since`、`until`（**含当天**）、`company_id`、`customer_id`。
- `GET /api/v1/qms/inspections/statistics/`（权限 `qms.inspection.view`）：质量信息动态监测；
  参数 `since`、`until`（**含当天**）、`company_id`、`inspection_type`；
  返回单据量（草稿 / 已提交 / 已判定）、**合格率（分母只含已判定单据）**、判定分布、
  不合格项目 TOP10、未关闭报警数与报警级别分布。
- 这些接口都**只有 `GET`**（无写路由），且**全部按明细实时聚合、不落汇总表**：
  页面上的数字永远能回到明细列表逐条核对。
- 错误码：`granularity` 不在支持列表 → `GRANULARITY_NOT_SUPPORTED`（400）；
  时间跨度超过该粒度上限 → `TIME_RANGE_TOO_WIDE`（400）；起始不早于结束 → `INVALID_TIME_RANGE`（400）。

**质量管理（`qms`）约定**：

- 检验项目 `inspection-items`、检验单 `inspections`、质量报警 `alerts`、知识库 `issues`
  均为 `list / retrieve / create / partial_update` + `set-active`（报警与检验单不做删除）。
- 状态一律走动作端点：检验单 `results/`（`GET` 查看 / `POST` 录入覆盖）、`submit/`、`judge/`、`close/`；
  报警 `handle/`、`close/`、`create-issue/`；知识库 `publish/`、`archive/`。
- **定量项目的合格与否只能由服务层按检验项目上下限判定**：请求里携带的 `is_qualified`
  对定量项目**被忽略**，对定性项目才是必填结论。
- `results/` 一个 action 同时服务查看与录入，而权限按 `self.action` 解析，
  写路径在方法内部用 `require_codes(request.user, "qms.inspection.update")` 二次校验。

**生产执行（`mes`）约定**：

- 工单 `/api/v1/mes/orders/`：`list / retrieve / create / partial_update` + 动作端点，
  **不提供 `DELETE`**；报工 `/api/v1/mes/reports/` 为**只读台账**（`list / retrieve`）。
- 状态迁移一律走**动作端点**（不做普通 PATCH推状态）：
  `release/`（下达，冻结 BOM / 工艺快照并生成工序与用料）、
  `issue-materials/`（领料，经统一库存服务过账）、`report/`（报工）、
  `complete/`（完工）、`receipt/`（完工入库）、`close/`（关闭）、`cancel/`（取消，必填 `reason`）。
- 查询类子资源：`GET /api/v1/mes/orders/{id}/materials/`（工单用料）、
  `GET /api/v1/mes/orders/{id}/steps/`（工单工序）、
  `GET /api/v1/mes/orders/statistics/`（只读统计）。
- **工单表头在非草稿状态下冻结**：已下达及之后的 `PATCH` 返回
  **409 `STATE_CONFLICT`**（只能改草稿）。
- **领料与完工入库支持 `Idempotency-Key`：**同一工单重复提交同一幂等键返回**首次结果**（不重复过账），
  已领料 / 已入库的工单再次请求且无幂等键则报
  `MATERIAL_ALREADY_ISSUED` / `RECEIPT_ALREADY_POSTED`（409）。
- 报工台账只读，录入只能经工单的 `report/`：报工是**不可回改的原始记录**，
  填错了补一条返工报工，而不是把历史数字改掉。
- 数量与金额均为字符串输出的 Decimal；`progress_rate` 等百分比字段输出为
  保留 2 位小数的字符串（如 `"0.00"`），不输出科学计数法。

## 二、认证与 CSRF

| 项 | 约定 |
| --- | --- |
| 认证 | Django Session（`SessionAuthentication`），同域部署 |
| Cookie | `HttpOnly`；生产 `Secure`；`SameSite=Lax` |
| CSRF | **所有写操作校验 CSRF**，登录接口同样防护（`/identity/auth/csrf/` 下发 token） |
| 退出 | 服务端会话失效，不是仅清前端状态 |
| 会话失效 | 改密、账号停用、权限撤销时按规则失效现有会话 |
| 设备上报 | 使用独立设备凭证，**不复用员工登录会话** |
| 未登录响应 | `403`（DRF `SessionAuthentication` 语义），前端据此跳转登录页 |

## 三、HTTP 状态码

| 码 | 场景 |
| --- | --- |
| 200 | 查询、更新成功 |
| 201 | 创建成功 |
| 204 | 无响应体的成功操作（部分动作接口） |
| 400 | 参数/业务校验失败（`VALIDATION_FAILED`、`PAGE_SIZE_EXCEEDED`） |
| 403 | 未认证或权限不足（`FORBIDDEN`、`PERMISSION_DENIED`） |
| 404 | 对象不存在或**不在数据范围内**（不泄露对象是否存在） |
| 409 | 状态冲突、并发版本冲突、幂等冲突、库存不足 |
| 429 | 触发限流（登录限流、设备上报限流） |
| 500 | 未预期错误（不外泄堆栈，仅返回 `request_id` 便于关联日志） |

## 四、统一错误结构

```json
{
  "code": "INSUFFICIENT_STOCK",
  "message": "可用库存不足",
  "details": { "required": "12.000000", "available": "8.000000" },
  "request_id": "3f6b1c2e-..."
}
```

- 所有错误（含 DRF 自带异常、Django `Http404`、`PermissionDenied`）经
  `yishang_exception_handler` 归一化为上述结构。
- **字段级错误**放在 `details.fields`，形如 `{"code": ["该编码已存在"]}`，前端表单可直接定位到字段。
- `request_id` 由 `apps/core/middleware.py` 注入并写入日志，用于关联审计与错误排查。

已定义的业务错误码（`apps/core/exceptions.py`）：

| 异常类 | HTTP | `code` |
| --- | --- | --- |
| `ValidationFailed` | 400 | `VALIDATION_FAILED` |
| `ObjectNotFound` | 404 | `NOT_FOUND` |
| `NotPermitted` | 403 | `FORBIDDEN` / `PERMISSION_DENIED` |
| `StateConflict` | 409 | `STATE_CONFLICT` |
| `OptimisticLockConflict` | 409 | `VERSION_CONFLICT` |
| `IdempotencyConflict` | 409 | `IDEMPOTENCY_KEY_CONFLICT` |
| `InsufficientStock` | 409 | `INSUFFICIENT_STOCK` |
| （分页超限，直接抛 `APIError`） | 400 | `PAGE_SIZE_EXCEEDED` |

阶段 2 起补充单据相关错误码时，**必须同步更新本表**。

## 五、分页

```json
{ "count": 120, "page": 1, "page_size": 20, "results": [...] }
```

- 查询参数：`page`、`page_size`。
- **最大页大小限制**：`YISHANG_PAGE_SIZE_MAX`（默认 200）。超过时返回 400 `PAGE_SIZE_EXCEEDED`，
  并在 `details.max_page_size` 给出上限，避免单次拉取全表。
- 不分页的固定规模接口（枚举、字典项）单独声明，不套用分页结构。

## 六、过滤与排序白名单

- 列表接口的 `filter` / `ordering` 字段**采用白名单**，非白名单字段被忽略或拒绝，不直接透传 ORM 查询表达式。
- 排序仅允许声明过的字段，避免按未索引字段排序导致慢查询。
- 关联对象过滤（如按 `warehouse` 过滤）同样经过数据范围过滤，防止通过参数探测范围外数据。

## 七、幂等（任务书 7.2）

适用操作：库存过账、扫码报工、转单、设备上报。

```text
请求头：Idempotency-Key: <客户端生成的唯一标识>
```

**已落地示例（阶段 2 库存）**：

```text
POST /api/v1/wms/inventory-documents/{id}/post/
Idempotency-Key: wms-document-post-{id}-{version}

POST /api/v1/procurement/receipts/{id}/post/       收货过账（记待检库存）
POST /api/v1/procurement/receipts/{id}/inspect/    来料检验判定（质量放行）
Idempotency-Key: procurement-receipt-{action}-{id}-{version}
```

重放时响应带 `Idempotency-Replayed: true`。
**多行收货单**的检验放行在服务内部按**行号**派生幂等键，
因此一次请求放行多行不会因为共用一个外部键而相互冲突（见 `test_multi_line_receipt_inspect_releases_every_line_once`）。

幂等键与「余额变化 + 流水 + 状态迁移」在**同一事务**内提交；
前端用 `{id}-{version}` 构造键，保证同一单据同一版本只过账一次，
而不会把「改草稿后重新过账」误判为重复。

规则：

1. 同一 `scope + key` 重复调用**不产生重复业务结果**，直接返回首次结果。
2. 同一 key 对应**不同请求内容**时拒绝处理，返回 409 `IDEMPOTENCY_KEY_CONFLICT`
   （通过 `request_hash` 比对请求体指纹）。
3. 幂等结果与业务操作**在同一事务内提交**（`core.IdempotencyRecord`，唯一约束 `uq_idempotency_scope_key`）。
4. 有效期由 `YISHANG_IDEMPOTENCY_TTL_HOURS` 控制（默认 24 小时），过期记录可清理。
5. 单据状态机与数据库唯一约束作为**额外保障**，不把幂等表当作唯一防线。

## 八、并发与重试

- 乐观并发：实体带 `version` 字段，更新时可携带版本，冲突返回 409 `VERSION_CONFLICT`。
- 悲观锁：库存等关键路径使用 `select_for_update()`，并**按 `dimension_key` 升序获取多个库存键的锁**以降低死锁风险（已实现）。
- **死锁与锁超时可有限重试**，但重试必须：
  1. 重新执行**完整事务**（不是从中断处继续）；
  2. 保证**幂等**（重试不重复生成单据、不重复扣减库存）。
  已实现：`MAX_LOCK_RETRIES = 3`，**仅** MySQL 1213（死锁）/ 1205（锁等待超时）触发重试，
  其余错误**直接上抛**，避免掩盖真实故障（见 `test_non_retryable_error_is_not_retried`）。
- 客户端不得对写操作做无限制自动重试；写操作重试必须带 `Idempotency-Key`。

## 九、Outbox 与异步任务

- 事件与业务数据**同事务写入** `core.OutboxEvent`；后台轮询分发，**至少一次**语义，消费者必须幂等。
- 重试超过 `max_attempts` 进入 `FAILED`，由有权限的人员人工处理/重放（`integration.outbox.retry`）。
- `transaction.on_commit()` 可用于加速唤醒，**但不能代替持久化 Outbox**。
- 长任务（大文件导入、Excel 导出、能源汇总、报表）通过 Celery 执行，要求：
  任务可观测、有超时（`CELERY_TASK_TIME_LIMIT`）、有重试与失败原因、长任务分批处理、
  执行前后持久化状态、**调度任务不得重复生成业务单据**。
- **MRP 运算是同步计算**（ADR-09），不经 Celery：它需要在同一事务内读供需、写运行快照并立即返回结果。
- **数据库是任务业务结果的最终依据**，不把任务返回值当正式记录。

## 十、Excel 导入导出

导入流程固定为：

```text
上传 → 校验 → 错误预览 → 确认导入 → 结果报告
```

- 提供标准模板下载。
- **每行返回明确错误**（行号 + 字段 + 原因），默认**不静默跳过错误行**。
- 明确声明原子导入或分批导入策略（阶段 2 起按单据类型选择并在页面标注）。
- 防公式注入（以 `=`、`+`、`-`、`@` 开头的单元格转义）与恶意文件（类型/大小/内容校验）。
- 下载链接设置**权限与有效期**，附件不能通过猜测地址绕过权限。

## 十一、OpenAPI

- 使用 `drf-spectacular` 生成，路径：`/api/v1/schema/`（YAML/JSON）与 `/api/v1/docs/`（Swagger UI）。
- 接口变更时**同步更新文档**；新增权限点需在注册表登记，否则启动自检失败。

## 十二、枚举字段与中文标签（`_display`）

- **英文枚举键是接口契约**：`status`、`warehouse_type`、`department_type` 等字段在
  **请求筛选、写入、排序**中一律传英文键（如 `?warehouse_type=finished`）。
- **中文标签随响应返回**：凡模型字段带 `choices`，序列化器自动附带同名只读字段
  `<field>_display`（如 `"warehouse_type": "finished"` + `"warehouse_type_display": "成品仓"`）。
  机制见 `apps/core/serializers.py::DisplayLabelsMixin`，由 `ReferenceIdSerializer` 统一继承；
  幂等性上它**只增加只读字段，不改变请求契约**。
- **前端只读 `_display`**：列表与详情优先展示 `_display`，缺失时才回退到原始值或前端 `meta` 字典
  （`frontend/src/components/ProTable.vue`、`EntityListPage.vue`）；
  **不允许前端硬编码枚举中文映射**，避免两端漂移。
- **枚举字典接口** `/api/v1/meta/` 提供下拉选项，其中 `label` 为中文、`value` 为英文键。
- **质量红线**：写入非法枚举值（不在 `choices` 内）视为数据缺陷。
  `backend/tests/test_enum_labels.py` 全量遍历序列化器，任一 choices 字段缺 `_display` 即失败；
  另有用例在 `seed_demo` 后对全库复扫非法枚举值。
