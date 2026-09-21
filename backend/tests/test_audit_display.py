"""审计与工作台的「中文展示」用例（回归：界面出现 masterdata.Material 这类内部标识）。

真实问题（本轮修复）：

* 审计日志的「对象类型」列、工作台「最近操作记录」直接渲染 ``object_type``，
  值是 ``app_label.ModelName``（例如 ``masterdata.Material``），业务用户看不懂，
  属于开发视角的文案；
* 审计详情的变更摘要是整块 ``{字段: {before, after}}`` 原始 JSON，键是英文字段名。

修复方式：**由后端算好展示名**（模型 ``verbose_name`` + 非字段键登记表），
前端只负责渲染。这里锁住三件事：

1. ``object_type_label`` / ``describe_changes`` / ``display_value`` 的翻译，
   以及「查不到就原样返回、不猜名字」的兜底；
2. ``/api/v1/audit-logs/`` 同时返回 ``object_type_display`` 与 ``changes_display``；
3. 工作台 ``recent_activity`` 带 ``action_display`` / ``object_type_display``，
   前端不需要自己维护翻译表。
"""

from __future__ import annotations

import pytest

from apps.core.models import AuditAction
from apps.core.services import (
    AUDIT_CHANGE_LABELS,
    describe_changes,
    display_value,
    object_type_label,
    record_audit,
)
from tests.conftest import make_user

pytestmark = pytest.mark.django_db

AUDIT_URL = "/api/v1/audit-logs/"
DASHBOARD_URL = "/api/v1/analytics/dashboard/"


class TestObjectTypeLabel:
    def test_已登记模型翻译成中文名(self) -> None:
        assert object_type_label("identity.Role") == "角色"
        assert object_type_label("wms.InventoryDocument") == "库存单据"
        assert object_type_label("workflow.ApprovalInstance") == "审批实例"

    def test_解析不到时原样返回而不是编名字(self) -> None:
        assert object_type_label("unknown.Thing") == "unknown.Thing"
        assert object_type_label("noDot") == "noDot"
        assert object_type_label("") == ""

    # 允许的非中文展示名：行业通用缩写，业务人员也这么叫（菜单同样写作「SKU 档案」）
    ALLOWED_NON_CHINESE = {"SKU"}

    def test_所有真实模型都能翻译成中文(self) -> None:
        """模型 verbose_name 一律是中文；如果哪天有人加了英文 verbose_name，
        审计界面会重新冒出英文，因此在这里兜住。"""
        from django.apps import apps as django_apps

        offenders = []
        for config in django_apps.get_app_configs():
            if not config.name.startswith("apps."):
                continue
            for model in config.get_models():
                label = object_type_label(f"{config.label}.{model.__name__}")
                if label in self.ALLOWED_NON_CHINESE:
                    continue
                if not any("\u4e00" <= char <= "\u9fff" for char in label):
                    offenders.append(f"{config.label}.{model.__name__} -> {label}")
        assert offenders == []


class TestDisplayValue:
    def test_空值布尔与集合都转成可读文字(self) -> None:
        assert display_value(None) == "空"
        assert display_value("") == "空"
        assert display_value(True) == "是"
        assert display_value(False) == "否"
        assert display_value(["a", "b"]) == "a、b"
        assert display_value([]) == "空"
        assert display_value({"k": 1}) == "k=1"
        assert display_value(12) == "12"


class TestDescribeChanges:
    def test_模型字段用中文字段名非字段键用登记表(self) -> None:
        rows = describe_changes(
            "identity.Role",
            {
                "company_id": {"before": None, "after": 2},
                "grants": {"before": [], "after": ["company:2"]},
            },
        )
        by_field = {row["field"]: row for row in rows}
        assert by_field["company_id"]["label"] == "归属公司"   # 模型字段 → verbose_name
        assert by_field["company_id"]["before"] == "空"
        assert by_field["company_id"]["after"] == "2"
        assert by_field["grants"]["label"] == AUDIT_CHANGE_LABELS["grants"] == "数据范围"

    def test_未登记的键保留原键名不猜含义(self) -> None:
        rows = describe_changes("identity.Role", {"totally_unknown": {"before": 1, "after": 2}})
        assert rows[0]["label"] == "totally_unknown"
        assert rows[0]["before"] == "1"

    def test_空摘要返回空列表(self) -> None:
        assert describe_changes("identity.Role", {}) == []
        assert describe_changes("identity.Role", None) == []


def test_审计接口同时返回中文对象类型与中文变更条目(api_client, login_as, user_factory, company):
    admin = make_user(username="audit_admin", company=company, is_superuser=True)
    login_as(api_client, admin)

    from apps.identity.models import Role

    role = Role.objects.create(code="AUDIT-R1", name="审计测试角色", company=company)
    record_audit(
        action=AuditAction.UPDATE,
        instance=role,
        changes={
            "company_id": {"before": None, "after": company.pk},
            "grants": {"before": [], "after": [f"company:{company.pk}"]},
        },
        actor=admin,
        company=company,
    )

    response = api_client.get(AUDIT_URL, {"ordering": "-id"})
    assert response.status_code == 200, response.content
    row = next(item for item in response.json()["results"] if item["object_id"] == str(role.pk))

    assert row["object_type"] == "identity.Role"        # 原始值保留，供排查用
    assert row["object_type_display"] == "角色"          # 展示值给用户看
    labels = {item["field"]: item["label"] for item in row["changes_display"]}
    assert labels["company_id"] == "归属公司"
    assert labels["grants"] == "数据范围"
    assert row["changes_display"][0]["after"]


def test_工作台最近动态带中文操作与对象名(api_client, login_as, user_factory, company):
    admin = make_user(username="dash_admin", company=company, is_superuser=True)
    login_as(api_client, admin)

    from apps.identity.models import Role

    role = Role.objects.create(code="DASH-R1", name="工作台测试角色", company=company)
    record_audit(action=AuditAction.CREATE, instance=role, actor=admin, company=company)

    response = api_client.get(DASHBOARD_URL)
    assert response.status_code == 200, response.content
    activity = response.json()["recent_activity"]
    assert activity, "工作台应返回最近操作记录"

    item = activity[0]
    assert item["object_type_display"] == "角色"
    assert item["action_display"] == "新增"
    # 前端不再自己维护翻译表：中文名必须来自接口
    assert "identity.Role" not in item["object_type_display"]


# --------------------------------------------------------------------------
# 内部协同事件：同理，不把 sales.SalesOrder 这类内部标识直接显示给业务人员
# --------------------------------------------------------------------------

OUTBOX_URL = "/api/v1/integration/outbox-events/"


def test_内部协同事件带中文业务对象名(api_client, login_as, company):
    from apps.core.services import publish_event

    admin = make_user(username="outbox_display_admin", company=company, is_superuser=True)
    login_as(api_client, admin)
    event = publish_event(
        event_type="sales.order.approved",
        aggregate_type="sales.SalesOrder",
        aggregate_id=1,
    )

    response = api_client.get(OUTBOX_URL)
    assert response.status_code == 200, response.content
    row = next(item for item in response.json()["results"] if item["id"] == event.pk)

    assert row["aggregate_type"] == "sales.SalesOrder"    # 原始值保留，供排查用
    assert row["aggregate_type_display"] == "销售订单"     # 展示值给用户看
