"""质量管理服务：结果判定 + 单据状态机 + 质量报警闭环。

检验单流转（非法跃迁一律拒绝，不能靠 PATCH 跳步）::

    draft --submit--> submitted --judge--> judged --close--> closed

判定规则（刻意如此，不要放宽）：

* **定量项目由系统判定**：实测值在 ``[lower_limit, upper_limit]``（含端点）内为合格，
  超出即不合格；客户端传上来的 ``is_qualified`` 对定量项目一律忽略，不允许人工粉饰。
* **定性项目由检验员判定**，但必须显式给出结论，不能留空蒙混过关。
* 只要存在不合格项，整单**不能**被判为「合格」；全部合格也不能被判为「不合格」。
* 判定为「不合格」时自动生成一条质量报警（同一张检验单只生成一条，重复判定不会重复报警）。
* 不合格报警没有关闭时，检验单**不能关闭**——不允许把没闭环的问题销账。
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.core.exceptions import StateConflict, ValidationFailed
from apps.core.models import AuditAction
from apps.core.permissions import require_codes
from apps.core.services import business_now, generate_code, record_audit
from apps.qms.models import (
    InspectionValueType,
    QualityAlert,
    QualityAlertLevel,
    QualityAlertStatus,
    QualityInspectionItem,
    QualityInspectionOrder,
    QualityInspectionResult,
    QualityInspectionStatus,
    QualityInspectionType,
    QualityIssue,
    QualityIssueCategory,
    QualityIssueStatus,
    QualityJudgement,
)

ITEM_CODE_RULE = "QIT"
ORDER_CODE_RULE = "QC"
ALERT_CODE_RULE = "QAL"
ISSUE_CODE_RULE = "KI"

#: 允许在判定后继续关闭结论的取值
JUDGED_OPTIONS = {QualityJudgement.PASSED, QualityJudgement.FAILED, QualityJudgement.CONCESSION}


def next_item_code() -> str:
    """检验项目编码（编码规则 QIT）。"""
    return generate_code(ITEM_CODE_RULE)


def next_order_no() -> str:
    """检验单号（编码规则 QC）。"""
    return generate_code(ORDER_CODE_RULE)


def next_alert_no() -> str:
    """质量报警编号（编码规则 QAL）。"""
    return generate_code(ALERT_CODE_RULE)


def next_issue_no() -> str:
    """质量问题编号（编码规则 KI）。"""
    return generate_code(ISSUE_CODE_RULE)


def create_order(
    user: Any,
    *,
    company: Any,
    inspection_type: str = QualityInspectionType.IPQC,
    source_no: str = "",
    material: Any = None,
    product_desc: str = "",
    batch_no: str = "",
    workshop: Any = None,
    production_line: Any = None,
    equipment: Any = None,
    quantity: Any = Decimal("0"),
    sample_quantity: Any = Decimal("0"),
    unit: str = "",
    inspector: Any = None,
    inspected_at: Any = None,
    remark: str = "",
    order_no: str = "",
) -> QualityInspectionOrder:
    """新建检验单（草稿），供 MES 等其他模块在质检点发起检验。

    跨模块调用仍受权限约束：调用方必须持有 ``qms.inspection.create``，
    否则整个事务回滚——不允许「先建单再补权限」。数量与公司归属在这里统一口径，
    避免每个调用方各写一套。
    """
    require_codes(user, "qms.inspection.create")
    with transaction.atomic():
        order = QualityInspectionOrder(
            company_id=getattr(company, "pk", company),
            order_no=str(order_no or "").strip() or next_order_no(),
            inspection_type=inspection_type,
            source_no=str(source_no or "")[:64],
            material=material,
            product_desc=str(product_desc or "")[:255],
            batch_no=str(batch_no or "")[:64],
            workshop=workshop,
            production_line=production_line,
            equipment=equipment,
            quantity=Decimal(quantity or 0),
            sample_quantity=Decimal(sample_quantity or 0),
            unit=str(unit or "")[:16],
            inspector=inspector,
            inspected_at=inspected_at,
            remark=remark,
        )
        order.save()
        record_audit(
            action=AuditAction.CREATE,
            instance=order,
            changes={
                "order_no": {"before": "", "after": order.order_no},
                "inspection_type": {"before": "", "after": order.inspection_type},
                "source_no": {"before": "", "after": order.source_no},
            },
            reason=remark,
            object_repr=order.order_no,
            company=order.company,
            actor=user,
        )
    return order


def judge_measured_value(item: QualityInspectionItem, measured_value: Decimal | None) -> bool:
    """按项目口径判定一个实测值是否合格。定量项目必须给出实测值。"""
    if item.value_type != InspectionValueType.QUANTITATIVE:
        raise ValidationFailed(
            f"项目「{item.name}」是定性项目，不能按数值判定。", code="ITEM_NOT_QUANTITATIVE"
        )
    if measured_value is None:
        raise ValidationFailed(
            f"定量项目「{item.name}」必须填写实测值。", code="MEASURED_VALUE_REQUIRED"
        )
    value = Decimal(measured_value)
    if item.lower_limit is not None and value < item.lower_limit:
        return False
    if item.upper_limit is not None:
        return value <= item.upper_limit
    return True


def _row_judgement(item: QualityInspectionItem, row: dict[str, Any]) -> bool:
    """一行检验结果的合格判定：定量按上下限算，定性必须由检验员给出结论。"""
    if item.value_type == InspectionValueType.QUANTITATIVE:
        return judge_measured_value(item, row.get("measured_value"))
    declared = row.get("is_qualified")
    if declared is None:
        raise ValidationFailed(
            f"定性项目「{item.name}」必须给出合格 / 不合格判定。", code="RESULT_JUDGEMENT_REQUIRED"
        )
    return bool(declared)


@transaction.atomic
def record_results(
    order: QualityInspectionOrder, rows: Iterable[dict[str, Any]]
) -> list[QualityInspectionResult]:
    """录入 / 覆盖检验结果。只在草稿与已提交状态下允许，判定之后不能再改。"""
    if order.status not in {QualityInspectionStatus.DRAFT, QualityInspectionStatus.SUBMITTED}:
        raise StateConflict(
            "检验单已判定，不能再修改检验结果。", code="INSPECTION_STATUS_INVALID"
        )
    saved: list[QualityInspectionResult] = []
    for index, row in enumerate(rows):
        item: QualityInspectionItem = row["item"]
        if item.company_id != order.company_id:
            raise ValidationFailed(
                f"检验项目「{item.name}」不属于该检验单的公司。", code="ITEM_COMPANY_MISMATCH"
            )
        is_qualified = _row_judgement(item, row)
        result, _ = QualityInspectionResult.objects.update_or_create(
            order=order,
            item=item,
            defaults={
                "measured_value": row.get("measured_value"),
                "text_value": str(row.get("text_value") or "")[:255],
                "is_qualified": is_qualified,
                "remark": str(row.get("remark") or "")[:255],
                "sort_order": row.get("sort_order") or index,
            },
        )
        saved.append(result)
    return saved


@transaction.atomic
def submit_order(order: QualityInspectionOrder) -> QualityInspectionOrder:
    """提交检验单：草稿 → 已提交。没有检验结果不允许提交。"""
    if order.status != QualityInspectionStatus.DRAFT:
        raise StateConflict("只有草稿状态的检验单可以提交。", code="INSPECTION_STATUS_INVALID")
    if not order.results.exists():
        raise ValidationFailed(
            "检验单还没有录入检验结果，不能提交。", code="INSPECTION_NO_RESULT"
        )
    order.status = QualityInspectionStatus.SUBMITTED
    order.save(update_fields=["status", "updated_at"])
    return order


def _alert_level(results: Iterable[QualityInspectionResult]) -> str:
    """不合格项越多，报警级别越高；只按事实分级，不做主观加权。"""
    failed = sum(1 for row in results if not row.is_qualified)
    if failed >= 3:
        return QualityAlertLevel.CRITICAL
    if failed == 2:
        return QualityAlertLevel.MAJOR
    return QualityAlertLevel.MINOR


def _ensure_alert(
    order: QualityInspectionOrder, results: list[QualityInspectionResult]
) -> QualityAlert:
    """不合格时生成质量报警；同一张检验单只保留一条（重复判定不重复报警）。"""
    existing = QualityAlert.objects.filter(order=order).first()
    if existing is not None:
        return existing
    failed_names = "、".join(row.item.name for row in results if not row.is_qualified)
    return QualityAlert.objects.create(
        company_id=order.company_id,
        alert_no=next_alert_no(),
        order=order,
        level=_alert_level(results),
        status=QualityAlertStatus.OPEN,
        title=f"检验单 {order.order_no} 判定不合格",
        description=f"不合格项目：{failed_names}" if failed_names else "",
        material=order.material,
        batch_no=order.batch_no,
    )


@transaction.atomic
def judge_order(
    order: QualityInspectionOrder,
    *,
    judgement: str | None = None,
    judge_remark: str = "",
    inspector: Any = None,
    inspected_at: Any = None,
) -> tuple[QualityInspectionOrder, QualityAlert | None]:
    """判定检验单：已提交 → 已判定。结论以**检验结果**为准，不接受与结果矛盾的判定。"""
    if order.status != QualityInspectionStatus.SUBMITTED:
        raise StateConflict("只有已提交的检验单可以判定。", code="INSPECTION_STATUS_INVALID")
    results = list(order.results.select_related("item").all())
    if not results:
        raise ValidationFailed("检验单没有检验结果，不能判定。", code="INSPECTION_NO_RESULT")

    failed = [row for row in results if not row.is_qualified]
    final = judgement or (QualityJudgement.FAILED if failed else QualityJudgement.PASSED)
    if final not in JUDGED_OPTIONS:
        raise ValidationFailed(
            f"判定结论不合法：{final}。", code="INVALID_JUDGEMENT", details={"allowed": sorted(JUDGED_OPTIONS)}
        )
    if failed and final == QualityJudgement.PASSED:
        raise StateConflict(
            "存在不合格项，不能判定为「合格」。", code="JUDGEMENT_CONFLICT"
        )
    if not failed and final == QualityJudgement.FAILED:
        raise StateConflict(
            "所有检验项目均合格，不能判定为「不合格」。", code="JUDGEMENT_CONFLICT"
        )
    if final == QualityJudgement.CONCESSION and not judge_remark.strip():
        raise ValidationFailed(
            "判定为「让步接收」必须写明判定说明与批准依据。", code="CONCESSION_REMARK_REQUIRED"
        )

    order.judgement = final
    order.status = QualityInspectionStatus.JUDGED
    order.judge_remark = judge_remark
    order.judged_at = business_now()
    if inspected_at is not None:
        order.inspected_at = inspected_at
    if inspector is not None:
        order.inspector = inspector
    order.save(
        update_fields=[
            "judgement", "status", "judge_remark", "judged_at", "inspected_at",
            "inspector", "updated_at",
        ]
    )

    alert: QualityAlert | None = None
    if final == QualityJudgement.FAILED:
        alert = _ensure_alert(order, results)
    return order, alert


@transaction.atomic
def close_order(order: QualityInspectionOrder) -> QualityInspectionOrder:
    """关闭检验单：已判定 → 已关闭。不合格报警没闭环时不允许关闭。"""
    if order.status != QualityInspectionStatus.JUDGED:
        raise StateConflict("只有已判定的检验单可以关闭。", code="INSPECTION_STATUS_INVALID")
    open_alerts = order.alerts.filter(
        status__in=[QualityAlertStatus.OPEN, QualityAlertStatus.HANDLING]
    )
    if open_alerts.exists():
        raise StateConflict(
            "该检验单的不合格报警还没有关闭，不能关闭检验单。", code="QUALITY_ALERT_OPEN"
        )
    order.status = QualityInspectionStatus.CLOSED
    order.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def handle_alert(alert: QualityAlert, *, handler: Any = None) -> QualityAlert:
    """开始处理质量报警：待处理 → 处理中。"""
    if alert.status != QualityAlertStatus.OPEN:
        raise StateConflict(
            "只有待处理的质量报警可以开始处理。", code="QUALITY_ALERT_STATUS_INVALID"
        )
    alert.status = QualityAlertStatus.HANDLING
    alert.handler = handler
    alert.handled_at = business_now()
    alert.save(update_fields=["status", "handler", "handled_at", "updated_at"])
    return alert


@transaction.atomic
def close_alert(alert: QualityAlert, *, remark: str) -> QualityAlert:
    """关闭质量报警：必须写清处理说明。"""
    if alert.status not in {QualityAlertStatus.OPEN, QualityAlertStatus.HANDLING}:
        raise StateConflict("该质量报警已经关闭。", code="QUALITY_ALERT_STATUS_INVALID")
    measure = (remark or "").strip()
    if not measure:
        raise ValidationFailed(
            "关闭质量报警必须填写处理说明。", code="ALERT_CLOSE_REMARK_REQUIRED"
        )
    alert.status = QualityAlertStatus.CLOSED
    alert.close_remark = measure
    alert.closed_at = business_now()
    alert.save(update_fields=["status", "close_remark", "closed_at", "updated_at"])
    return alert


@transaction.atomic
def publish_issue(issue: QualityIssue) -> QualityIssue:
    """发布知识库条目：草稿 → 已发布。"""
    if issue.status != QualityIssueStatus.DRAFT:
        raise StateConflict("只有草稿状态的问题可以发布。", code="QUALITY_ISSUE_STATUS_INVALID")
    issue.status = QualityIssueStatus.PUBLISHED
    issue.published_at = business_now()
    issue.save(update_fields=["status", "published_at", "updated_at"])
    return issue


@transaction.atomic
def archive_issue(issue: QualityIssue) -> QualityIssue:
    """归档知识库条目（发布的条目过时后归档，而不是删除）。"""
    if issue.status == QualityIssueStatus.ARCHIVED:
        raise StateConflict("该问题已经归档。", code="QUALITY_ISSUE_STATUS_INVALID")
    issue.status = QualityIssueStatus.ARCHIVED
    issue.save(update_fields=["status", "updated_at"])
    return issue


@transaction.atomic
def create_issue_from_alert(
    alert: QualityAlert,
    *,
    title: str,
    category: str = QualityIssueCategory.OTHER,
    cause: str = "",
    corrective_action: str = "",
    preventive_action: str = "",
    severity: str | None = None,
    tags: list[str] | None = None,
) -> QualityIssue:
    """把一次质量报警沉淀成知识库条目，并保留来源链路。"""
    return QualityIssue.objects.create(
        company_id=alert.company_id,
        issue_no=next_issue_no(),
        title=title,
        category=category,
        severity=severity or alert.level,
        phenomenon=alert.description or alert.title,
        cause=cause,
        corrective_action=corrective_action,
        preventive_action=preventive_action,
        material=alert.material,
        product_desc=alert.material.name if alert.material_id else "",
        tags=list(tags or []),
        source_order=alert.order,
        source_alert=alert,
        status=QualityIssueStatus.DRAFT,
    )


__all__ = [
    "ALERT_CODE_RULE",
    "ISSUE_CODE_RULE",
    "ITEM_CODE_RULE",
    "ORDER_CODE_RULE",
    "archive_issue",
    "close_alert",
    "close_order",
    "create_issue_from_alert",
    "create_order",
    "handle_alert",
    "judge_measured_value",
    "judge_order",
    "next_alert_no",
    "next_issue_no",
    "next_item_code",
    "next_order_no",
    "publish_issue",
    "record_results",
    "submit_order",
]
