"""枚举字段的中文标签与数据合法性用例（回归：界面显示英文枚举值）。

真实缺陷（本轮修复）：
* 列表与详情直接渲染枚举的**英文键**，界面出现 ``raw`` / ``finished`` /
  ``management`` / ``quantity`` 这类值，与任务书 8.1「中文业务界面」不符；
* 早期 ``seed_demo`` 还写入了**不在 choices 里**的值（中文性别、``supply``、
  ``worker``、``professional`` 等），这些值连 ``get_FOO_display()`` 都翻译不出来。

因此这里做两层断言：
1. 展示层——凡是序列化器暴露的 choices 字段，都必须同时提供 ``<field>_display``；
2. 数据层——执行 ``seed_demo`` 后，全库不得存在非法枚举值。
"""

from __future__ import annotations

import inspect

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from rest_framework import serializers

from tests.conftest import make_user

pytestmark = pytest.mark.django_db

WAREHOUSES_URL = "/api/v1/wms/warehouses/"
DEPARTMENTS_URL = "/api/v1/factory/departments/"
UOMS_URL = "/api/v1/masterdata/uoms/"
META_URL = "/api/v1/meta/"

SKIPPED_APPS = {"admin", "auth", "contenttypes", "sessions", "django_celery_beat"}


def _iter_model_serializers():
    for config in django_apps.get_app_configs():
        if not config.name.startswith("apps."):
            continue
        try:
            module = __import__(f"{config.name}.serializers", fromlist=["x"])
        except ImportError:
            continue
        for name, obj in vars(module).items():
            if not inspect.isclass(obj) or not issubclass(obj, serializers.ModelSerializer):
                continue
            if obj.__module__ != module.__name__:
                continue
            if getattr(getattr(obj, "Meta", None), "model", None) is None:
                continue
            yield f"{config.label}.{name}", obj


def _choosy_model_fields(model):
    for field in model._meta.get_fields():
        if getattr(field, "choices", None) and getattr(field, "concrete", False):
            yield field.name, {str(key) for key, _ in field.choices}


def _invalid_enum_values():
    """返回全库中「不在 choices 内」的枚举值清单。"""
    invalid = []
    for model in django_apps.get_models():
        if not model._meta.managed or model._meta.auto_created:
            continue
        if model._meta.app_label in SKIPPED_APPS:
            continue
        counts: dict[object, int] = {}
        for field_name, valid_keys in _choosy_model_fields(model):
            counts.clear()
            for value in model.objects.values_list(field_name, flat=True):
                counts[value] = counts.get(value, 0) + 1
            for value, number in counts.items():
                if value in (None, "") or str(value) in valid_keys:
                    continue
                invalid.append(f"{model._meta.label}.{field_name}={value!r}（{number} 条）")
    return invalid


@pytest.fixture
def enum_admin_client(api_client, company):
    user = make_user(username="enum_admin", company=company, is_superuser=True)
    response = api_client.post(
        "/api/v1/identity/auth/login/",
        {"username": user.username, "password": "Tst!Passw0rd2026"},
        format="json",
    )
    assert response.status_code == 200
    return api_client


def test_every_choice_field_exposes_chinese_label():
    """序列化器里的每个 choices 字段都必须带 `<field>_display`。"""
    missing: list[str] = []
    checked = 0
    for label, serializer_class in _iter_model_serializers():
        serializer = serializer_class()
        model = serializer_class.Meta.model
        for field_name in list(serializer.fields):
            try:
                model_field = model._meta.get_field(field_name)
            except Exception:
                continue
            if not getattr(model_field, "choices", None):
                continue
            checked += 1
            if f"{field_name}_display" not in serializer.fields:
                missing.append(f"{label}.{field_name}")
    assert checked > 0, "没有扫描到任何 choices 字段，用例本身可能失效"
    assert missing == [], (
        "以下序列化器暴露了枚举字段却没有中文标签（界面会显示英文键）："
        + "、".join(missing)
        + "。请让序列化器继承 apps.core.serializers.DisplayLabelsMixin。"
    )


def test_label_is_not_the_raw_key(enum_admin_client, company):
    """标签必须真的是中文，而不是把英文键原样返回。"""
    from apps.factory.models import Department
    from apps.masterdata.models import UoM
    from apps.wms.models import Warehouse

    Warehouse.objects.create(company=company, code="WH-ENUM", name="成品仓", warehouse_type="finished")
    Department.objects.create(company=company, code="PUR", name="采购部", department_type="procurement")
    UoM.objects.create(code="M2", name="平方米", category="area")

    warehouse = enum_admin_client.get(WAREHOUSES_URL).json()["results"][0]
    department = enum_admin_client.get(DEPARTMENTS_URL).json()["results"][0]
    uom = enum_admin_client.get(UOMS_URL).json()["results"][0]

    assert warehouse["warehouse_type"] == "finished"
    assert warehouse["warehouse_type_display"] == "成品仓"
    assert department["department_type"] == "procurement"
    assert department["department_type_display"] == "采购部门"
    assert uom["category"] == "area"
    assert uom["category_display"] == "面积"


def test_meta_endpoint_labels_are_chinese(enum_admin_client):
    payload = enum_admin_client.get(META_URL).json()
    for key in ("department_types", "workshop_types", "uom_categories", "warehouse_types"):
        options = payload[key]
        assert options, f"{key} 不应为空"
        for option in options:
            assert option["label"] != option["value"], f"{key} 的 {option['value']} 没有中文标签"
    department_values = {item["value"] for item in payload["department_types"]}
    assert {"procurement", "sales", "equipment"} <= department_values


def test_seed_demo_writes_only_valid_enum_values(settings):
    """演示数据必须只写合法枚举键——这正是「界面显示英文」的根因之一。"""
    settings.DJANGO_ENV = "test"
    settings.YISHANG = {**settings.YISHANG, "DEMO_PASSWORD": "Demo!Passw0rd2026"}
    call_command("bootstrap_system", "--skip-admin", verbosity=0)
    call_command("seed_demo", verbosity=0)

    invalid = _invalid_enum_values()
    assert invalid == [], "演示数据写入了不在 choices 内的值：" + "；".join(invalid)
