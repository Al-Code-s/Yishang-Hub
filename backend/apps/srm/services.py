"""供应商模块的领域规则。"""

from __future__ import annotations

from apps.core.services import ensure_single_primary
from apps.srm.models import SupplierContact


def ensure_single_primary_contact(contact: SupplierContact) -> None:
    """保证同一供应商下只有一个主要联系人。"""
    ensure_single_primary(
        SupplierContact,
        instance=contact,
        scope_field="supplier_id",
        scope_id=contact.supplier_id,
    )
