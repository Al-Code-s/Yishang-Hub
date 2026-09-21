"""客户模块的领域规则。

放在服务层而不是信号里：规则需要显式可测、可审计，且不要在保存客户时
隐式产生别的副作用（任务书 4.3 禁止用 signals 承载关键流程）。

客户编码的自动取号（`next_customer_code`）也放在这里：让「编码从哪来」只有一处口径，
视图层只调用，不自己拼格式。
"""

from __future__ import annotations

from apps.core.services import ensure_single_primary, generate_code
from apps.crm.models import CustomerContact

CUSTOMER_CODE_RULE = "CUS"


def next_customer_code() -> str:
    """按编码规则取下一个客户编码。

    规则本体（编号格式与重置周期）由 `bootstrap_system.CODE_RULES` 登记，
    并可在「系统管理 -> 编码规则」中调整；这里只引用规则编码，**不硬编码格式**，
    避免出现「改了规则却不生效」的两套口径。

    取号在 `generate_code` 的事务内完成（先锁规则行再锁流水行），并发调用不会重号。
    """
    return generate_code(CUSTOMER_CODE_RULE)


def ensure_single_primary_contact(contact: CustomerContact) -> None:
    """保证同一客户下只有一个主要联系人。

    通用规则实现在 `apps/core/services.py::ensure_single_primary`，
    这里只绑定客户联系人的归属字段，避免各模块各写一份。
    """
    ensure_single_primary(
        CustomerContact,
        instance=contact,
        scope_field="customer_id",
        scope_id=contact.customer_id,
    )
