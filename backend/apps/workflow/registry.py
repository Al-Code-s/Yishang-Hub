"""审批结果回写业务单据的显式注册点。

审批通过与业务状态迁移是**两个动作**，但同一张业务单据在审批结束后必须同步自己的状态，
否则会出现「审批已通过、订单仍是草稿」的脱节。

这里不使用 Django signals（任务书 4.3 禁止用 signals 承载关键业务流程），而是：

* 业务模块在 ``AppConfig.ready()`` 里**显式注册**自己的处理函数；
* ``workflow.services`` 在审批终结（通过 / 驳回 / 撤回）时**同步调用**该函数；
* 调用发生在 workflow 的 ``transaction.atomic()`` 内部，业务状态与审批状态同事务提交。

未注册 ``biz_type`` 时什么也不做（例如通用的 ``generic.request`` 审批单），
因此本机制对既有审批能力完全向后兼容。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型提示
    from apps.workflow.models import ApprovalInstance

# 审批终结结果
OUTCOME_APPROVED = "approved"
OUTCOME_REJECTED = "rejected"
OUTCOME_WITHDRAWN = "withdrawn"

BizOutcomeHandler = Callable[["ApprovalInstance", str], None]

_HANDLERS: dict[str, BizOutcomeHandler] = {}


def register_biz_handler(biz_type: str, handler: BizOutcomeHandler) -> None:
    """登记某业务类型的审批终结回调。重复登记视为覆盖，便于测试注入。"""
    if not biz_type:
        raise ValueError("biz_type 不能为空")
    _HANDLERS[biz_type] = handler


def registered_biz_types() -> tuple[str, ...]:
    return tuple(sorted(_HANDLERS))


def apply_biz_outcome(instance: ApprovalInstance, outcome: str) -> None:
    """把审批终结结果同步给业务单据。必须在 workflow 的事务内调用。"""
    handler = _HANDLERS.get(instance.biz_type)
    if handler is None:
        return
    handler(instance, outcome)


__all__ = [
    "OUTCOME_APPROVED",
    "OUTCOME_REJECTED",
    "OUTCOME_WITHDRAWN",
    "apply_biz_outcome",
    "register_biz_handler",
    "registered_biz_types",
]
