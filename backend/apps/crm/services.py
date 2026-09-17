"""客户模块的领域规则。

放在服务层而不是信号里：规则需要显式可测、可审计，且不要在保存客户时
隐式产生别的副作用（任务书 4.3 禁止用 signals 承载关键流程）。
"""

from __future__ import annotations

from apps.core.services import ensure_single_primary
from apps.crm.models import CustomerContact


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
