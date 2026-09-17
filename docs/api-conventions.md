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
| crm | `/api/v1/crm/customers/`、`/api/v1/crm/customer-contacts/` |
| srm | `/api/v1/srm/suppliers/`、`/api/v1/srm/supplier-contacts/`、`/api/v1/srm/supplier-qualifications/` |
| wms | `/api/v1/wms/`（仓库、库区、储位、**库存余额、库存流水、库存单据**） |
| procurement | `/api/v1/procurement/`（**采购申请、采购订单、采购收货**） |
| workflow | `/api/v1/workflow/`（审批模板、实例、待办） |
| integration | `/api/v1/integration/`（Outbox 事件、单据关系） |
| analytics | `/api/v1/analytics/`（看板聚合） |
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
- 长任务（大文件导入、Excel 导出、MRP、能源汇总、报表）通过 Celery 执行，要求：
  任务可观测、有超时（`CELERY_TASK_TIME_LIMIT`）、有重试与失败原因、长任务分批处理、
  执行前后持久化状态、**调度任务不得重复生成业务单据**。
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