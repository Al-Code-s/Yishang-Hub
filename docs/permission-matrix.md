# 权限矩阵（docs/permission-matrix.md）

> 权限的唯一契约是 `backend/apps/identity/permissions_registry.py`。后端启动时由
> `apps/core/checks.py` 校验所有已声明的权限编码都存在于注册表；前端菜单树由
> `identity/menus/mine/` 下发。**不允许任何模块私自新增未注册的权限编码。**

## 一、四层权限（任务书 6.3）

| 层 | 名称 | 载体 | 执行位置 | 缺省行为 |
| --- | --- | --- | --- | --- |
| 1 | 菜单权限 | `identity_menu.permission_code` | 后端下发菜单树；前端据此注册路由 | 无权限 → 不下发该菜单，前端不注册路由 |
| 2 | 操作权限 | `Permission.code`（如 `sales.order.submit`） | `HasRequiredPermissions` + `require_codes()` 二次校验 | 未满足 → `403 PERMISSION_DENIED` |
| 3 | 接口权限 | 同操作权限，按 ViewSet 的 `required_permissions` 声明 | DRF 视图层 | 未声明权限的接口仅要求登录 |
| 4 | 数据范围 | `Role.data_scope_type` + `RoleScopeGrant` | `apps/core/selectors.py::resolve_data_scope`，用于所有查询 | 无角色/无授权 → **空集（fail-closed）** |

**关键约定**：前三层是「能不能做这个动作」，第四层是「能对哪些数据做这个动作」。
两者必须同时满足。前端传入的 `factory_id` / `warehouse_id` **只作为过滤条件，不作为授权依据**。

## 二、数据范围类型

| `data_scope_type` | 语义 | 实现 |
| --- | --- | --- |
| `all` | 全部数据 | 不加范围过滤（超级管理员亦走此档） |
| `company` | 本公司及以下 | 收敛到用户归属公司 |
| `factory` | 指定工厂 | 由 `RoleScopeGrant(dimension=factory)` 指定 |
| `department` | 指定部门 | 授权部门 + **部门子树**展开 |
| `warehouse` | 指定仓库 | 由 `RoleScopeGrant(dimension=warehouse)` 指定 |
| `self` | 仅本人 | 按 `created_by` / `applicant` 等归属字段过滤 |
| `custom` | 自定义组织范围 | 多维度 `RoleScopeGrant`，各维度内部取并集 |

## 三、权限编码清单（生成自注册表，实际共 368 条）

### analytics（工作台与看板，1 条）

| 权限编码 | 名称 |
| --- | --- |
| `analytics.dashboard.view` | 查看工作台 |

### core（公共基础，12 条）

| 权限编码 | 名称 |
| --- | --- |
| `core.attachment.delete` | 删除附件 |
| `core.attachment.download` | 下载附件 |
| `core.attachment.upload` | 上传附件 |
| `core.audit.view` | 查看审计日志 |
| `core.code_rule.create` | 新增编码规则 |
| `core.code_rule.update` | 修改编码规则 |
| `core.code_rule.view` | 查看编码规则 |
| `core.dictionary.create` | 新增数据字典 |
| `core.dictionary.update` | 修改数据字典 |
| `core.dictionary.view` | 查看数据字典 |
| `core.notification.view` | 查看通知 |
| `core.progress.view` | 查看实施进度 |

### crm（客户管理，17 条）

| 权限编码 | 名称 |
| --- | --- |
| `crm.complaint.close` | 关闭客户投诉 |
| `crm.complaint.create` | 登记客户投诉 |
| `crm.complaint.handle` | 受理与处理客户投诉 |
| `crm.complaint.update` | 修改客户投诉 |
| `crm.complaint.view` | 查看客户投诉 |
| `crm.customer.create` | 新增客户 |
| `crm.customer.deactivate` | 启用/停用客户 |
| `crm.customer.update` | 修改客户 |
| `crm.customer.view` | 查看客户 |
| `crm.customer_contact.create` | 新增客户联系人 |
| `crm.customer_contact.update` | 修改客户联系人 |
| `crm.customer_contact.view` | 查看客户联系人 |
| `crm.product_review.close` | 关闭产品评价 |
| `crm.product_review.create` | 登记产品评价 |
| `crm.product_review.reply` | 回复产品评价 |
| `crm.product_review.update` | 修改产品评价 |
| `crm.product_review.view` | 查看产品评价 |

### ehs（安全环保管理，46 条）

| 权限编码 | 名称 |
| --- | --- |
| `ehs.accident.create` | 上报事故 |
| `ehs.accident.handle` | 事故调查、整改与关闭 |
| `ehs.accident.update` | 修改事故记录 |
| `ehs.accident.view` | 查看事故记录 |
| `ehs.compliance.create` | 新增环保合规检查 |
| `ehs.compliance.update` | 修改/关闭环保合规检查 |
| `ehs.compliance.view` | 查看环保合规检查 |
| `ehs.emergency_plan.create` | 新增应急预案 |
| `ehs.emergency_plan.update` | 修改应急预案 |
| `ehs.emergency_plan.view` | 查看应急预案 |
| `ehs.env_monitor.create` | 新增排污监测 |
| `ehs.env_monitor.update` | 修改排污监测 |
| `ehs.env_monitor.view` | 查看排污监测 |
| `ehs.fire_drill.create` | 新增消防演练 |
| `ehs.fire_drill.update` | 修改消防演练 |
| `ehs.fire_drill.view` | 查看消防演练 |
| `ehs.fire_facility.create` | 新增消防设施 |
| `ehs.fire_facility.update` | 修改消防设施 |
| `ehs.fire_facility.view` | 查看消防设施 |
| `ehs.hazard.create` | 上报隐患 |
| `ehs.hazard.rectify` | 隐患整改与提交验收 |
| `ehs.hazard.update` | 修改隐患 |
| `ehs.hazard.verify` | 隐患验收 |
| `ehs.hazard.view` | 查看隐患排查 |
| `ehs.log.view` | 查看安全环保操作日志 |
| `ehs.permit.accept` | 作业许可现场验收 |
| `ehs.permit.approve` | 审批作业许可 |
| `ehs.permit.create` | 申请作业许可 |
| `ehs.permit.execute` | 作业开工与完工 |
| `ehs.permit.update` | 修改作业许可 |
| `ehs.permit.view` | 查看作业许可 |
| `ehs.regulation.create` | 新增安全制度 |
| `ehs.regulation.update` | 修改安全制度 |
| `ehs.regulation.view` | 查看安全制度 |
| `ehs.safety_check.create` | 新增安全检查 |
| `ehs.safety_check.update` | 修改安全检查 |
| `ehs.safety_check.view` | 查看安全检查 |
| `ehs.special_equipment.create` | 新增特种设备检验 |
| `ehs.special_equipment.update` | 修改特种设备检验 |
| `ehs.special_equipment.view` | 查看特种设备检验 |
| `ehs.training.create` | 新增安全培训 |
| `ehs.training.update` | 修改安全培训 |
| `ehs.training.view` | 查看安全培训 |
| `ehs.waste.create` | 新增固废危废台账 |
| `ehs.waste.update` | 修改固废危废台账 |
| `ehs.waste.view` | 查看固废危废台账 |

### ems（能源管理，25 条）

| 权限编码 | 名称 |
| --- | --- |
| `ems.alarm.create` | 上报能源报警 |
| `ems.alarm.handle` | 处理与关闭能源报警 |
| `ems.alarm.update` | 修改能源报警 |
| `ems.alarm.view` | 查看能源报警 |
| `ems.area.create` | 新增计量区域 |
| `ems.area.update` | 修改计量区域 |
| `ems.area.view` | 查看计量区域 |
| `ems.home.view` | 查看能源首页 |
| `ems.meter.create` | 新增计量设备 |
| `ems.meter.update` | 修改计量设备 |
| `ems.meter.view` | 查看计量设备 |
| `ems.monitor.view` | 查看设备监控 |
| `ems.price.create` | 新增能源价格 |
| `ems.price.update` | 修改能源价格 |
| `ems.price.view` | 查看能源价格 |
| `ems.reading.create` | 抄表录入 |
| `ems.reading.view` | 查看抄表记录 |
| `ems.report.view` | 查看与导出能耗报表 |
| `ems.run_record.create` | 开始设备运行记录 |
| `ems.run_record.execute` | 结束/取消设备运行记录 |
| `ems.run_record.view` | 查看设备运行记录 |
| `ems.statistics.view` | 查看能耗统计与看板 |
| `ems.threshold.create` | 新增能源阈值 |
| `ems.threshold.update` | 修改能源阈值 |
| `ems.threshold.view` | 查看能源阈值 |

### equipment（设备管理，58 条）

| 权限编码 | 名称 |
| --- | --- |
| `equipment.abnormal_record.create` | 新增异常记录 |
| `equipment.abnormal_record.update` | 修改异常记录 |
| `equipment.abnormal_record.view` | 查看异常记录 |
| `equipment.abnormal_task.create` | 新增异常任务 |
| `equipment.abnormal_task.handle` | 处理异常任务 |
| `equipment.abnormal_task.update` | 修改异常任务 |
| `equipment.abnormal_task.view` | 查看异常任务 |
| `equipment.abnormal_type.create` | 新增异常类型 |
| `equipment.abnormal_type.update` | 修改异常类型 |
| `equipment.abnormal_type.view` | 查看异常类型 |
| `equipment.equipment.create` | 新增设备台账 |
| `equipment.equipment.deactivate` | 启用/停用设备 |
| `equipment.equipment.update` | 修改设备台账 |
| `equipment.equipment.view` | 查看设备台账 |
| `equipment.fault_report.create` | 新增故障保修 |
| `equipment.fault_report.update` | 修改故障保修 |
| `equipment.fault_report.view` | 查看故障保修 |
| `equipment.inspection_item.create` | 新增点巡检项目 |
| `equipment.inspection_item.update` | 修改点巡检项目 |
| `equipment.inspection_item.view` | 查看点巡检项目 |
| `equipment.inspection_record.create` | 新增点巡检记录 |
| `equipment.inspection_record.update` | 修改点巡检记录 |
| `equipment.inspection_record.view` | 查看点巡检记录 |
| `equipment.inspection_task.create` | 新增点巡检任务 |
| `equipment.inspection_task.execute` | 执行点巡检任务 |
| `equipment.inspection_task.update` | 修改点巡检任务 |
| `equipment.inspection_task.view` | 查看点巡检任务 |
| `equipment.maintenance_item.create` | 新增保养项目 |
| `equipment.maintenance_item.update` | 修改保养项目 |
| `equipment.maintenance_item.view` | 查看保养项目 |
| `equipment.maintenance_plan.create` | 新增保养计划 |
| `equipment.maintenance_plan.update` | 修改保养计划 |
| `equipment.maintenance_plan.view` | 查看保养计划 |
| `equipment.maintenance_record.create` | 新增保养记录 |
| `equipment.maintenance_record.update` | 修改保养记录 |
| `equipment.maintenance_record.view` | 查看保养记录 |
| `equipment.maintenance_task.create` | 新增保养任务 |
| `equipment.maintenance_task.execute` | 执行保养任务 |
| `equipment.maintenance_task.update` | 修改保养任务 |
| `equipment.maintenance_task.view` | 查看保养任务 |
| `equipment.part.create` | 新增设备零部件 |
| `equipment.part.update` | 修改设备零部件 |
| `equipment.part.view` | 查看设备零部件 |
| `equipment.repair_record.create` | 新增维修记录 |
| `equipment.repair_record.update` | 修改维修记录 |
| `equipment.repair_record.view` | 查看维修记录 |
| `equipment.repair_task.create` | 新增维修任务 |
| `equipment.repair_task.execute` | 执行维修任务 |
| `equipment.repair_task.update` | 修改维修任务 |
| `equipment.repair_task.view` | 查看维修任务 |
| `equipment.spare_part.create` | 新增备品备件 |
| `equipment.spare_part.deactivate` | 启用/停用备品备件 |
| `equipment.spare_part.update` | 修改备品备件 |
| `equipment.spare_part.view` | 查看备品备件 |
| `equipment.spare_part_stock.view` | 查看备件库存台账 |
| `equipment.type.create` | 新增设备类型 |
| `equipment.type.update` | 修改设备类型 |
| `equipment.type.view` | 查看设备类型 |

### factory（工厂与排班，27 条）

| 权限编码 | 名称 |
| --- | --- |
| `factory.company.create` | 新增公司 |
| `factory.company.update` | 修改公司 |
| `factory.company.view` | 查看公司 |
| `factory.department.create` | 新增部门 |
| `factory.department.update` | 修改部门 |
| `factory.department.view` | 查看部门 |
| `factory.employee.create` | 新增员工 |
| `factory.employee.update` | 修改员工 |
| `factory.employee.view` | 查看员工 |
| `factory.factory.create` | 新增工厂 |
| `factory.factory.update` | 修改工厂 |
| `factory.factory.view` | 查看工厂 |
| `factory.line.create` | 新增线体 |
| `factory.line.update` | 修改线体 |
| `factory.line.view` | 查看线体 |
| `factory.shift.create` | 新增班次 |
| `factory.shift.update` | 修改班次 |
| `factory.shift.view` | 查看班次 |
| `factory.station.create` | 新增工位 |
| `factory.station.update` | 修改工位 |
| `factory.station.view` | 查看工位 |
| `factory.team.create` | 新增班组 |
| `factory.team.update` | 修改班组 |
| `factory.team.view` | 查看班组 |
| `factory.workshop.create` | 新增车间 |
| `factory.workshop.update` | 修改车间 |
| `factory.workshop.view` | 查看车间 |

### identity（用户与权限，15 条）

| 权限编码 | 名称 |
| --- | --- |
| `identity.log.view` | 查看登录记录 |
| `identity.menu.view` | 查看菜单 |
| `identity.permission.view` | 查看权限点 |
| `identity.role.assign_permission` | 配置角色权限与数据范围 |
| `identity.role.create` | 新增角色 |
| `identity.role.delete` | 删除角色 |
| `identity.role.update` | 修改角色 |
| `identity.role.view` | 查看角色 |
| `identity.user.assign_role` | 分配用户角色 |
| `identity.user.create` | 新增用户 |
| `identity.user.deactivate` | 启用/停用用户 |
| `identity.user.reset_password` | 重置用户密码 |
| `identity.user.unlock` | 解除用户锁定 |
| `identity.user.update` | 修改用户 |
| `identity.user.view` | 查看用户 |

### integration（内部协同，3 条）

| 权限编码 | 名称 |
| --- | --- |
| `integration.document_link.view` | 查看单据关系 |
| `integration.outbox.retry` | 重试发件箱事件 |
| `integration.outbox.view` | 查看发件箱事件 |

### iot（设备数采与监控，13 条）

| 权限编码 | 名称 |
| --- | --- |
| `iot.connection.create` | 新增数采连接 |
| `iot.connection.update` | 修改数采连接 |
| `iot.connection.view` | 查看数采连接 |
| `iot.gateway.create` | 新增数采设备 |
| `iot.gateway.rotate_token` | 生成/轮换设备令牌 |
| `iot.gateway.update` | 修改数采设备 |
| `iot.gateway.view` | 查看数采设备 |
| `iot.message.view` | 查看采集日志 |
| `iot.monitor.view` | 查看设备监控 |
| `iot.point.create` | 新增采集测点 |
| `iot.point.update` | 修改采集测点 |
| `iot.point.view` | 查看采集测点 |
| `iot.reading.view` | 查看采集读数 |

### logistics（生产物流管理，8 条）

| 权限编码 | 名称 |
| --- | --- |
| `logistics.device.create` | 新增自动化设备 |
| `logistics.device.update` | 修改自动化设备与状态 |
| `logistics.device.view` | 查看自动化设备 |
| `logistics.log.view` | 查看物流操作日志 |
| `logistics.task.create` | 新增物流任务 |
| `logistics.task.execute` | 执行物流任务 |
| `logistics.task.update` | 修改/下发/取消物流任务 |
| `logistics.task.view` | 查看物流任务 |

### masterdata（基础资料，27 条）

| 权限编码 | 名称 |
| --- | --- |
| `masterdata.color.create` | 新增颜色 |
| `masterdata.color.update` | 修改颜色 |
| `masterdata.color.view` | 查看颜色 |
| `masterdata.identifier.create` | 新增标识 |
| `masterdata.identifier.deactivate` | 停用标识 |
| `masterdata.identifier.update` | 修改标识 |
| `masterdata.identifier.view` | 查看标识 |
| `masterdata.material.create` | 新增物料 |
| `masterdata.material.deactivate` | 启用/停用物料 |
| `masterdata.material.update` | 修改物料 |
| `masterdata.material.view` | 查看物料 |
| `masterdata.material_category.create` | 新增物料分类 |
| `masterdata.material_category.update` | 修改物料分类 |
| `masterdata.material_category.view` | 查看物料分类 |
| `masterdata.size.create` | 新增尺码 |
| `masterdata.size.update` | 修改尺码 |
| `masterdata.size.view` | 查看尺码 |
| `masterdata.sku.create` | 新增 SKU |
| `masterdata.sku.generate` | 批量生成 SKU |
| `masterdata.sku.update` | 修改 SKU |
| `masterdata.sku.view` | 查看 SKU |
| `masterdata.style.create` | 新增款式 |
| `masterdata.style.update` | 修改款式 |
| `masterdata.style.view` | 查看款式 |
| `masterdata.uom.create` | 新增计量单位 |
| `masterdata.uom.update` | 修改计量单位 |
| `masterdata.uom.view` | 查看计量单位 |

### mes（生产执行，10 条）

| 权限编码 | 名称 |
| --- | --- |
| `mes.order.cancel` | 取消生产工单 |
| `mes.order.close` | 关闭生产工单 |
| `mes.order.complete` | 生产完工与完工入库 |
| `mes.order.create` | 新增生产工单 |
| `mes.order.issue` | 生产领料 |
| `mes.order.release` | 下达生产工单 |
| `mes.order.update` | 修改生产工单 |
| `mes.order.view` | 查看生产工单 |
| `mes.report.create` | 新增生产报工 |
| `mes.report.view` | 查看生产报工 |

### planning（计划管理，15 条）

| 权限编码 | 名称 |
| --- | --- |
| `planning.bom.create` | 新增 BOM |
| `planning.bom.obsolete` | 作废 BOM 版本 |
| `planning.bom.submit` | 提交 BOM 审批 |
| `planning.bom.update` | 修改 BOM 草稿 |
| `planning.bom.view` | 查看 BOM |
| `planning.mrp.archive` | 归档 MRP 运行 |
| `planning.mrp.cancel` | 取消 MRP 建议 |
| `planning.mrp.convert` | MRP 建议转单 |
| `planning.mrp.run` | 运行 MRP 计算 |
| `planning.mrp.view` | 查看 MRP 运行与建议 |
| `planning.routing.create` | 新增工艺路线 |
| `planning.routing.obsolete` | 作废工艺路线版本 |
| `planning.routing.submit` | 提交工艺路线审批 |
| `planning.routing.update` | 修改工艺路线草稿 |
| `planning.routing.view` | 查看工艺路线 |

### procurement（采购管理，15 条）

| 权限编码 | 名称 |
| --- | --- |
| `procurement.order.close` | 关闭采购订单 |
| `procurement.order.create` | 新增采购订单 |
| `procurement.order.override_supplier` | 采购订单供应商例外授权 |
| `procurement.order.submit` | 提交采购订单审批 |
| `procurement.order.update` | 修改/取消采购订单 |
| `procurement.order.view` | 查看采购订单 |
| `procurement.receipt.create` | 新增采购收货单 |
| `procurement.receipt.inspect` | 来料检验判定（质量放行） |
| `procurement.receipt.post` | 采购收货过账（记待检库存） |
| `procurement.receipt.update` | 修改/取消采购收货单 |
| `procurement.receipt.view` | 查看采购收货单 |
| `procurement.requisition.create` | 新增采购申请 |
| `procurement.requisition.submit` | 提交采购申请审批 |
| `procurement.requisition.update` | 修改/取消采购申请 |
| `procurement.requisition.view` | 查看采购申请 |

### qms（质量管理，17 条）

| 权限编码 | 名称 |
| --- | --- |
| `qms.alert.close` | 关闭质量报警 |
| `qms.alert.handle` | 处理质量报警 |
| `qms.alert.view` | 查看质量报警 |
| `qms.inspection.close` | 关闭检验单 |
| `qms.inspection.create` | 新增检验单 |
| `qms.inspection.judge` | 判定检验单 |
| `qms.inspection.submit` | 提交检验单 |
| `qms.inspection.update` | 修改检验单与录入检验结果 |
| `qms.inspection.view` | 查看检验单与质量监测 |
| `qms.inspection_item.create` | 新增检验项目 |
| `qms.inspection_item.update` | 修改检验项目 |
| `qms.inspection_item.view` | 查看检验项目 |
| `qms.issue.archive` | 归档质量问题条目 |
| `qms.issue.create` | 新增质量问题条目 |
| `qms.issue.publish` | 发布质量问题条目 |
| `qms.issue.update` | 修改质量问题条目 |
| `qms.issue.view` | 查看质量问题知识库 |

### sales（销售管理，16 条）

| 权限编码 | 名称 |
| --- | --- |
| `sales.order.close` | 关闭销售订单 |
| `sales.order.create` | 新增销售订单 |
| `sales.order.release` | 释放销售订单库存占用 |
| `sales.order.reserve` | 销售订单库存占用 |
| `sales.order.submit` | 提交销售订单审批 |
| `sales.order.update` | 修改/取消销售订单 |
| `sales.order.view` | 查看销售订单 |
| `sales.return.create` | 新增销售退货单 |
| `sales.return.inspect` | 销售退货检验判定 |
| `sales.return.post` | 销售退货收货过账 |
| `sales.return.update` | 修改/取消销售退货单 |
| `sales.return.view` | 查看销售退货单 |
| `sales.shipment.create` | 新增销售发货单 |
| `sales.shipment.post` | 销售发货出库过账 |
| `sales.shipment.update` | 修改/取消销售发货单 |
| `sales.shipment.view` | 查看销售发货单 |

### srm（供应商管理，18 条）

| 权限编码 | 名称 |
| --- | --- |
| `srm.evaluation.archive` | 归档供应商评价 |
| `srm.evaluation.create` | 发起供应商评价 |
| `srm.evaluation.publish` | 供应商评价生效 |
| `srm.evaluation.update` | 录入或修改评价明细 |
| `srm.evaluation.view` | 查看供应商评价 |
| `srm.evaluation_weight.create` | 新增供应商评价权重 |
| `srm.evaluation_weight.update` | 修改评价权重（派生新版本） |
| `srm.evaluation_weight.view` | 查看供应商评价权重 |
| `srm.supplier.create` | 新增供应商 |
| `srm.supplier.deactivate` | 启用/停用供应商 |
| `srm.supplier.update` | 修改供应商 |
| `srm.supplier.view` | 查看供应商 |
| `srm.supplier_contact.create` | 新增供应商联系人 |
| `srm.supplier_contact.update` | 修改供应商联系人 |
| `srm.supplier_contact.view` | 查看供应商联系人 |
| `srm.supplier_qualification.create` | 新增供应商资质 |
| `srm.supplier_qualification.update` | 修改供应商资质 |
| `srm.supplier_qualification.view` | 查看供应商资质 |

### wms（仓储管理，18 条）

| 权限编码 | 名称 |
| --- | --- |
| `wms.document.create` | 创建库存单据 |
| `wms.document.post` | 库存单据过账 |
| `wms.document.reverse` | 库存单据冲销 |
| `wms.document.update` | 修改库存单据草稿 |
| `wms.document.view` | 查看库存单据 |
| `wms.inventory.release` | 释放库存占用 |
| `wms.inventory.reserve` | 库存占用 |
| `wms.inventory.view` | 查看库存余额与流水 |
| `wms.location.create` | 新增储位 |
| `wms.location.update` | 修改储位 |
| `wms.location.view` | 查看储位 |
| `wms.quality.release` | 库存质量放行 |
| `wms.warehouse.create` | 新增仓库 |
| `wms.warehouse.update` | 修改仓库 |
| `wms.warehouse.view` | 查看仓库 |
| `wms.zone.create` | 新增库区 |
| `wms.zone.update` | 修改库区 |
| `wms.zone.view` | 查看库区 |

### workflow（审批中心，7 条）

| 权限编码 | 名称 |
| --- | --- |
| `workflow.instance.approve` | 审批通过/驳回 |
| `workflow.instance.submit` | 提交审批 |
| `workflow.instance.view` | 查看审批单 |
| `workflow.instance.withdraw` | 撤回审批 |
| `workflow.template.create` | 新增审批模板 |
| `workflow.template.update` | 修改审批模板 |
| `workflow.template.view` | 查看审批模板 |

## 四、菜单树与页面映射（生成自注册表，实际共 144 项）

| 菜单编码 | 名称 | 路由 | 组件 | 所需权限 | 类型 |
| --- | --- | --- | --- | --- | --- |
| `workspace` | 工作台 | /workspace | views/workspace/Index.vue | `analytics.dashboard.view` | page |
| `masterdata` | 基础资料 | /masterdata | Layout | - | directory |
| 　└ `masterdata.material` | 物料档案 | /masterdata/materials | views/masterdata/MaterialList.vue | `masterdata.material.view` | page |
| 　└ `masterdata.material-category` | 物料分类 | /masterdata/material-categories | views/masterdata/MaterialCategoryList.vue | `masterdata.material_category.view` | page |
| 　└ `masterdata.style` | 款式档案 | /masterdata/styles | views/masterdata/StyleList.vue | `masterdata.style.view` | page |
| 　└ `masterdata.sku` | SKU 档案 | /masterdata/skus | views/masterdata/SkuList.vue | `masterdata.sku.view` | page |
| 　└ `masterdata.color-size` | 颜色与尺码 | /masterdata/color-size | views/masterdata/ColorSizeList.vue | `masterdata.color.view` | page |
| 　└ `masterdata.uom` | 计量单位 | /masterdata/uoms | views/masterdata/UomList.vue | `masterdata.uom.view` | page |
| `factory` | 工厂与排班 | /factory | Layout | - | directory |
| 　└ `factory.company` | 公司 | /factory/companies | views/factory/CompanyList.vue | `factory.company.view` | page |
| 　└ `factory.department` | 部门 | /factory/departments | views/factory/DepartmentList.vue | `factory.department.view` | page |
| 　└ `factory.factory` | 工厂 | /factory/factories | views/factory/FactoryList.vue | `factory.factory.view` | page |
| 　└ `factory.workshop` | 车间与线体 | /factory/workshops | views/factory/WorkshopList.vue | `factory.workshop.view` | page |
| 　└ `factory.employee` | 员工档案 | /factory/employees | views/factory/EmployeeList.vue | `factory.employee.view` | page |
| 　└ `factory.team` | 班组 | /factory/teams | views/factory/TeamList.vue | `factory.team.view` | page |
| 　└ `factory.shift` | 班次 | /factory/shifts | views/factory/ShiftList.vue | `factory.shift.view` | page |
| `crm` | 客户管理 | /crm | Layout | - | directory |
| 　└ `crm.customer` | 客户档案 | /crm/customers | views/crm/CustomerList.vue | `crm.customer.view` | page |
| 　└ `crm.customer-contact` | 客户联系人 | /crm/customer-contacts | views/crm/CustomerContactList.vue | `crm.customer_contact.view` | page |
| 　└ `crm.complaint` | 客户投诉 | /crm/complaints | views/crm/ComplaintList.vue | `crm.complaint.view` | page |
| 　└ `crm.product-review` | 产品评价 | /crm/product-reviews | views/crm/ProductReviewList.vue | `crm.product_review.view` | page |
| `sales` | 销售管理 | /sales | Layout | - | directory |
| 　└ `sales.order` | 销售订单 | /sales/orders | views/sales/SalesOrderList.vue | `sales.order.view` | page |
| 　└ `sales.shipment` | 销售发货 | /sales/shipments | views/sales/SalesShipmentList.vue | `sales.shipment.view` | page |
| 　└ `sales.return` | 销售退货 | /sales/returns | views/sales/SalesReturnList.vue | `sales.return.view` | page |
| `srm` | 供应商管理 | /srm | Layout | - | directory |
| 　└ `srm.supplier` | 供应商档案 | /srm/suppliers | views/srm/SupplierList.vue | `srm.supplier.view` | page |
| 　└ `srm.supplier-contact` | 供应商联系人 | /srm/supplier-contacts | views/srm/SupplierContactList.vue | `srm.supplier_contact.view` | page |
| 　└ `srm.supplier-qualification` | 供应商资质 | /srm/supplier-qualifications | views/srm/SupplierQualificationList.vue | `srm.supplier_qualification.view` | page |
| 　└ `srm.evaluation-weight` | 评价权重配置 | /srm/evaluation-weights | views/srm/SupplierEvaluationWeightList.vue | `srm.evaluation_weight.view` | page |
| 　└ `srm.supplier-evaluation` | 供应商评价 | /srm/supplier-evaluations | views/srm/SupplierEvaluationList.vue | `srm.evaluation.view` | page |
| `procurement` | 采购管理 | /procurement | Layout | - | directory |
| 　└ `procurement.requisition` | 采购申请 | /procurement/requisitions | views/procurement/RequisitionList.vue | `procurement.requisition.view` | page |
| 　└ `procurement.order` | 采购订单 | /procurement/orders | views/procurement/PurchaseOrderList.vue | `procurement.order.view` | page |
| 　└ `procurement.receipt` | 采购收货 | /procurement/receipts | views/procurement/GoodsReceiptList.vue | `procurement.receipt.view` | page |
| `planning` | 计划管理 | /planning | Layout | - | directory |
| 　└ `planning.bom` | 物料清单（BOM） | /planning/boms | views/planning/BomList.vue | `planning.bom.view` | page |
| 　└ `planning.routing` | 工艺路线 | /planning/routings | views/planning/RoutingList.vue | `planning.routing.view` | page |
| 　└ `planning.mrp` | MRP 运算 | /planning/mrp-runs | views/planning/MrpRunList.vue | `planning.mrp.view` | page |
| 　└ `planning.mrp_suggestion` | 缺料与建议 | /planning/mrp-suggestions | views/planning/MrpSuggestionList.vue | `planning.mrp.view` | page |
| `mes` | 生产执行 | /mes | Layout | - | directory |
| `wms` | 仓储管理 | /wms | Layout | - | directory |
| 　└ `wms.warehouse` | 仓库与储位 | /wms/warehouses | views/wms/WarehouseList.vue | `wms.warehouse.view` | page |
| 　└ `wms.inventory-balance` | 库存余额 | /wms/inventory-balances | views/wms/InventoryBalanceList.vue | `wms.inventory.view` | page |
| 　└ `wms.inventory-transaction` | 库存流水 | /wms/inventory-transactions | views/wms/InventoryTransactionList.vue | `wms.inventory.view` | page |
| 　└ `wms.inventory-document` | 库存单据 | /wms/inventory-documents | views/wms/InventoryDocumentList.vue | `wms.document.view` | page |
| `qms` | 质量管理 | /qms | Layout | - | directory |
| 　└ `qms.inspection-item` | 检验项目 | /qms/inspection-items | views/qms/InspectionItemList.vue | `qms.inspection_item.view` | page |
| 　└ `qms.inspection` | 检验单 | /qms/inspections | views/qms/InspectionOrderList.vue | `qms.inspection.view` | page |
| 　└ `qms.alert` | 质量报警 | /qms/alerts | views/qms/QualityAlertList.vue | `qms.alert.view` | page |
| 　└ `qms.issue` | 质量问题知识库 | /qms/issues | views/qms/QualityIssueList.vue | `qms.issue.view` | page |
| `equipment` | 设备管理 | /equipment | Layout | - | directory |
| 　└ `equipment.equipment-type` | 设备类型管理 | /equipment/types | views/equipment/EquipmentTypeList.vue | `equipment.type.view` | page |
| 　└ `equipment.equipment` | 设备信息管理 | /equipment/equipments | views/equipment/EquipmentList.vue | `equipment.equipment.view` | page |
| 　└ `equipment.ledger` | 设备台账 | /equipment/ledger | views/equipment/EquipmentLedgerList.vue | `equipment.equipment.view` | page |
| 　└ `equipment.equipment-part` | 设备零部件 | /equipment/parts | views/equipment/EquipmentPartList.vue | `equipment.part.view` | page |
| 　└ `equipment.spare-part` | 备品备件 | /equipment/spare-parts | views/equipment/SparePartList.vue | `equipment.spare_part.view` | page |
| `ems` | 能源管理 | /ems | Layout | - | directory |
| 　└ `equipment.accessory` | 配件管理 | /equipment/accessories | views/equipment/SparePartList.vue | `equipment.spare_part.view` | page |
| `logistics` | 生产物流管理 | /logistics | Layout | - | directory |
| 　└ `equipment.fault-report` | 故障保修 | /equipment/fault-reports | views/equipment/FaultReportList.vue | `equipment.fault_report.view` | page |
| `ehs` | 安全环保管理 | /ehs | Layout | - | directory |
| 　└ `equipment.spare-part-stock` | 库存台账 | /equipment/spare-part-stock | views/equipment/SparePartStockList.vue | `equipment.spare_part_stock.view` | page |
| `iot` | 设备数采与监控 | /iot | Layout | - | directory |
| 　└ `equipment.requisition` | 备件采购申请 | /equipment/requisitions | views/procurement/RequisitionList.vue | `procurement.requisition.view` | page |
| `workflow` | 审批中心 | /workflow | Layout | - | directory |
| 　└ `equipment.maintenance-item` | 保养项目 | /equipment/maintenance-items | views/equipment/MaintenanceItemList.vue | `equipment.maintenance_item.view` | page |
| 　└ `workflow.todo` | 我的待办 | /workflow/todo | views/workflow/TodoList.vue | `workflow.instance.view` | page |
| 　└ `equipment.maintenance-plan` | 保养计划 | /equipment/maintenance-plans | views/equipment/MaintenancePlanList.vue | `equipment.maintenance_plan.view` | page |
| 　└ `workflow.my-requests` | 我的申请 | /workflow/my-requests | views/workflow/MyRequestList.vue | `workflow.instance.view` | page |
| 　└ `equipment.maintenance-task` | 保养任务 | /equipment/maintenance-tasks | views/equipment/MaintenanceTaskList.vue | `equipment.maintenance_task.view` | page |
| 　└ `workflow.template` | 审批模板 | /workflow/templates | views/workflow/TemplateList.vue | `workflow.template.view` | page |
| 　└ `equipment.maintenance-calendar` | 保养日历 | /equipment/maintenance-calendar | views/equipment/MaintenanceCalendar.vue | `equipment.maintenance_task.view` | page |
| 　└ `equipment.maintenance-record` | 保养记录 | /equipment/maintenance-records | views/equipment/MaintenanceRecordList.vue | `equipment.maintenance_record.view` | page |
| `integration` | 内部协同 | /integration | Layout | - | directory |
| 　└ `equipment.repair-task` | 维修任务 | /equipment/repair-tasks | views/equipment/RepairTaskList.vue | `equipment.repair_task.view` | page |
| 　└ `integration.outbox` | 事件与协同 | /integration/outbox | views/integration/OutboxList.vue | `integration.outbox.view` | page |
| 　└ `equipment.repair-record` | 维修记录 | /equipment/repair-records | views/equipment/RepairRecordList.vue | `equipment.repair_record.view` | page |
| 　└ `equipment.inspection-item` | 点巡检项目 | /equipment/inspection-items | views/equipment/InspectionItemList.vue | `equipment.inspection_item.view` | page |
| 　└ `equipment.inspection-task` | 点巡检任务 | /equipment/inspection-tasks | views/equipment/InspectionTaskList.vue | `equipment.inspection_task.view` | page |
| 　└ `equipment.inspection-record` | 点巡检记录 | /equipment/inspection-records | views/equipment/InspectionRecordList.vue | `equipment.inspection_record.view` | page |
| 　└ `equipment.abnormal-type` | 异常类型 | /equipment/abnormal-types | views/equipment/AbnormalTypeList.vue | `equipment.abnormal_type.view` | page |
| 　└ `equipment.abnormal-task` | 异常任务 | /equipment/abnormal-tasks | views/equipment/AbnormalTaskList.vue | `equipment.abnormal_task.view` | page |
| 　└ `equipment.abnormal-record` | 异常记录 | /equipment/abnormal-records | views/equipment/AbnormalRecordList.vue | `equipment.abnormal_record.view` | page |
| `system` | 系统管理 | /system | Layout | - | directory |
| 　└ `system.user` | 用户管理 | /system/users | views/system/UserList.vue | `identity.user.view` | page |
| 　└ `system.role` | 角色权限 | /system/roles | views/system/RoleList.vue | `identity.role.view` | page |
| 　└ `system.permission` | 权限与菜单 | /system/permissions | views/system/PermissionList.vue | `identity.permission.view` | page |
| 　└ `system.dictionary` | 数据字典 | /system/dictionaries | views/system/DictionaryList.vue | `core.dictionary.view` | page |
| 　└ `system.code-rule` | 编码规则 | /system/code-rules | views/system/CodeRuleList.vue | `core.code_rule.view` | page |
| 　└ `system.audit` | 审计与登录日志 | /system/audit-logs | views/system/AuditLogList.vue | `core.audit.view` | page |
| 　└ `system.notification` | 我的通知 | /system/notifications | views/system/NotificationList.vue | `core.notification.view` | page |
| 　└ `system.progress` | 实施进度 | /system/progress | views/system/ProgressView.vue | `core.progress.view` | page |
| 　└ `mes.production-order` | 生产工单 | /mes/production-orders | views/mes/ProductionOrderList.vue | `mes.order.view` | page |
| 　└ `mes.production-report` | 生产报工 | /mes/production-reports | views/mes/ProductionReportList.vue | `mes.report.view` | page |
| 　└ `ems.home` | 能源首页 | /ems/home | views/ems/EnergyHome.vue | `ems.home.view` | page |
| 　└ `ems.monitor` | 设备监控 | /ems/monitor | views/ems/EnergyMonitor.vue | `ems.monitor.view` | page |
| 　└ `ems.run-record` | 设备运行记录 | /ems/run-records | views/ems/EnergyRunRecordList.vue | `ems.run_record.view` | page |
| 　└ `ems.alarm` | 报警管理 | /ems/alarms | views/ems/EnergyAlarmList.vue | `ems.alarm.view` | page |
| 　└ `ems.kanban` | 能源看板 | /ems/kanban | views/ems/EnergyKanban.vue | `ems.statistics.view` | page |
| 　└ `ems.report` | 能耗报表 | /ems/report | views/ems/EnergyReport.vue | `ems.report.view` | page |
| 　└ `ems.statistics` | 能耗统计 | /ems/statistics | views/ems/EnergyStatistics.vue | `ems.statistics.view` | page |
| 　└ `ems.statistics-water` | 用水统计 | /ems/statistics/water | views/ems/WaterStatistics.vue | `ems.statistics.view` | page |
| 　└ `ems.statistics-electricity` | 用电统计 | /ems/statistics/electricity | views/ems/ElectricityStatistics.vue | `ems.statistics.view` | page |
| 　└ `ems.statistics-gas` | 用气统计 | /ems/statistics/gas | views/ems/GasStatistics.vue | `ems.statistics.view` | page |
| 　└ `ems.statistics-liquid` | 用液统计 | /ems/statistics/liquid | views/ems/LiquidStatistics.vue | `ems.statistics.view` | page |
| 　└ `logistics.device` | 自动化设备 | /logistics/devices | views/logistics/AutomationDeviceList.vue | `logistics.device.view` | page |
| 　└ `logistics.task` | 任务管理 | /logistics/tasks | views/logistics/LogisticsTaskList.vue | `logistics.task.view` | page |
| 　└ `logistics.log` | 操作日志 | /logistics/logs | views/logistics/LogisticsOperationLogList.vue | `logistics.log.view` | page |
| 　└ `ems.base` | 基础管理 | /ems/base | Layout | - | directory |
| 　└ `ems.price-water` | 水价管理 | /ems/base/water-prices | views/ems/WaterPriceList.vue | `ems.price.view` | page |
| 　└ `ehs.safety` | 安全管理 | /ehs/safety | Layout | - | directory |
| 　└ `ems.price-electricity` | 电价管理 | /ems/base/electricity-prices | views/ems/ElectricityPriceList.vue | `ems.price.view` | page |
| 　└ `ehs.environment` | 环保管理 | /ehs/environment | Layout | - | directory |
| 　└ `ems.price-gas` | 气价管理 | /ems/base/gas-prices | views/ems/GasPriceList.vue | `ems.price.view` | page |
| 　└ `ehs.fire` | 消防管理 | /ehs/fire | Layout | - | directory |
| 　└ `ems.price-liquid` | 液价管理 | /ems/base/liquid-prices | views/ems/LiquidPriceList.vue | `ems.price.view` | page |
| 　└ `ehs.equipment-safety` | 设备设施安全 | /ehs/equipment-safety | Layout | - | directory |
| 　└ `ems.threshold` | 阈值管理 | /ems/base/thresholds | views/ems/EnergyThresholdList.vue | `ems.threshold.view` | page |
| 　└ `ehs.log` | 操作日志 | /ehs/logs | views/ehs/EhsOperationLogList.vue | `ehs.log.view` | page |
| 　└ `ems.area` | 区域管理 | /ems/base/areas | views/ems/EnergyAreaList.vue | `ems.area.view` | page |
| 　└ `ems.meter` | 设备管理 | /ems/base/meters | views/ems/EnergyMeterList.vue | `ems.meter.view` | page |
| 　└ `iot.connection` | 数采连接配置 | /iot/connections | views/iot/ConnectionList.vue | `iot.connection.view` | page |
| 　└ `iot.gateway` | 数采设备 | /iot/gateways | views/iot/GatewayList.vue | `iot.gateway.view` | page |
| 　└ `iot.point` | 采集测点 | /iot/points | views/iot/PointList.vue | `iot.point.view` | page |
| 　└ `iot.monitor` | 设备监控 | /iot/monitor | views/iot/DeviceMonitor.vue | `iot.monitor.view` | page |
| 　└ `iot.reading` | 采集读数 | /iot/readings | views/iot/ReadingList.vue | `iot.reading.view` | page |
| 　└ `iot.message` | 采集日志 | /iot/messages | views/iot/MessageList.vue | `iot.message.view` | page |
| 　└ `ehs.regulation` | 安全制度 | /ehs/safety/regulations | views/ehs/SafetyRegulationList.vue | `ehs.regulation.view` | page |
| 　└ `ehs.training` | 安全培训 | /ehs/safety/trainings | views/ehs/SafetyTrainingList.vue | `ehs.training.view` | page |
| 　└ `ehs.hazard` | 隐患排查 | /ehs/safety/hazards | views/ehs/HazardList.vue | `ehs.hazard.view` | page |
| 　└ `ehs.emergency-plan` | 应急预案 | /ehs/safety/emergency-plans | views/ehs/EmergencyPlanList.vue | `ehs.emergency_plan.view` | page |
| 　└ `ehs.accident` | 事故处理 | /ehs/safety/accidents | views/ehs/AccidentList.vue | `ehs.accident.view` | page |
| 　└ `ehs.env-monitor` | 排污监测 | /ehs/environment/monitors | views/ehs/EnvironmentMonitorList.vue | `ehs.env_monitor.view` | page |
| 　└ `ehs.waste` | 固废危废 | /ehs/environment/wastes | views/ehs/WasteRecordList.vue | `ehs.waste.view` | page |
| 　└ `ehs.compliance` | 环保合规 | /ehs/environment/compliance-checks | views/ehs/ComplianceCheckList.vue | `ehs.compliance.view` | page |
| 　└ `ehs.fire-facility` | 消防设施 | /ehs/fire/facilities | views/ehs/FireFacilityList.vue | `ehs.fire_facility.view` | page |
| 　└ `ehs.fire-drill` | 消防演练 | /ehs/fire/drills | views/ehs/FireDrillList.vue | `ehs.fire_drill.view` | page |
| 　└ `ehs.hot-work` | 动火作业 | /ehs/fire/hot-works | views/ehs/HotWorkPermitList.vue | `ehs.permit.view` | page |
| 　└ `ehs.special-equipment` | 特种设备检验 | /ehs/equipment-safety/special-equipment | views/ehs/SpecialEquipmentList.vue | `ehs.special_equipment.view` | page |
| 　└ `ehs.maintenance-permit` | 检维修作业 | /ehs/equipment-safety/maintenance-permits | views/ehs/MaintenancePermitList.vue | `ehs.permit.view` | page |
| 　└ `ehs.intrinsic-check` | 本质安全检查 | /ehs/equipment-safety/intrinsic-checks | views/ehs/IntrinsicSafetyCheckList.vue | `ehs.safety_check.view` | page |
| 　└ `ehs.explosion-proof-check` | 防爆防静电检查 | /ehs/equipment-safety/explosion-proof-checks | views/ehs/ExplosionProofCheckList.vue | `ehs.safety_check.view` | page |
| 　└ `ehs.fire-proof-check` | 防火防爆检查 | /ehs/equipment-safety/fire-proof-checks | views/ehs/FireProofCheckList.vue | `ehs.safety_check.view` | page |

## 五、权限合并规则（多角色用户）

规则实现在 `apps/core/selectors.py::resolve_data_scope`，**后端启动与测试均校验该规则**：

1. **超级管理员**不受限制：`is_superuser=True` 的账号在数据范围上直接得到 `all`；
   在操作权限上 `User.permission_codes()` 返回的是**通配符 `{"*"}`**，而不是 173 条编码的展开。

   > ⚠️ **通配符契约（真实缺陷的教训）**：任何客户端都必须把 `*` 解释为「全部权限」。
   > 前端实现在 `frontend/src/stores/auth.ts::hasFullAccess`；
   > 早期版本只做 `permissions.includes(code)`，导致超级管理员被误判为「没有任何权限」、
   > 所有新增 / 编辑 / 删除按钮全部消失（已修复，回归用例 `frontend/tests/auth-store.spec.ts`）。
   > 后端 `has_permission_codes()` 同步支持 `*`，两者语义必须一致。
2. **无角色**用户 → 空范围（`none`），看不到任何业务数据。
3. **操作权限取并集**：用户拥有多个角色时，只要任一角色授予某权限编码，即视为拥有。
4. **数据范围取最宽的一档**：按 `DataScopeType.rank_map()` 排序，取 rank 最高的角色档次作为生效档次。
   - 例：角色 A = 指定仓库，角色 B = 本公司 → 生效档次为「本公司」。
5. **同档次内取并集**：多个角色均为 `custom` 时，各角色授权的组织范围合并。
6. **先公司边界，再细分维度**：`company` 边界首先施加，工厂/部门/仓库维度只在公司边界内生效，
   不能借由某个角色的组织授权突破公司边界。
7. **自定义范围维度间取并集、与公司边界取交集**（即 `OR(维度并集) AND 公司边界`）。
8. **单一维度范围缺少对应字段时 fail-closed**：若角色范围为 `factory`/`department`/`warehouse`，
   但被查询模型上**没有该维度字段**，则返回**空集**（就严不就宽），而不是退化为「不过滤」。
9. **共享主数据显式放开**：`scope_fields=None` 的模型（如颜色、尺码、计量单位等全局共享主数据）
   不施加数据范围过滤，属于**显式声明**，不是遗漏。

> 规则 8 是安全关键点：任何「维度字段缺失」都必须收敛为「看不到」，不允许静默放宽。

## 六、权限执行位置（任务书 6.4）

| 位置 | 实现方式 | 对应测试 |
| --- | --- | --- |
| 列表查询过滤 | Selector 中统一 `apply_data_scope()` | `test_permissions.py`（范围过滤断言） |
| 详情访问校验 | `get_object()` 走同一 scope 过滤后的查询集 | `test_permissions.py` |
| 修改 / 审批 / 删除校验 | `HasRequiredPermissions` + Service 内 `require_codes()` | `test_permissions.py`、`test_workflow_api.py` |
| 关联对象选择校验 | 选项类接口（下拉数据源）同样走 scope | `test_permissions.py`（跨范围选项不可见） |
| 导出与异步任务校验 | 导出任务记录发起人，执行与下载时**重新校验**权限状态 | 阶段 2 随导出实现 |
| 附件下载校验 | `core.attachment.download` 权限 + 业务对象可达性校验 | `test_core_services.py` |
| 图表汇总校验 | `analytics` 聚合同样按 scope 过滤 | `test_smoke_api.py::test_dashboard_endpoint` |

**权限撤销后的收敛**：`identity_user.permission_version` 用于在权限变更时使已缓存的权限判定失效；
后台导出任务在执行与下载两个时点**分别校验**，避免账号权限被撤销后仍可下载敏感数据。
登录态变更（改密、停用）按规则使现有会话失效。

## 七、必测案例映射（任务书 14.2 中与权限相关的部分）

| 必测案例 | 覆盖测试 |
| --- | --- |
| 1. 未登录访问被拒绝 | `test_auth_api.py`（未认证返回 403）、HTTP 验证脚本（未登录访问 `/identity/users/`） |
| 2. 无操作权限不能调用接口 | `test_permissions.py::test_*permission_denied*` |
| 3. 工厂和仓库范围不能越权 | `test_permissions.py`（scope 过滤断言） |
| 4. 关联对象 ID 不能绕过范围限制 | `test_permissions.py`（跨范围详情返回 404/403） |
| 20. 敏感附件不能越权下载 | `test_permissions.py::test_attachment_download_requires_permission` |
| 3/4（客户与供应商主数据） | `test_crm_api.py`、`test_srm_api.py`：列表 / 详情 / 写入三处范围校验；联系人、资质通过 `customer__company_id`、`supplier__company_id` 继承父级范围，跨公司详情返回 404、跨公司写入返回 403 `OUT_OF_DATA_SCOPE` |
| 3 （库存数据范围） | `test_wms_inventory.py::test_api_enforces_warehouse_scope`：仓库范围外的仓库 ID 不可查询、不可建单 |
| 2 （库存操作权限） | `test_wms_inventory.py::test_inventory_endpoints_require_permission`：无 `wms.document.post` 的用户过账返回 403 |
| 1 （库存未登录） | `test_wms_inventory.py::test_inventory_endpoints_require_login`：余额/流水/单据三类接口未登录均被拒 |
| 1 / 2 / 3 / 4 （MRP） | `test_mrp.py`：`test_anonymous_access_rejected`（匿名 403）、`test_view_only_user_cannot_run_mrp`、`test_user_without_convert_permission_cannot_convert`、`test_convert_requires_procurement_requisition_create`（转单同时要求 `planning.mrp.convert` 与 `procurement.requisition.create`）、`test_api_run_scoped_to_company_and_warehouse`（公司 / 仓库范围）、`test_mrp_permissions_do_not_grant_other_modules`（权限不外溢）、`test_archive_api_requires_permission_and_is_audited` |

其余必测案例（部分并发场景、排班冲突、表计复位等）属于后续阶段，见 `docs/test-report.md` 的「未执行」清单。

## 八、安全限制（硬性）

- **Django 内置权限不能替代业务数据权限**：`is_staff` 不等于业务权限；业务接口一律走权限点 + 数据范围。
- 前端不做最终授权：即使前端隐藏按钮，后端仍必须独立校验（已通过 HTTP 验证脚本确认：直接调用接口会被拒绝）。
- 权限编码是**跨模块契约**：新增页面/接口必须先在 `permissions_registry` 注册，否则启动自检失败。
- 职业健康等敏感信息在阶段 6 落地时**单独授权**，不复用通用查看权限。
- 密码与设备密钥不得明文记入日志；审计不保存完整密码、令牌或无必要的敏感原文。
