"""内部协同：单据关系。

跨模块追溯（订单→MRP→采购/生产→入库→发货）依赖本表建立显式关系，
而不是靠字符串约定或前端拼接。
"""

from __future__ import annotations

from django.db import models

from apps.core.models import BaseModel


class DocumentRelation(models.TextChoices):
    GENERATED_FROM = "generated_from", "由...生成"
    FULFILLS = "fulfills", "满足"
    CONSUMES = "consumes", "消耗"
    REFERENCES = "references", "关联"
    REVERSES = "reverses", "冲销"


class DocumentLink(BaseModel):
    """单据关系。source 派生 target。"""

    source_type = models.CharField("来源单据类型", max_length=128, db_index=True)
    source_id = models.CharField("来源单据主键", max_length=64, db_index=True)
    source_no = models.CharField("来源单据号", max_length=64, blank=True, default="")
    target_type = models.CharField("目标单据类型", max_length=128, db_index=True)
    target_id = models.CharField("目标单据主键", max_length=64, db_index=True)
    target_no = models.CharField("目标单据号", max_length=64, blank=True, default="")
    relation = models.CharField(
        "关系", max_length=32, choices=DocumentRelation.choices, default=DocumentRelation.GENERATED_FROM
    )
    quantity = models.DecimalField(
        "关联数量", max_digits=20, decimal_places=6, null=True, blank=True
    )
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        verbose_name = "单据关系"
        verbose_name_plural = "单据关系"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "target_type", "target_id", "relation"],
                name="uq_document_link",
            ),
        ]
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="idx_doclink_target"),
        ]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id} -> {self.target_type}:{self.target_id}"
