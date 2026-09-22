from __future__ import annotations

from rest_framework import serializers

from apps.core.models import Attachment, AuditLog, CodeRule, Dictionary, DictionaryItem
from apps.core.services import describe_changes, object_type_label


class DisplayLabelsMixin:
    """为「带 choices 的字段」自动补一个 ``<field>_display`` 只读字段。

    背景：枚举值在数据库里是稳定的英文键（例如 ``warehouse_type="raw"``、
    ``department_type="management"``）。直接渲染到界面就会显示英文，与任务书
    8.1「中文业务界面」不符；而这个翻译在 Django 里本来就存在
    （``get_<field>_display()``），没有理由让每个模块各写一遍、更不该由前端硬编码。

    约定：
    * 只对**序列化器 ``Meta.fields`` 中确实包含**、且模型字段**确实有 choices** 的字段生效；
    * 已经被模块显式声明的 ``<field>_display`` 不覆盖（保留模块自己的口径）；
    * 新增字段一律 ``read_only``，因此不影响写入、也不需要迁移；
    * 写入与筛选仍然使用**英文键**，只有展示层拿到中文标签。
    """

    def get_fields(self) -> dict[str, serializers.Field]:
        from django.core.exceptions import FieldDoesNotExist

        fields = super().get_fields()
        model = getattr(getattr(self, "Meta", None), "model", None)
        if model is None:
            return fields

        for name in list(fields):
            display_name = f"{name}_display"
            if display_name in fields:
                continue
            try:
                model_field = model._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            if not getattr(model_field, "choices", None):
                continue
            if not getattr(model_field, "concrete", False):
                continue
            if not hasattr(model, f"get_{name}_display"):
                continue
            verbose = getattr(model_field, "verbose_name", "") or name
            fields[display_name] = serializers.CharField(
                source=f"get_{name}_display",
                read_only=True,
                label=f"{verbose}（中文标签）",
            )
        return fields


class ReferenceIdSerializer(DisplayLabelsMixin, serializers.ModelSerializer):
    """把 ``<外键>_id`` 字段声明为可写的主键关联字段。

    背景：DRF 在序列化器 fields 中遇到 ``company_id`` 这类名称时，会因为模型上存在
    同名属性（Django 为外键生成的 ``attname``）而生成只读字段，导致「创建」接口
    永远写不进外键，只能在数据库报 NOT NULL 错误。本基类在 fields 构建完成后统一
    把这类字段替换为可写的主键关联字段，required/allow_null 严格对齐模型定义。

    约定：
    * 在 ``Meta.read_only_fields`` 中显式声明为只读的字段保持只读；
    * 显式声明了 ``source`` 的字段（例如 ``company_id = IntegerField(source=...)``）
      不做替换，避免覆盖联表只读字段；
    * 外键是否可写只影响「能否写入」，组织范围仍由视图的
      ``assert_in_scope`` 校验，绝不因为字段可写就放宽数据范围。
    """

    def get_fields(self) -> dict[str, serializers.Field]:
        from django.core.exceptions import FieldDoesNotExist

        fields = super().get_fields()
        model = self.Meta.model
        declared_read_only = set(getattr(self.Meta, "read_only_fields", ()) or ())

        for name in list(fields):
            if not name.endswith("_id") or name in declared_read_only:
                continue
            current = fields[name]
            # get_fields() 返回的是未绑定字段，此时 source 仍为 None；
            # 显式声明了不同 source 的联表只读字段不能被替换
            if not getattr(current, "read_only", False):
                continue
            if getattr(current, "source", None) not in (None, name):
                continue
            relation_name = name[: -len("_id")]
            try:
                model_field = model._meta.get_field(relation_name)
            except FieldDoesNotExist:
                continue
            if not (model_field.is_relation and model_field.many_to_one):
                continue
            fields[name] = serializers.PrimaryKeyRelatedField(
                source=relation_name,
                queryset=model_field.related_model._default_manager.all(),
                required=not (model_field.null or model_field.has_default() or model_field.blank),
                allow_null=bool(model_field.null),
                label=str(model_field.verbose_name),
            )
        return fields


class ServerDerivedCodeSerializerMixin:
    """编号（或组织归属）由服务端推导的序列化器基类：关掉 DRF 自动派生的唯一性校验。

    背景：模型的 ``UniqueConstraint``（例如「公司 + 投诉编号」）会被 DRF 自动转成
    ``UniqueTogetherValidator``，而该校验器会**强制约束里的每个字段必填**，
    包括由服务端推导、客户端根本不会传的字段（自动取的编号、由来源单据推导的公司）。
    结果是新增会被一句「该字段是必填项」挡在门外，而页面上连填的地方都没有。

    这里关掉自动生成的唯一性校验，重复数据由数据库唯一约束兜底，再由视图的
    ``uniqueness_error_map`` 翻译成「同一公司下编号已存在」这类中文提示；
    编号格式与取号时机仍由服务层保证，不受影响。

    由客户端显式指定全部约束字段的对象不要继承本基类，保留 DRF 的前置校验。
    """

    def get_unique_together_validators(self):
        return []



class DictionaryItemSerializer(ReferenceIdSerializer):
    class Meta:
        model = DictionaryItem
        fields = (
            "id", "dictionary_id", "code", "label", "sort_order", "is_active", "extra",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")


class DictionarySerializer(ReferenceIdSerializer):
    items = DictionaryItemSerializer(many=True, read_only=True)

    class Meta:
        model = Dictionary
        fields = (
            "id", "code", "name", "is_system", "is_active", "remark", "items",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "is_system", "items", "version", "created_at", "updated_at")


class CodeRuleSerializer(ReferenceIdSerializer):
    class Meta:
        model = CodeRule
        fields = (
            "id", "code", "name", "pattern", "reset_period", "is_active", "remark",
            "version", "created_at", "updated_at",
        )
        read_only_fields = ("id", "version", "created_at", "updated_at")

    def validate_pattern(self, value: str) -> str:
        from apps.core.exceptions import ValidationFailed
        from apps.core.services import render_code_pattern

        try:
            render_code_pattern(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError(exc.message) from exc
        return value


class CodeRulePreviewSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)
    sample = serializers.IntegerField(required=False, default=1, min_value=1)


class AuditLogSerializer(ReferenceIdSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    # object_type 存的是 `app_label.ModelName`（内部标识），界面上要给使用者看中文名
    object_type_display = serializers.SerializerMethodField()
    # 变更摘要的键是英文字段名，这里额外给出中文条目供界面直接渲染
    changes_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id", "request_id", "action", "action_display", "actor_id", "actor_username",
            "actor_name", "company_id", "object_type", "object_type_display", "object_id",
            "object_repr", "changes", "changes_display", "reason", "approval_basis",
            "ip_address", "user_agent", "created_at",
        )
        read_only_fields = fields

    def get_object_type_display(self, obj: AuditLog) -> str:
        return object_type_label(obj.object_type)

    def get_changes_display(self, obj: AuditLog) -> list[dict[str, str]]:
        return describe_changes(obj.object_type, obj.changes)


class AttachmentSerializer(ReferenceIdSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = (
            "id", "original_name", "content_type", "size_bytes", "sha256", "biz_type",
            "biz_id", "uploaded_by_name", "download_url", "created_at",
        )
        read_only_fields = fields

    def get_uploaded_by_name(self, obj: Attachment) -> str:
        if not obj.created_by_id:
            return ""
        return obj.created_by.display_name or obj.created_by.username

    def get_download_url(self, obj: Attachment) -> str:
        return f"/api/v1/attachments/{obj.pk}/download/"


class AttachmentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    biz_type = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    biz_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
