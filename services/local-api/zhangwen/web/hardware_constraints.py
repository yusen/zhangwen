"""Unknown-aware adapter over the original declarative Hardware Skill operators."""
from collections import defaultdict

from zhangwen.hardware.models import HardwareCategory, ValidationCheck, ValidationSeverity
from zhangwen.hardware import rule_engine as engine
from . import module_guides


def complete_checks(repo, details, result):
    components = [repo.component_from_detail(d) for d in details]
    if not components:
        return result
    dimensions = {'voltage', 'logic_level', 'current', 'i2c_address', 'mcu_support', 'firmware', 'component_selection'}
    result.checks = [c for c in result.checks if c.dimension not in dimensions]
    seen = set()
    for detail in details:
        for rule in detail.rules:
            signature = rule.model_dump_json(exclude={'id'})
            if signature in seen:
                continue
            seen.add(signature)
            operator = rule.operator.value
            if operator == 'range-overlap':
                field = rule.params.get('field')
                attr = {'electrical.voltage': 'voltage', 'electrical.logicLevel': 'logicLevel'}.get(field)
                if attr:
                    known = [c for c in components if getattr(c.electrical, attr) > 0]
                    result.checks.extend(engine._execute_range_overlap(known, rule))
            elif operator == 'sum-lte':
                result.checks.extend(engine._execute_sum_lte(components, rule))
            elif operator == 'contains-any':
                result.checks.extend(engine._execute_contains_any(components, rule))
            elif operator == 'required-if':
                result.checks.extend(engine._execute_required_if(components, rule))
            # I2C uniqueness is checked below with per-board local addresses.

    def warn(dimension, message, notes):
        result.checks.append(ValidationCheck(dimension=dimension, severity=ValidationSeverity.WARNING,
                                            message=message, details=notes))

    unknown_current = [d.displayName for d in details if d.category != HardwareCategory.STRUCTURE
                       and d.specification.electrical.peakCurrent <= 0]
    if unknown_current:
        result.checks = [c for c in result.checks if c.dimension != 'current' or c.severity != ValidationSeverity.PASS]
        warn('current', '峰值电流资料不完整，无法确认完整供电余量。', '未知：' + '、'.join(unknown_current) + '。0是未知占位，不能按零负载计算。')
    loads = [c for c in components if c.category not in {HardwareCategory.POWER, HardwareCategory.STRUCTURE}]
    if any(c.electrical.peakCurrent > 0 for c in loads) and not any(c.category == HardwareCategory.POWER for c in components):
        warn('current', '未选择供电模块，无法确认峰值电流余量。', '已知负载仅为下限；还须核对实际供电路径。')

    boards = [d.componentId for d in details if d.category == HardwareCategory.MCU]
    if not boards and not any(c.dimension == 'mcu' for c in result.checks):
        warn('mcu', '未选择主控，电压、电平与主控适配检查不完整。', '请补充主控后重新检查。')
    addresses = defaultdict(list)
    for detail in details:
        info = module_guides.i2c_info(detail, repo.web_controllers)
        if info is None:
            continue
        local = next((e for e in repo.local_examples(detail) if len(boards) == 1 and e['boardId'] == boards[0]), {})
        guide = next((g for g in module_guides.guides(detail, repo.web_controllers)
                      if len(boards) == 1 and g['boardId'] == boards[0]), None)
        setup = module_guides.values(guide, local.get('setup')) if guide else local.get('setup') or {}
        if setup.get('interface') and setup['interface'].upper() not in {'I2C', 'IIC', 'I²C'}:
            continue
        address = local.get('i2cAddress') or (local.get('setup') or {}).get('address') or info['defaultAddress']
        if address and module_guides.valid_i2c_address(address):
            addresses[int(address, 16)].append(detail.displayName)
        else:
            warn('i2c_address', f'{detail.displayName}：I²C实际地址尚未确认。', '资料可能有多个可选地址；需要核对地址配置及实际总线。')
    for address, names in sorted(addresses.items()):
        if len(names) > 1:
            warn('i2c_address', f'I²C地址0x{address:02x}可能重叠，请核对实际总线。',
                 '、'.join(names) + '。采用当前主控保存地址或资料默认地址；尚未记录总线分配，不能判定在同一总线。')
    result.overall = engine._overall(result.checks)
    result.message = engine._summary(result.overall)
    return result
