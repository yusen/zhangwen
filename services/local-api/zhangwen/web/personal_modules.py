"""Self-service modules use the canonical Hardware Skill creator, not a new catalog."""
import json
import uuid
from fastapi import APIRouter
from pydantic import Field
from zhangwen.hardware.hardware_skills import HardwareSkillValidationError, _specification_markdown, _rules_markdown, default_rules
from zhangwen.hardware.models import HardwareSkillSpecification, HardwareSkillSourceKind
from .models import PersonalModuleInput, Boundary
from .hardware import EXAMPLES_START, EXAMPLES_END, WEB_CONTROLLERS


def create_module(skills, request):
    if request.boardId and request.boardId not in WEB_CONTROLLERS:
        raise HardwareSkillValidationError('当前主控无效。')
    token = uuid.uuid4().hex
    spec = HardwareSkillSpecification(
        componentId='hw_my_' + token, name=request.name, category=request.category,
        electrical=dict(voltage=request.voltage, logicLevel=request.logicLevel, peakCurrent=0,
                        communicationProtocol=request.protocol, supportedMCUs=[]),
        notes=request.description, verificationStatus='UNVERIFIED', sourceIds=['user-import'])
    sections = {'references/sources.md': '\n\n## 用户导入资料（未经实物核实）\n\n' + request.notes}
    usage = '\n\n## 用户提供的接线与案例\n\n' + request.description
    if request.boardId:
        usage += '\n\n' + EXAMPLES_START + '\n```json\n' + json.dumps([dict(boardId=request.boardId,
                 notes=request.description, code=request.code)], ensure_ascii=False, indent=2) + '\n```\n' + EXAMPLES_END + '\n'
    sections['examples/usage.md'] = usage
    return skills.create_skill(spec, skill_name='my-module-' + token, description=request.description,
                               source_kind=HardwareSkillSourceKind.MANUAL, migrated_sections=sections)


def router(repo):
    routes = APIRouter()

    @routes.post('/api/personal-modules', status_code=201)
    def create(request: PersonalModuleInput):
        return repo.skills.web_detail(create_module(repo.skills, request))

    @routes.put('/api/personal-modules/{skill_name}/facts')
    def facts(skill_name: str, request: PersonalFacts):
        detail = repo.skills.get_skill(skill_name)
        if not skill_name.startswith('my-module-'):
            raise HardwareSkillValidationError('此入口仅修改我的模块。')
        electrical = detail.specification.electrical.model_copy(update=dict(voltage=request.voltage, voltageMin=None,
                    voltageMax=None, logicLevel=request.logicLevel, communicationProtocol=request.protocol))
        spec = detail.specification.model_copy(update={'electrical': electrical})
        value = repo.skills.update_files(skill_name, expected_revision=request.expectedRevision, updates=[
            ('references/specifications.md', _specification_markdown(spec)),
            ('references/compatibility-rules.md', _rules_markdown(default_rules(spec)))])
        return repo.skills.web_detail(value)

    return routes


class PersonalFacts(Boundary):
    expectedRevision: str = Field(pattern=r'^[a-f0-9]{24}$')
    voltage: float = Field(ge=0, le=1000, allow_inf_nan=False)
    logicLevel: float = Field(ge=0, le=1000, allow_inf_nan=False)
    protocol: str = Field(min_length=1, max_length=80)
