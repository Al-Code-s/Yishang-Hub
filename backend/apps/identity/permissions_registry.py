"""权限与菜单注册表。

权限编码是后端与前端共同依赖的契约：
* bootstrap_system 依据本表写入 identity.Permission / identity.Menu；
* apps/core/checks.py 会校验视图声明的编码都在本表中，防止拼写错误悄悄放行。
"""

from __future__ import annotations

from typing import NamedTuple


class PermissionDef(NamedTuple):
    code: str
    name: str
    permission_type: str = "action"

    @property
    def module(self) -> str:
        return self.code.split(".")[0]

    @property
    def resource(self) -> str:
        return self.code.split(".")[1]

    @property
    def action(self) -> str:
        return ".".join(self.code.split(".")[2:])


PERMISSIONS: list[PermissionDef] = [
    # 工作台
    PermissionDef("analytics.dashboard.view", "查看工作台"),
    # 系统管理 - 用户
    PermissionDef("identity.user.view", "查看用户"),
    PermissionDef("identity.user.create", "新增用户"),
    PermissionDef("identity.user.update", "修改用户"),
    PermissionDef("identity.user.deactivate", "启用/停用用户"),
    PermissionDef("identity.user.reset_password", "重置用户密码"),
    PermissionDef("identity.user.unlock", "解除用户锁定"),
    PermissionDef("identity.user.assign_role", "分配用户角色"),
    # 系统管理 - 角色
    PermissionDef("identity.role.view", "查看角色"),
    PermissionDef("identity.role.create", "新增角色"),
    PermissionDef("identity.role.update", "修改角色"),
    PermissionDef("identity.role.delete", "删除角色"),
    PermissionDef("identity.role.assign_permission", "配置角色权限与数据范围"),
    PermissionDef("identity.menu.view", "查看菜单"),
    PermissionDef("identity.permission.view", "查看权限点"),
    PermissionDef("identity.log.view", "查看登录记录"),
    # 组织与工厂
    PermissionDef("factory.company.view", "查看公司"),
    PermissionDef("factory.company.create", "新增公司"),
    PermissionDef("factory.company.update", "修改公司"),
    PermissionDef("factory.department.view", "查看部门"),
    PermissionDef("factory.department.create", "新增部门"),
    PermissionDef("factory.department.update", "修改部门"),
    PermissionDef("factory.factory.view", "查看工厂"),
    PermissionDef("factory.factory.create", "新增工厂"),
    PermissionDef("factory.factory.update", "修改工厂"),
    PermissionDef("factory.workshop.view", "查看车间"),
    PermissionDef("factory.workshop.create", "新增车间"),
    PermissionDef("factory.workshop.update", "修改车间"),
    PermissionDef("factory.line.view", "查看线体"),
    PermissionDef("factory.line.create", "新增线体"),
    PermissionDef("factory.line.update", "修改线体"),
    PermissionDef("factory.station.view", "查看工位"),
    PermissionDef("factory.station.create", "新增工位"),
    PermissionDef("factory.station.update", "修改工位"),
    PermissionDef("factory.employee.view", "查看员工"),
    PermissionDef("factory.employee.create", "新增员工"),
    PermissionDef("factory.employee.update", "修改员工"),
    PermissionDef("factory.shift.view", "查看班次"),
    PermissionDef("factory.shift.create", "新增班次"),
    PermissionDef("factory.shift.update", "修改班次"),
    PermissionDef("factory.team.view", "查看班组"),
    PermissionDef("factory.team.create", "新增班组"),
    PermissionDef("factory.team.update", "修改班组"),
    # 基础资料 - 计量单位
    PermissionDef("masterdata.uom.view", "查看计量单位"),
    PermissionDef("masterdata.uom.create", "新增计量单位"),
    PermissionDef("masterdata.uom.update", "修改计量单位"),
    # 基础资料 - 物料分类
    PermissionDef("masterdata.material_category.view", "查看物料分类"),
    PermissionDef("masterdata.material_category.create", "新增物料分类"),
    PermissionDef("masterdata.material_category.update", "修改物料分类"),
    # 基础资料 - 物料
    PermissionDef("masterdata.material.view", "查看物料"),
    PermissionDef("masterdata.material.create", "新增物料"),
    PermissionDef("masterdata.material.update", "修改物料"),
    PermissionDef("masterdata.material.deactivate", "启用/停用物料"),
    # 基础资料 - 颜色 / 尺码
    PermissionDef("masterdata.color.view", "查看颜色"),
    PermissionDef("masterdata.color.create", "新增颜色"),
    PermissionDef("masterdata.color.update", "修改颜色"),
    PermissionDef("masterdata.size.view", "查看尺码"),
    PermissionDef("masterdata.size.create", "新增尺码"),
    PermissionDef("masterdata.size.update", "修改尺码"),
    # 基础资料 - 款式与 SKU
    PermissionDef("masterdata.style.view", "查看款式"),
    PermissionDef("masterdata.style.create", "新增款式"),
    PermissionDef("masterdata.style.update", "修改款式"),
    PermissionDef("masterdata.sku.view", "查看 SKU"),
    PermissionDef("masterdata.sku.create", "新增 SKU"),
    PermissionDef("masterdata.sku.update", "修改 SKU"),
    PermissionDef("masterdata.sku.generate", "批量生成 SKU"),
    # 基础资料 - 标识（条码 / 批次 / 卷号 / 箱码 / RFID / 载具）
    PermissionDef("masterdata.identifier.view", "查看标识"),
    PermissionDef("masterdata.identifier.create", "新增标识"),
    PermissionDef("masterdata.identifier.update", "修改标识"),
    PermissionDef("masterdata.identifier.deactivate", "停用标识"),
    # 仓储 - 仓库 / 库区 / 储位
    # 仓储 - 库存占用（销售发货「先占用、后发货」的业务规则依赖它）
    PermissionDef("wms.inventory.reserve", "库存占用"),
    PermissionDef("wms.inventory.release", "释放库存占用"),
    # 销售管理 - 销售订单
    PermissionDef("sales.order.view", "查看销售订单"),
    PermissionDef("sales.order.create", "新增销售订单"),
    PermissionDef("sales.order.update", "修改/取消销售订单"),
    PermissionDef("sales.order.submit", "提交销售订单审批"),
    PermissionDef("sales.order.close", "关闭销售订单"),
    PermissionDef("sales.order.reserve", "销售订单库存占用"),
    PermissionDef("sales.order.release", "释放销售订单库存占用"),
    # 销售管理 - 发货
    PermissionDef("sales.shipment.view", "查看销售发货单"),
    PermissionDef("sales.shipment.create", "新增销售发货单"),
    PermissionDef("sales.shipment.update", "修改/取消销售发货单"),
    PermissionDef("sales.shipment.post", "销售发货出库过账"),
    # 销售管理 - 退货
    PermissionDef("sales.return.view", "查看销售退货单"),
    PermissionDef("sales.return.create", "新增销售退货单"),
    PermissionDef("sales.return.update", "修改/取消销售退货单"),
    PermissionDef("sales.return.post", "销售退货收货过账"),
    PermissionDef("sales.return.inspect", "销售退货检验判定"),
    # 采购管理 - 采购申请
    PermissionDef("procurement.requisition.view", "查看采购申请"),
    PermissionDef("procurement.requisition.create", "新增采购申请"),
    PermissionDef("procurement.requisition.update", "修改/取消采购申请"),
    PermissionDef("procurement.requisition.submit", "提交采购申请审批"),
    # 采购管理 - 采购订单
    PermissionDef("procurement.order.view", "查看采购订单"),
    PermissionDef("procurement.order.create", "新增采购订单"),
    PermissionDef("procurement.order.update", "修改/取消采购订单"),
    PermissionDef("procurement.order.submit", "提交采购订单审批"),
    PermissionDef("procurement.order.close", "关闭采购订单"),
    PermissionDef(
        "procurement.order.override_supplier", "采购订单供应商例外授权"
    ),
    # 采购管理 - 收货与检验
    PermissionDef("procurement.receipt.view", "查看采购收货单"),
    PermissionDef("procurement.receipt.create", "新增采购收货单"),
    PermissionDef("procurement.receipt.update", "修改/取消采购收货单"),
    PermissionDef("procurement.receipt.post", "采购收货过账（记待检库存）"),
    PermissionDef("procurement.receipt.inspect", "来料检验判定（质量放行）"),
    PermissionDef("wms.warehouse.view", "查看仓库"),
    PermissionDef("wms.warehouse.create", "新增仓库"),
    PermissionDef("wms.warehouse.update", "修改仓库"),
    PermissionDef("wms.zone.view", "查看库区"),
    PermissionDef("wms.zone.create", "新增库区"),
    PermissionDef("wms.zone.update", "修改库区"),
    PermissionDef("wms.location.view", "查看储位"),
    PermissionDef("wms.location.create", "新增储位"),
    PermissionDef("wms.location.update", "修改储位"),
    # 仓储 - 库存（统一库存服务，阶段 2）
    PermissionDef("wms.inventory.view", "查看库存余额与流水"),
    PermissionDef("wms.document.view", "查看库存单据"),
    PermissionDef("wms.document.create", "创建库存单据"),
    PermissionDef("wms.document.update", "修改库存单据草稿"),
    PermissionDef("wms.document.post", "库存单据过账"),
    PermissionDef("wms.document.reverse", "库存单据冲销"),
    PermissionDef("wms.quality.release", "库存质量放行"),
    # 审批
    PermissionDef("workflow.template.view", "查看审批模板"),
    PermissionDef("workflow.template.create", "新增审批模板"),
    PermissionDef("workflow.template.update", "修改审批模板"),
    PermissionDef("workflow.instance.view", "查看审批单"),
    PermissionDef("workflow.instance.submit", "提交审批"),
    PermissionDef("workflow.instance.approve", "审批通过/驳回"),
    PermissionDef("workflow.instance.withdraw", "撤回审批"),
    # 客户管理
    PermissionDef("crm.customer.view", "查看客户"),
    PermissionDef("crm.customer.create", "新增客户"),
    PermissionDef("crm.customer.update", "修改客户"),
    PermissionDef("crm.customer.deactivate", "启用/停用客户"),
    PermissionDef("crm.customer_contact.view", "查看客户联系人"),
    PermissionDef("crm.customer_contact.create", "新增客户联系人"),
    PermissionDef("crm.customer_contact.update", "修改客户联系人"),
    # 客户管理 - 客户投诉（待受理 → 处理中 → 已解决 → 已关闭）
    PermissionDef("crm.complaint.view", "查看客户投诉"),
    PermissionDef("crm.complaint.create", "登记客户投诉"),
    PermissionDef("crm.complaint.update", "修改客户投诉"),
    PermissionDef("crm.complaint.handle", "受理与处理客户投诉"),
    PermissionDef("crm.complaint.close", "关闭客户投诉"),
    # 客户管理 - 产品评价（待回复 → 已回复 → 已关闭）
    PermissionDef("crm.product_review.view", "查看产品评价"),
    PermissionDef("crm.product_review.create", "登记产品评价"),
    PermissionDef("crm.product_review.update", "修改产品评价"),
    PermissionDef("crm.product_review.reply", "回复产品评价"),
    PermissionDef("crm.product_review.close", "关闭产品评价"),
    # 供应商管理
    PermissionDef("srm.supplier.view", "查看供应商"),
    PermissionDef("srm.supplier.create", "新增供应商"),
    PermissionDef("srm.supplier.update", "修改供应商"),
    PermissionDef("srm.supplier.deactivate", "启用/停用供应商"),
    PermissionDef("srm.supplier_contact.view", "查看供应商联系人"),
    PermissionDef("srm.supplier_contact.create", "新增供应商联系人"),
    PermissionDef("srm.supplier_contact.update", "修改供应商联系人"),
    PermissionDef("srm.supplier_qualification.view", "查看供应商资质"),
    PermissionDef("srm.supplier_qualification.create", "新增供应商资质"),
    PermissionDef("srm.supplier_qualification.update", "修改供应商资质"),
    # 供应商管理 - 五维量化评价与权重配置
    PermissionDef("srm.evaluation_weight.view", "查看供应商评价权重"),
    PermissionDef("srm.evaluation_weight.create", "新增供应商评价权重"),
    PermissionDef("srm.evaluation_weight.update", "修改评价权重（派生新版本）"),
    PermissionDef("srm.evaluation.view", "查看供应商评价"),
    PermissionDef("srm.evaluation.create", "发起供应商评价"),
    PermissionDef("srm.evaluation.update", "录入或修改评价明细"),
    PermissionDef("srm.evaluation.publish", "供应商评价生效"),
    PermissionDef("srm.evaluation.archive", "归档供应商评价"),
    # 计划管理 - BOM（物料清单）
    PermissionDef("planning.bom.view", "查看 BOM"),
    PermissionDef("planning.bom.create", "新增 BOM"),
    PermissionDef("planning.bom.update", "修改 BOM 草稿"),
    PermissionDef("planning.bom.submit", "提交 BOM 审批"),
    PermissionDef("planning.bom.obsolete", "作废 BOM 版本"),
    # 计划管理 - 工艺路线
    PermissionDef("planning.routing.view", "查看工艺路线"),
    PermissionDef("planning.routing.create", "新增工艺路线"),
    PermissionDef("planning.routing.update", "修改工艺路线草稿"),
    PermissionDef("planning.routing.submit", "提交工艺路线审批"),
    PermissionDef("planning.routing.obsolete", "作废工艺路线版本"),
    # 计划管理 - MRP 运算
    PermissionDef("planning.mrp.view", "查看 MRP 运行与建议"),
    PermissionDef("planning.mrp.run", "运行 MRP 计算"),
    PermissionDef("planning.mrp.convert", "MRP 建议转单"),
    PermissionDef("planning.mrp.cancel", "取消 MRP 建议"),
    PermissionDef("planning.mrp.archive", "归档 MRP 运行"),
    # 生产执行 - 生产工单
    PermissionDef("mes.order.view", "查看生产工单"),
    PermissionDef("mes.order.create", "新增生产工单"),
    PermissionDef("mes.order.update", "修改生产工单"),
    PermissionDef("mes.order.release", "下达生产工单"),
    PermissionDef("mes.order.issue", "生产领料"),
    PermissionDef("mes.order.complete", "生产完工与完工入库"),
    PermissionDef("mes.order.close", "关闭生产工单"),
    PermissionDef("mes.order.cancel", "取消生产工单"),
    # 生产执行 - 生产报工
    PermissionDef("mes.report.view", "查看生产报工"),
    PermissionDef("mes.report.create", "新增生产报工"),
    # 质量管理 - 检验项目
    PermissionDef("qms.inspection_item.view", "查看检验项目"),
    PermissionDef("qms.inspection_item.create", "新增检验项目"),
    PermissionDef("qms.inspection_item.update", "修改检验项目"),
    # 质量管理 - 检验单与结果判定
    PermissionDef("qms.inspection.view", "查看检验单与质量监测"),
    PermissionDef("qms.inspection.create", "新增检验单"),
    PermissionDef("qms.inspection.update", "修改检验单与录入检验结果"),
    PermissionDef("qms.inspection.submit", "提交检验单"),
    PermissionDef("qms.inspection.judge", "判定检验单"),
    PermissionDef("qms.inspection.close", "关闭检验单"),
    # 质量管理 - 质量报警
    PermissionDef("qms.alert.view", "查看质量报警"),
    PermissionDef("qms.alert.handle", "处理质量报警"),
    PermissionDef("qms.alert.close", "关闭质量报警"),
    # 质量管理 - 质量问题知识库
    PermissionDef("qms.issue.view", "查看质量问题知识库"),
    PermissionDef("qms.issue.create", "新增质量问题条目"),
    PermissionDef("qms.issue.update", "修改质量问题条目"),
    PermissionDef("qms.issue.publish", "发布质量问题条目"),
    PermissionDef("qms.issue.archive", "归档质量问题条目"),
    # 设备管理 - 设备类型
    PermissionDef("equipment.type.view", "查看设备类型"),
    PermissionDef("equipment.type.create", "新增设备类型"),
    PermissionDef("equipment.type.update", "修改设备类型"),
    # 设备管理 - 设备台账
    PermissionDef("equipment.equipment.view", "查看设备台账"),
    PermissionDef("equipment.equipment.create", "新增设备台账"),
    PermissionDef("equipment.equipment.update", "修改设备台账"),
    PermissionDef("equipment.equipment.deactivate", "启用/停用设备"),
    # 设备管理 - 设备零部件
    PermissionDef("equipment.part.view", "查看设备零部件"),
    PermissionDef("equipment.part.create", "新增设备零部件"),
    PermissionDef("equipment.part.update", "修改设备零部件"),
    # 设备管理 - 备品备件
    PermissionDef("equipment.spare_part.view", "查看备品备件"),
    PermissionDef("equipment.spare_part.create", "新增备品备件"),
    PermissionDef("equipment.spare_part.update", "修改备品备件"),
    PermissionDef("equipment.spare_part.deactivate", "启用/停用备品备件"),
    # 设备管理 - 备件库存台账
    PermissionDef("equipment.spare_part_stock.view", "查看备件库存台账"),
    # 设备管理 - 设备保养
    PermissionDef("equipment.maintenance_item.view", "查看保养项目"),
    PermissionDef("equipment.maintenance_item.create", "新增保养项目"),
    PermissionDef("equipment.maintenance_item.update", "修改保养项目"),
    PermissionDef("equipment.maintenance_plan.view", "查看保养计划"),
    PermissionDef("equipment.maintenance_plan.create", "新增保养计划"),
    PermissionDef("equipment.maintenance_plan.update", "修改保养计划"),
    PermissionDef("equipment.maintenance_task.view", "查看保养任务"),
    PermissionDef("equipment.maintenance_task.create", "新增保养任务"),
    PermissionDef("equipment.maintenance_task.update", "修改保养任务"),
    PermissionDef("equipment.maintenance_task.execute", "执行保养任务"),
    PermissionDef("equipment.maintenance_record.view", "查看保养记录"),
    PermissionDef("equipment.maintenance_record.create", "新增保养记录"),
    PermissionDef("equipment.maintenance_record.update", "修改保养记录"),
    # 设备管理 - 设备维修
    PermissionDef("equipment.fault_report.view", "查看故障保修"),
    PermissionDef("equipment.fault_report.create", "新增故障保修"),
    PermissionDef("equipment.fault_report.update", "修改故障保修"),
    PermissionDef("equipment.repair_task.view", "查看维修任务"),
    PermissionDef("equipment.repair_task.create", "新增维修任务"),
    PermissionDef("equipment.repair_task.update", "修改维修任务"),
    PermissionDef("equipment.repair_task.execute", "执行维修任务"),
    PermissionDef("equipment.repair_record.view", "查看维修记录"),
    PermissionDef("equipment.repair_record.create", "新增维修记录"),
    PermissionDef("equipment.repair_record.update", "修改维修记录"),
    # 设备管理 - 点巡检
    PermissionDef("equipment.inspection_item.view", "查看点巡检项目"),
    PermissionDef("equipment.inspection_item.create", "新增点巡检项目"),
    PermissionDef("equipment.inspection_item.update", "修改点巡检项目"),
    PermissionDef("equipment.inspection_task.view", "查看点巡检任务"),
    PermissionDef("equipment.inspection_task.create", "新增点巡检任务"),
    PermissionDef("equipment.inspection_task.update", "修改点巡检任务"),
    PermissionDef("equipment.inspection_task.execute", "执行点巡检任务"),
    PermissionDef("equipment.inspection_record.view", "查看点巡检记录"),
    PermissionDef("equipment.inspection_record.create", "新增点巡检记录"),
    PermissionDef("equipment.inspection_record.update", "修改点巡检记录"),
    # 设备管理 - 设备异常上报
    PermissionDef("equipment.abnormal_type.view", "查看异常类型"),
    PermissionDef("equipment.abnormal_type.create", "新增异常类型"),
    PermissionDef("equipment.abnormal_type.update", "修改异常类型"),
    PermissionDef("equipment.abnormal_task.view", "查看异常任务"),
    PermissionDef("equipment.abnormal_task.create", "新增异常任务"),
    PermissionDef("equipment.abnormal_task.update", "修改异常任务"),
    PermissionDef("equipment.abnormal_task.handle", "处理异常任务"),
    PermissionDef("equipment.abnormal_record.view", "查看异常记录"),
    PermissionDef("equipment.abnormal_record.create", "新增异常记录"),
    PermissionDef("equipment.abnormal_record.update", "修改异常记录"),
    # 能源管理 - 首页与监控
    PermissionDef("ems.home.view", "查看能源首页"),
    PermissionDef("ems.monitor.view", "查看设备监控"),
    # 能源管理 - 表计与区域基础管理
    PermissionDef("ems.meter.view", "查看计量设备"),
    PermissionDef("ems.meter.create", "新增计量设备"),
    PermissionDef("ems.meter.update", "修改计量设备"),
    PermissionDef("ems.area.view", "查看计量区域"),
    PermissionDef("ems.area.create", "新增计量区域"),
    PermissionDef("ems.area.update", "修改计量区域"),
    # 能源管理 - 价格与阈值
    PermissionDef("ems.price.view", "查看能源价格"),
    PermissionDef("ems.price.create", "新增能源价格"),
    PermissionDef("ems.price.update", "修改能源价格"),
    PermissionDef("ems.threshold.view", "查看能源阈值"),
    PermissionDef("ems.threshold.create", "新增能源阈值"),
    PermissionDef("ems.threshold.update", "修改能源阈值"),
    # 能源管理 - 抄表与运行记录
    PermissionDef("ems.reading.view", "查看抄表记录"),
    PermissionDef("ems.reading.create", "抄表录入"),
    PermissionDef("ems.run_record.view", "查看设备运行记录"),
    PermissionDef("ems.run_record.create", "开始设备运行记录"),
    PermissionDef("ems.run_record.execute", "结束/取消设备运行记录"),
    # 能源管理 - 报警
    PermissionDef("ems.alarm.view", "查看能源报警"),
    PermissionDef("ems.alarm.create", "上报能源报警"),
    PermissionDef("ems.alarm.update", "修改能源报警"),
    PermissionDef("ems.alarm.handle", "处理与关闭能源报警"),
    # 能源管理 - 统计与报表
    PermissionDef("ems.statistics.view", "查看能耗统计与看板"),
    PermissionDef("ems.report.view", "查看与导出能耗报表"),
    # 生产物流管理
    PermissionDef("logistics.device.view", "查看自动化设备"),
    PermissionDef("logistics.device.create", "新增自动化设备"),
    PermissionDef("logistics.device.update", "修改自动化设备与状态"),
    PermissionDef("logistics.task.view", "查看物流任务"),
    PermissionDef("logistics.task.create", "新增物流任务"),
    PermissionDef("logistics.task.update", "修改/下发/取消物流任务"),
    PermissionDef("logistics.task.execute", "执行物流任务"),
    PermissionDef("logistics.log.view", "查看物流操作日志"),
    # 安全环保管理 - 安全管理
    PermissionDef("ehs.regulation.view", "查看安全制度"),
    PermissionDef("ehs.regulation.create", "新增安全制度"),
    PermissionDef("ehs.regulation.update", "修改安全制度"),
    PermissionDef("ehs.training.view", "查看安全培训"),
    PermissionDef("ehs.training.create", "新增安全培训"),
    PermissionDef("ehs.training.update", "修改安全培训"),
    PermissionDef("ehs.hazard.view", "查看隐患排查"),
    PermissionDef("ehs.hazard.create", "上报隐患"),
    PermissionDef("ehs.hazard.update", "修改隐患"),
    PermissionDef("ehs.hazard.rectify", "隐患整改与提交验收"),
    PermissionDef("ehs.hazard.verify", "隐患验收"),
    PermissionDef("ehs.emergency_plan.view", "查看应急预案"),
    PermissionDef("ehs.emergency_plan.create", "新增应急预案"),
    PermissionDef("ehs.emergency_plan.update", "修改应急预案"),
    PermissionDef("ehs.accident.view", "查看事故记录"),
    PermissionDef("ehs.accident.create", "上报事故"),
    PermissionDef("ehs.accident.update", "修改事故记录"),
    PermissionDef("ehs.accident.handle", "事故调查、整改与关闭"),
    # 安全环保管理 - 环保管理
    PermissionDef("ehs.env_monitor.view", "查看排污监测"),
    PermissionDef("ehs.env_monitor.create", "新增排污监测"),
    PermissionDef("ehs.env_monitor.update", "修改排污监测"),
    PermissionDef("ehs.waste.view", "查看固废危废台账"),
    PermissionDef("ehs.waste.create", "新增固废危废台账"),
    PermissionDef("ehs.waste.update", "修改固废危废台账"),
    PermissionDef("ehs.compliance.view", "查看环保合规检查"),
    PermissionDef("ehs.compliance.create", "新增环保合规检查"),
    PermissionDef("ehs.compliance.update", "修改/关闭环保合规检查"),
    # 安全环保管理 - 消防管理
    PermissionDef("ehs.fire_facility.view", "查看消防设施"),
    PermissionDef("ehs.fire_facility.create", "新增消防设施"),
    PermissionDef("ehs.fire_facility.update", "修改消防设施"),
    PermissionDef("ehs.fire_drill.view", "查看消防演练"),
    PermissionDef("ehs.fire_drill.create", "新增消防演练"),
    PermissionDef("ehs.fire_drill.update", "修改消防演练"),
    PermissionDef("ehs.permit.view", "查看作业许可"),
    PermissionDef("ehs.permit.create", "申请作业许可"),
    PermissionDef("ehs.permit.update", "修改作业许可"),
    PermissionDef("ehs.permit.approve", "审批作业许可"),
    PermissionDef("ehs.permit.execute", "作业开工与完工"),
    PermissionDef("ehs.permit.accept", "作业许可现场验收"),
    # 安全环保管理 - 设备设施安全
    PermissionDef("ehs.safety_check.view", "查看安全检查"),
    PermissionDef("ehs.safety_check.create", "新增安全检查"),
    PermissionDef("ehs.safety_check.update", "修改安全检查"),
    PermissionDef("ehs.special_equipment.view", "查看特种设备检验"),
    PermissionDef("ehs.special_equipment.create", "新增特种设备检验"),
    PermissionDef("ehs.special_equipment.update", "修改特种设备检验"),
    PermissionDef("ehs.log.view", "查看安全环保操作日志"),
    # 设备数采与监控（IoT：只读采集，不包含控制下发）
    PermissionDef("iot.connection.view", "查看数采连接"),
    PermissionDef("iot.connection.create", "新增数采连接"),
    PermissionDef("iot.connection.update", "修改数采连接"),
    PermissionDef("iot.gateway.view", "查看数采设备"),
    PermissionDef("iot.gateway.create", "新增数采设备"),
    PermissionDef("iot.gateway.update", "修改数采设备"),
    PermissionDef("iot.gateway.rotate_token", "生成/轮换设备令牌"),
    PermissionDef("iot.point.view", "查看采集测点"),
    PermissionDef("iot.point.create", "新增采集测点"),
    PermissionDef("iot.point.update", "修改采集测点"),
    PermissionDef("iot.reading.view", "查看采集读数"),
    PermissionDef("iot.message.view", "查看采集日志"),
    PermissionDef("iot.monitor.view", "查看设备监控"),
    # 公共
    PermissionDef("core.dictionary.view", "查看数据字典"),
    PermissionDef("core.dictionary.create", "新增数据字典"),
    PermissionDef("core.dictionary.update", "修改数据字典"),
    PermissionDef("core.code_rule.view", "查看编码规则"),
    PermissionDef("core.code_rule.create", "新增编码规则"),
    PermissionDef("core.code_rule.update", "修改编码规则"),
    PermissionDef("core.audit.view", "查看审计日志"),
    PermissionDef("core.attachment.upload", "上传附件"),
    PermissionDef("core.attachment.download", "下载附件"),
    PermissionDef("core.attachment.delete", "删除附件"),
    PermissionDef("core.notification.view", "查看通知"),
    PermissionDef("core.progress.view", "查看实施进度"),
    # 内部协同
    PermissionDef("integration.outbox.view", "查看发件箱事件"),
    PermissionDef("integration.outbox.retry", "重试发件箱事件"),
    PermissionDef("integration.document_link.view", "查看单据关系"),
]


class MenuDef(NamedTuple):
    code: str
    name: str
    parent: str | None
    path: str
    component: str
    icon: str
    sort_order: int
    menu_type: str = "page"
    permission_code: str = ""


# 只登记**已实际实现**的页面；未实施的模块不放置伪可用菜单（AGENTS.md 一、三.3）
MENUS: list[MenuDef] = [
    # 工作台绑定 analytics.dashboard.view：能看到看板的用户就应看到入口
    MenuDef(
        "workspace", "工作台", None, "/workspace", "views/workspace/Index.vue", "Odometer", 10,
        "page", "analytics.dashboard.view",
    ),
    MenuDef("masterdata", "基础资料", None, "/masterdata", "Layout", "Files", 20, "directory"),
    MenuDef(
        "masterdata.material", "物料档案", "masterdata", "/masterdata/materials",
        "views/masterdata/MaterialList.vue", "Box", 21, "page", "masterdata.material.view",
    ),
    MenuDef(
        "masterdata.material-category", "物料分类", "masterdata", "/masterdata/material-categories",
        "views/masterdata/MaterialCategoryList.vue", "Collection", 22, "page",
        "masterdata.material_category.view",
    ),
    MenuDef(
        "masterdata.style", "款式档案", "masterdata", "/masterdata/styles",
        "views/masterdata/StyleList.vue", "Suitcase", 23, "page", "masterdata.style.view",
    ),
    MenuDef(
        "masterdata.sku", "SKU 档案", "masterdata", "/masterdata/skus",
        "views/masterdata/SkuList.vue", "Grid", 24, "page", "masterdata.sku.view",
    ),
    MenuDef(
        "masterdata.color-size", "颜色与尺码", "masterdata", "/masterdata/color-size",
        "views/masterdata/ColorSizeList.vue", "Brush", 25, "page", "masterdata.color.view",
    ),
    MenuDef(
        "masterdata.uom", "计量单位", "masterdata", "/masterdata/uoms",
        "views/masterdata/UomList.vue", "ScaleToOriginal", 26, "page", "masterdata.uom.view",
    ),
    MenuDef("factory", "工厂与排班", None, "/factory", "Layout", "OfficeBuilding", 30, "directory"),
    MenuDef(
        "factory.company", "公司", "factory", "/factory/companies",
        "views/factory/CompanyList.vue", "Postcard", 31, "page", "factory.company.view",
    ),
    MenuDef(
        "factory.department", "部门", "factory", "/factory/departments",
        "views/factory/DepartmentList.vue", "Share", 32, "page", "factory.department.view",
    ),
    MenuDef(
        "factory.factory", "工厂", "factory", "/factory/factories",
        "views/factory/FactoryList.vue", "OfficeBuilding", 33, "page", "factory.factory.view",
    ),
    MenuDef(
        "factory.workshop", "车间与线体", "factory", "/factory/workshops",
        "views/factory/WorkshopList.vue", "SetUp", 34, "page", "factory.workshop.view",
    ),
    MenuDef(
        "factory.employee", "员工档案", "factory", "/factory/employees",
        "views/factory/EmployeeList.vue", "User", 35, "page", "factory.employee.view",
    ),
    MenuDef(
        "factory.team", "班组", "factory", "/factory/teams",
        "views/factory/TeamList.vue", "UserFilled", 36, "page", "factory.team.view",
    ),
    MenuDef(
        "factory.shift", "班次", "factory", "/factory/shifts",
        "views/factory/ShiftList.vue", "Clock", 37, "page", "factory.shift.view",
    ),
    MenuDef("crm", "客户管理", None, "/crm", "Layout", "Tickets", 40, "directory"),
    MenuDef(
        "crm.customer", "客户档案", "crm", "/crm/customers",
        "views/crm/CustomerList.vue", "Avatar", 41, "page", "crm.customer.view",
    ),
    MenuDef(
        "crm.customer-contact", "客户联系人", "crm", "/crm/customer-contacts",
        "views/crm/CustomerContactList.vue", "Phone", 42, "page", "crm.customer_contact.view",
    ),
    MenuDef(
        "crm.complaint", "客户投诉", "crm", "/crm/complaints",
        "views/crm/ComplaintList.vue", "Warning", 43, "page", "crm.complaint.view",
    ),
    MenuDef(
        "crm.product-review", "产品评价", "crm", "/crm/product-reviews",
        "views/crm/ProductReviewList.vue", "Star", 44, "page", "crm.product_review.view",
    ),
    MenuDef("sales", "销售管理", None, "/sales", "Layout", "Sell", 50, "directory"),
    MenuDef(
        "sales.order", "销售订单", "sales", "/sales/orders",
        "views/sales/SalesOrderList.vue", "Document", 51, "page", "sales.order.view",
    ),
    MenuDef(
        "sales.shipment", "销售发货", "sales", "/sales/shipments",
        "views/sales/SalesShipmentList.vue", "Van", 52, "page", "sales.shipment.view",
    ),
    MenuDef(
        "sales.return", "销售退货", "sales", "/sales/returns",
        "views/sales/SalesReturnList.vue", "RefreshLeft", 53, "page", "sales.return.view",
    ),
    MenuDef("srm", "供应商管理", None, "/srm", "Layout", "Shop", 60, "directory"),
    MenuDef(
        "srm.supplier", "供应商档案", "srm", "/srm/suppliers",
        "views/srm/SupplierList.vue", "OfficeBuilding", 61, "page", "srm.supplier.view",
    ),
    MenuDef(
        "srm.supplier-contact", "供应商联系人", "srm", "/srm/supplier-contacts",
        "views/srm/SupplierContactList.vue", "PhoneFilled", 62, "page", "srm.supplier_contact.view",
    ),
    MenuDef(
        "srm.supplier-qualification", "供应商资质", "srm", "/srm/supplier-qualifications",
        "views/srm/SupplierQualificationList.vue", "Medal", 63, "page",
        "srm.supplier_qualification.view",
    ),
    MenuDef(
        "srm.evaluation-weight", "评价权重配置", "srm", "/srm/evaluation-weights",
        "views/srm/SupplierEvaluationWeightList.vue", "ScaleToOriginal", 64, "page",
        "srm.evaluation_weight.view",
    ),
    MenuDef(
        "srm.supplier-evaluation", "供应商评价", "srm", "/srm/supplier-evaluations",
        "views/srm/SupplierEvaluationList.vue", "TrendCharts", 65, "page",
        "srm.evaluation.view",
    ),
    MenuDef("procurement", "采购管理", None, "/procurement", "Layout", "ShoppingCart", 70, "directory"),
    MenuDef(
        "procurement.requisition", "采购申请", "procurement", "/procurement/requisitions",
        "views/procurement/RequisitionList.vue", "Document", 71, "page",
        "procurement.requisition.view",
    ),
    MenuDef(
        "procurement.order", "采购订单", "procurement", "/procurement/orders",
        "views/procurement/PurchaseOrderList.vue", "ShoppingCart", 72, "page",
        "procurement.order.view",
    ),
    MenuDef(
        "procurement.receipt", "采购收货", "procurement", "/procurement/receipts",
        "views/procurement/GoodsReceiptList.vue", "Van", 73, "page",
        "procurement.receipt.view",
    ),
    MenuDef("planning", "计划管理", None, "/planning", "Layout", "Calendar", 75, "directory"),
    MenuDef(
        "planning.bom", "物料清单（BOM）", "planning", "/planning/boms",
        "views/planning/BomList.vue", "Files", 76, "page", "planning.bom.view",
    ),
    MenuDef(
        "planning.routing", "工艺路线", "planning", "/planning/routings",
        "views/planning/RoutingList.vue", "Guide", 77, "page", "planning.routing.view",
    ),
    MenuDef(
        "planning.mrp", "MRP 运算", "planning", "/planning/mrp-runs",
        "views/planning/MrpRunList.vue", "TrendCharts", 78, "page", "planning.mrp.view",
    ),
    MenuDef(
        "planning.mrp_suggestion", "缺料与建议", "planning", "/planning/mrp-suggestions",
        "views/planning/MrpSuggestionList.vue", "Warning", 79, "page", "planning.mrp.view",
    ),
    MenuDef("mes", "生产执行", None, "/mes", "Layout", "SetUp", 79, "directory"),
    MenuDef(
        "mes.production-order", "生产工单", "mes", "/mes/production-orders",
        "views/mes/ProductionOrderList.vue", "Tickets", 791, "page", "mes.order.view",
    ),
    MenuDef(
        "mes.production-report", "生产报工", "mes", "/mes/production-reports",
        "views/mes/ProductionReportList.vue", "DocumentChecked", 792, "page",
        "mes.report.view",
    ),
    MenuDef("wms", "仓储管理", None, "/wms", "Layout", "Box", 80, "directory"),
    MenuDef(
        "wms.warehouse", "仓库与储位", "wms", "/wms/warehouses",
        "views/wms/WarehouseList.vue", "House", 81, "page", "wms.warehouse.view",
    ),
    MenuDef(
        "wms.inventory-balance", "库存余额", "wms", "/wms/inventory-balances",
        "views/wms/InventoryBalanceList.vue", "Coin", 82, "page", "wms.inventory.view",
    ),
    MenuDef(
        "wms.inventory-transaction", "库存流水", "wms", "/wms/inventory-transactions",
        "views/wms/InventoryTransactionList.vue", "Tickets", 83, "page", "wms.inventory.view",
    ),
    MenuDef(
        "wms.inventory-document", "库存单据", "wms", "/wms/inventory-documents",
        "views/wms/InventoryDocumentList.vue", "Document", 84, "page", "wms.document.view",
    ),
    MenuDef("qms", "质量管理", None, "/qms", "Layout", "Checked", 85, "directory"),
    MenuDef(
        "qms.inspection-item", "检验项目", "qms", "/qms/inspection-items",
        "views/qms/InspectionItemList.vue", "List", 86, "page", "qms.inspection_item.view",
    ),
    MenuDef(
        "qms.inspection", "检验单", "qms", "/qms/inspections",
        "views/qms/InspectionOrderList.vue", "DocumentChecked", 87, "page",
        "qms.inspection.view",
    ),
    MenuDef(
        "qms.alert", "质量报警", "qms", "/qms/alerts",
        "views/qms/QualityAlertList.vue", "Warning", 88, "page", "qms.alert.view",
    ),
    MenuDef(
        "qms.issue", "质量问题知识库", "qms", "/qms/issues",
        "views/qms/QualityIssueList.vue", "Notebook", 89, "page", "qms.issue.view",
    ),
    MenuDef("equipment", "设备管理", None, "/equipment", "Layout", "Tools", 90, "directory"),
    MenuDef(
        "equipment.equipment-type", "设备类型管理", "equipment", "/equipment/types",
        "views/equipment/EquipmentTypeList.vue", "Collection", 91, "page",
        "equipment.type.view",
    ),
    MenuDef(
        "equipment.equipment", "设备信息管理", "equipment", "/equipment/equipments",
        "views/equipment/EquipmentList.vue", "Tools", 92, "page",
        "equipment.equipment.view",
    ),
    MenuDef(
        "equipment.ledger", "设备台账", "equipment", "/equipment/ledger",
        "views/equipment/EquipmentLedgerList.vue", "Memo", 93, "page",
        "equipment.equipment.view",
    ),
    MenuDef(
        "equipment.equipment-part", "设备零部件", "equipment", "/equipment/parts",
        "views/equipment/EquipmentPartList.vue", "Grid", 94, "page",
        "equipment.part.view",
    ),
    MenuDef(
        "equipment.spare-part", "备品备件", "equipment", "/equipment/spare-parts",
        "views/equipment/SparePartList.vue", "Box", 95, "page",
        "equipment.spare_part.view",
    ),
    MenuDef(
        "equipment.accessory", "配件管理", "equipment", "/equipment/accessories",
        "views/equipment/SparePartList.vue", "Box", 96, "page",
        "equipment.spare_part.view",
    ),
    MenuDef(
        "equipment.fault-report", "故障保修", "equipment", "/equipment/fault-reports",
        "views/equipment/FaultReportList.vue", "Warning", 97, "page",
        "equipment.fault_report.view",
    ),
    MenuDef(
        "equipment.spare-part-stock", "库存台账", "equipment", "/equipment/spare-part-stock",
        "views/equipment/SparePartStockList.vue", "Coin", 98, "page",
        "equipment.spare_part_stock.view",
    ),
    MenuDef(
        "equipment.requisition", "备件采购申请", "equipment", "/equipment/requisitions",
        "views/procurement/RequisitionList.vue", "ShoppingCart", 99, "page",
        "procurement.requisition.view",
    ),
    MenuDef(
        "equipment.maintenance-item", "保养项目", "equipment", "/equipment/maintenance-items",
        "views/equipment/MaintenanceItemList.vue", "SetUp", 101, "page",
        "equipment.maintenance_item.view",
    ),
    MenuDef(
        "equipment.maintenance-plan", "保养计划", "equipment", "/equipment/maintenance-plans",
        "views/equipment/MaintenancePlanList.vue", "Calendar", 102, "page",
        "equipment.maintenance_plan.view",
    ),
    MenuDef(
        "equipment.maintenance-task", "保养任务", "equipment", "/equipment/maintenance-tasks",
        "views/equipment/MaintenanceTaskList.vue", "Tickets", 103, "page",
        "equipment.maintenance_task.view",
    ),
    MenuDef(
        "equipment.maintenance-calendar", "保养日历", "equipment",
        "/equipment/maintenance-calendar",
        "views/equipment/MaintenanceCalendar.vue", "Clock", 104, "page",
        "equipment.maintenance_task.view",
    ),
    MenuDef(
        "equipment.maintenance-record", "保养记录", "equipment",
        "/equipment/maintenance-records",
        "views/equipment/MaintenanceRecordList.vue", "Document", 105, "page",
        "equipment.maintenance_record.view",
    ),
    MenuDef(
        "equipment.repair-task", "维修任务", "equipment", "/equipment/repair-tasks",
        "views/equipment/RepairTaskList.vue", "Tools", 111, "page",
        "equipment.repair_task.view",
    ),
    MenuDef(
        "equipment.repair-record", "维修记录", "equipment", "/equipment/repair-records",
        "views/equipment/RepairRecordList.vue", "Document", 112, "page",
        "equipment.repair_record.view",
    ),
    MenuDef(
        "equipment.inspection-item", "点巡检项目", "equipment", "/equipment/inspection-items",
        "views/equipment/InspectionItemList.vue", "List", 121, "page",
        "equipment.inspection_item.view",
    ),
    MenuDef(
        "equipment.inspection-task", "点巡检任务", "equipment", "/equipment/inspection-tasks",
        "views/equipment/InspectionTaskList.vue", "Tickets", 122, "page",
        "equipment.inspection_task.view",
    ),
    MenuDef(
        "equipment.inspection-record", "点巡检记录", "equipment",
        "/equipment/inspection-records",
        "views/equipment/InspectionRecordList.vue", "Document", 123, "page",
        "equipment.inspection_record.view",
    ),
    MenuDef(
        "equipment.abnormal-type", "异常类型", "equipment", "/equipment/abnormal-types",
        "views/equipment/AbnormalTypeList.vue", "Warning", 131, "page",
        "equipment.abnormal_type.view",
    ),
    MenuDef(
        "equipment.abnormal-task", "异常任务", "equipment", "/equipment/abnormal-tasks",
        "views/equipment/AbnormalTaskList.vue", "Bell", 132, "page",
        "equipment.abnormal_task.view",
    ),
    MenuDef(
        "equipment.abnormal-record", "异常记录", "equipment", "/equipment/abnormal-records",
        "views/equipment/AbnormalRecordList.vue", "Document", 133, "page",
        "equipment.abnormal_record.view",
    ),
    # 能源管理：首页/监控/报表是只读聚合页，基础管理维护表计、区域、价格与阈值
    MenuDef("ems", "能源管理", None, "/ems", "Layout", "Lightning", 95, "directory"),
    MenuDef(
        "ems.home", "能源首页", "ems", "/ems/home",
        "views/ems/EnergyHome.vue", "Odometer", 951, "page", "ems.home.view",
    ),
    MenuDef(
        "ems.monitor", "设备监控", "ems", "/ems/monitor",
        "views/ems/EnergyMonitor.vue", "Monitor", 952, "page", "ems.monitor.view",
    ),
    MenuDef(
        "ems.run-record", "设备运行记录", "ems", "/ems/run-records",
        "views/ems/EnergyRunRecordList.vue", "Tickets", 953, "page", "ems.run_record.view",
    ),
    MenuDef(
        "ems.alarm", "报警管理", "ems", "/ems/alarms",
        "views/ems/EnergyAlarmList.vue", "Bell", 954, "page", "ems.alarm.view",
    ),
    MenuDef(
        "ems.kanban", "能源看板", "ems", "/ems/kanban",
        "views/ems/EnergyKanban.vue", "DataLine", 955, "page", "ems.statistics.view",
    ),
    MenuDef(
        "ems.report", "能耗报表", "ems", "/ems/report",
        "views/ems/EnergyReport.vue", "Document", 956, "page", "ems.report.view",
    ),
    MenuDef(
        "ems.statistics", "能耗统计", "ems", "/ems/statistics",
        "views/ems/EnergyStatistics.vue", "Histogram", 957, "page", "ems.statistics.view",
    ),
    # 四种介质的统计页共用同一套聚合接口，只固定 medium 参数
    MenuDef(
        "ems.statistics-water", "用水统计", "ems", "/ems/statistics/water",
        "views/ems/WaterStatistics.vue", "Odometer", 958, "page", "ems.statistics.view",
    ),
    MenuDef(
        "ems.statistics-electricity", "用电统计", "ems", "/ems/statistics/electricity",
        "views/ems/ElectricityStatistics.vue", "Lightning", 959, "page", "ems.statistics.view",
    ),
    MenuDef(
        "ems.statistics-gas", "用气统计", "ems", "/ems/statistics/gas",
        "views/ems/GasStatistics.vue", "Odometer", 960, "page", "ems.statistics.view",
    ),
    MenuDef(
        "ems.statistics-liquid", "用液统计", "ems", "/ems/statistics/liquid",
        "views/ems/LiquidStatistics.vue", "Odometer", 961, "page", "ems.statistics.view",
    ),
    MenuDef("ems.base", "基础管理", "ems", "/ems/base", "Layout", "Setting", 970, "directory"),
    MenuDef(
        "ems.price-water", "水价管理", "ems.base", "/ems/base/water-prices",
        "views/ems/WaterPriceList.vue", "Coin", 971, "page", "ems.price.view",
    ),
    MenuDef(
        "ems.price-electricity", "电价管理", "ems.base", "/ems/base/electricity-prices",
        "views/ems/ElectricityPriceList.vue", "Coin", 972, "page", "ems.price.view",
    ),
    MenuDef(
        "ems.price-gas", "气价管理", "ems.base", "/ems/base/gas-prices",
        "views/ems/GasPriceList.vue", "Coin", 973, "page", "ems.price.view",
    ),
    MenuDef(
        "ems.price-liquid", "液价管理", "ems.base", "/ems/base/liquid-prices",
        "views/ems/LiquidPriceList.vue", "Coin", 974, "page", "ems.price.view",
    ),
    MenuDef(
        "ems.threshold", "阈值管理", "ems.base", "/ems/base/thresholds",
        "views/ems/EnergyThresholdList.vue", "Warning", 975, "page", "ems.threshold.view",
    ),
    MenuDef(
        "ems.area", "区域管理", "ems.base", "/ems/base/areas",
        "views/ems/EnergyAreaList.vue", "Collection", 976, "page", "ems.area.view",
    ),
    MenuDef(
        "ems.meter", "设备管理", "ems.base", "/ems/base/meters",
        "views/ems/EnergyMeterList.vue", "Grid", 977, "page", "ems.meter.view",
    ),
    # 生产物流管理：自动化设备台账、任务状态机、操作日志
    MenuDef("logistics", "生产物流管理", None, "/logistics", "Layout", "Van", 96, "directory"),
    MenuDef(
        "logistics.device", "自动化设备", "logistics", "/logistics/devices",
        "views/logistics/AutomationDeviceList.vue", "Cpu", 961, "page", "logistics.device.view",
    ),
    MenuDef(
        "logistics.task", "任务管理", "logistics", "/logistics/tasks",
        "views/logistics/LogisticsTaskList.vue", "Tickets", 962, "page", "logistics.task.view",
    ),
    MenuDef(
        "logistics.log", "操作日志", "logistics", "/logistics/logs",
        "views/logistics/LogisticsOperationLogList.vue", "Document", 963, "page",
        "logistics.log.view",
    ),
    # 安全环保管理：四大块各自成组，外加统一操作日志
    MenuDef("ehs", "安全环保管理", None, "/ehs", "Layout", "FirstAidKit", 97, "directory"),
    MenuDef("ehs.safety", "安全管理", "ehs", "/ehs/safety", "Layout", "Warning", 971, "directory"),
    MenuDef(
        "ehs.regulation", "安全制度", "ehs.safety", "/ehs/safety/regulations",
        "views/ehs/SafetyRegulationList.vue", "Document", 9711, "page", "ehs.regulation.view",
    ),
    MenuDef(
        "ehs.training", "安全培训", "ehs.safety", "/ehs/safety/trainings",
        "views/ehs/SafetyTrainingList.vue", "Notebook", 9712, "page", "ehs.training.view",
    ),
    MenuDef(
        "ehs.hazard", "隐患排查", "ehs.safety", "/ehs/safety/hazards",
        "views/ehs/HazardList.vue", "WarningFilled", 9713, "page", "ehs.hazard.view",
    ),
    MenuDef(
        "ehs.emergency-plan", "应急预案", "ehs.safety", "/ehs/safety/emergency-plans",
        "views/ehs/EmergencyPlanList.vue", "Guide", 9714, "page", "ehs.emergency_plan.view",
    ),
    MenuDef(
        "ehs.accident", "事故处理", "ehs.safety", "/ehs/safety/accidents",
        "views/ehs/AccidentList.vue", "FirstAidKit", 9715, "page", "ehs.accident.view",
    ),
    MenuDef("ehs.environment", "环保管理", "ehs", "/ehs/environment", "Layout", "Sunny", 972,
            "directory"),
    MenuDef(
        "ehs.env-monitor", "排污监测", "ehs.environment", "/ehs/environment/monitors",
        "views/ehs/EnvironmentMonitorList.vue", "DataLine", 9721, "page",
        "ehs.env_monitor.view",
    ),
    MenuDef(
        "ehs.waste", "固废危废", "ehs.environment", "/ehs/environment/wastes",
        "views/ehs/WasteRecordList.vue", "Delete", 9722, "page", "ehs.waste.view",
    ),
    MenuDef(
        "ehs.compliance", "环保合规", "ehs.environment", "/ehs/environment/compliance-checks",
        "views/ehs/ComplianceCheckList.vue", "Checked", 9723, "page", "ehs.compliance.view",
    ),
    MenuDef("ehs.fire", "消防管理", "ehs", "/ehs/fire", "Layout", "Umbrella", 973, "directory"),
    MenuDef(
        "ehs.fire-facility", "消防设施", "ehs.fire", "/ehs/fire/facilities",
        "views/ehs/FireFacilityList.vue", "Box", 9731, "page", "ehs.fire_facility.view",
    ),
    MenuDef(
        "ehs.fire-drill", "消防演练", "ehs.fire", "/ehs/fire/drills",
        "views/ehs/FireDrillList.vue", "Flag", 9732, "page", "ehs.fire_drill.view",
    ),
    MenuDef(
        "ehs.hot-work", "动火作业", "ehs.fire", "/ehs/fire/hot-works",
        "views/ehs/HotWorkPermitList.vue", "MagicStick", 9733, "page", "ehs.permit.view",
    ),
    MenuDef("ehs.equipment-safety", "设备设施安全", "ehs", "/ehs/equipment-safety", "Layout",
            "Tools", 974, "directory"),
    MenuDef(
        "ehs.special-equipment", "特种设备检验", "ehs.equipment-safety",
        "/ehs/equipment-safety/special-equipment",
        "views/ehs/SpecialEquipmentList.vue", "Aim", 9741, "page", "ehs.special_equipment.view",
    ),
    MenuDef(
        "ehs.maintenance-permit", "检维修作业", "ehs.equipment-safety",
        "/ehs/equipment-safety/maintenance-permits",
        "views/ehs/MaintenancePermitList.vue", "SetUp", 9742, "page", "ehs.permit.view",
    ),
    MenuDef(
        "ehs.intrinsic-check", "本质安全检查", "ehs.equipment-safety",
        "/ehs/equipment-safety/intrinsic-checks",
        "views/ehs/IntrinsicSafetyCheckList.vue", "Checked", 9743, "page",
        "ehs.safety_check.view",
    ),
    MenuDef(
        "ehs.explosion-proof-check", "防爆防静电检查", "ehs.equipment-safety",
        "/ehs/equipment-safety/explosion-proof-checks",
        "views/ehs/ExplosionProofCheckList.vue", "Lightning", 9744, "page",
        "ehs.safety_check.view",
    ),
    MenuDef(
        "ehs.fire-proof-check", "防火防爆检查", "ehs.equipment-safety",
        "/ehs/equipment-safety/fire-proof-checks",
        "views/ehs/FireProofCheckList.vue", "Warning", 9745, "page", "ehs.safety_check.view",
    ),
    MenuDef(
        "ehs.log", "操作日志", "ehs", "/ehs/logs",
        "views/ehs/EhsOperationLogList.vue", "Document", 975, "page", "ehs.log.view",
    ),
    # 设备数采与监控：接入配置 + 采集数据（只读采集，不下发控制）
    MenuDef("iot", "设备数采与监控", None, "/iot", "Layout", "Monitor", 98, "directory"),
    MenuDef(
        "iot.connection", "数采连接配置", "iot", "/iot/connections",
        "views/iot/ConnectionList.vue", "Connection", 981, "page", "iot.connection.view",
    ),
    MenuDef(
        "iot.gateway", "数采设备", "iot", "/iot/gateways",
        "views/iot/GatewayList.vue", "Cpu", 982, "page", "iot.gateway.view",
    ),
    MenuDef(
        "iot.point", "采集测点", "iot", "/iot/points",
        "views/iot/PointList.vue", "Aim", 983, "page", "iot.point.view",
    ),
    MenuDef(
        "iot.monitor", "设备监控", "iot", "/iot/monitor",
        "views/iot/DeviceMonitor.vue", "DataLine", 984, "page", "iot.monitor.view",
    ),
    MenuDef(
        "iot.reading", "采集读数", "iot", "/iot/readings",
        "views/iot/ReadingList.vue", "Histogram", 985, "page", "iot.reading.view",
    ),
    MenuDef(
        "iot.message", "采集日志", "iot", "/iot/messages",
        "views/iot/MessageList.vue", "Document", 986, "page", "iot.message.view",
    ),
    MenuDef("workflow", "审批中心", None, "/workflow", "Layout", "Stamp", 100, "directory"),
    MenuDef(
        "workflow.todo", "我的待办", "workflow", "/workflow/todo",
        "views/workflow/TodoList.vue", "Bell", 101, "page", "workflow.instance.view",
    ),
    MenuDef(
        "workflow.my-requests", "我的申请", "workflow", "/workflow/my-requests",
        "views/workflow/MyRequestList.vue", "Document", 102, "page", "workflow.instance.view",
    ),
    MenuDef(
        "workflow.template", "审批模板", "workflow", "/workflow/templates",
        "views/workflow/TemplateList.vue", "SetUp", 103, "page", "workflow.template.view",
    ),
    MenuDef("integration", "内部协同", None, "/integration", "Layout", "Connection", 110, "directory"),
    MenuDef(
        "integration.outbox", "事件与协同", "integration", "/integration/outbox",
        "views/integration/OutboxList.vue", "Promotion", 111, "page", "integration.outbox.view",
    ),
    MenuDef("system", "系统管理", None, "/system", "Layout", "Setting", 190, "directory"),
    MenuDef(
        "system.user", "用户管理", "system", "/system/users",
        "views/system/UserList.vue", "User", 191, "page", "identity.user.view",
    ),
    MenuDef(
        "system.role", "角色权限", "system", "/system/roles",
        "views/system/RoleList.vue", "Lock", 192, "page", "identity.role.view",
    ),
    MenuDef(
        "system.permission", "权限与菜单", "system", "/system/permissions",
        "views/system/PermissionList.vue", "Key", 193, "page", "identity.permission.view",
    ),
    MenuDef(
        "system.dictionary", "数据字典", "system", "/system/dictionaries",
        "views/system/DictionaryList.vue", "Notebook", 194, "page", "core.dictionary.view",
    ),
    MenuDef(
        "system.code-rule", "编码规则", "system", "/system/code-rules",
        "views/system/CodeRuleList.vue", "Ticket", 195, "page", "core.code_rule.view",
    ),
    MenuDef(
        "system.audit", "审计与登录日志", "system", "/system/audit-logs",
        "views/system/AuditLogList.vue", "Document", 196, "page", "core.audit.view",
    ),
    MenuDef(
        "system.notification", "我的通知", "system", "/system/notifications",
        "views/system/NotificationList.vue", "ChatDotRound", 197, "page", "core.notification.view",
    ),
    MenuDef(
        "system.progress", "实施进度", "system", "/system/progress",
        "views/system/ProgressView.vue", "DataLine", 198, "page", "core.progress.view",
    ),
]

PERMISSION_CODES: set[str] = {item.code for item in PERMISSIONS}
MENU_CODES: set[str] = {item.code for item in MENUS}

# 权限模块的中文名。
#
# 权限编码的第一段是模块（如 ``core.user.view`` 的 ``core``），角色配置界面的
# 一级分组若只显示英文模块名，业务人员无法判断「core」到底管什么。
# 界面上统一显示为 ``模块编码（中文名）``，例如 ``core（公共基础）``。
#
# 名称尽量与左侧一级菜单保持一致，便于对照；``core`` 这类不直接对应菜单的
# 基础能力单独命名，不与「用户与权限」重复。
# 新增权限模块时**必须**在此登记，否则 ``yishang.E002`` 启动检查会报错。
MODULE_LABELS: dict[str, str] = {
    "analytics": "工作台与看板",
    "core": "公共基础",
    "crm": "客户管理",
    "ems": "能源管理",
    "ehs": "安全环保管理",
    "equipment": "设备管理",
    "factory": "工厂与排班",
    "identity": "用户与权限",
    "integration": "内部协同",
    "iot": "设备数采与监控",
    "logistics": "生产物流管理",
    "masterdata": "基础资料",
    "mes": "生产执行",
    "planning": "计划管理",
    "qms": "质量管理",
    "procurement": "采购管理",
    "sales": "销售管理",
    "srm": "供应商管理",
    "wms": "仓储管理",
    "workflow": "审批中心",
}


def module_label(module: str) -> str:
    """模块中文名；未登记时返回空串，界面只显示模块编码。"""
    return MODULE_LABELS.get(module, "")
