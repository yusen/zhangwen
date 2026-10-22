"""Mechanical facts live in the existing Hardware Skill, never in another library."""
import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field
from zhangwen.hardware.hardware_skills import HardwareSkillValidationError


class MechanicalInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedRevision: str = Field(min_length=1, max_length=160)
    profile: dict
    notes: str = Field(min_length=1, max_length=8000)


def save(skills, name, request):
    if len(json.dumps(request.profile)) > 60000:
        raise HardwareSkillValidationError('机械资料过大。')
    detail = skills.get_skill(name)
    expected_id = detail.mechanicalProfile['profile_id'] if detail.mechanicalProfile else 'module_' + re.sub('[^a-zA-Z0-9_]', '_', detail.componentId)
    if request.profile.get('profile_id') != expected_id:
        raise HardwareSkillValidationError('机械档案 ID 与原模块绑定，不能替换其他硬件的身份。')
    if not request.notes.strip():
        raise HardwareSkillValidationError('请填写尺寸来源、型号修订与尚未核实的项目。')
    files = {item.path: item.content for item in detail.files}
    # A reference file is required by the original package schema. It is inert
    # documentation and never becomes a worker execution input.
    source = files.get('models/cadquery.py', '# Mechanical envelope reference only; no executable model.\n')
    declaration = {'schema': 'zhangwen.hardware-mechanical/v1', 'profile': request.profile,
                   'model': {'path': 'models/cadquery.py', 'sha256': hashlib.sha256(source.encode()).hexdigest(),
                             'verificationStatus': 'USER_CONFIRMED', 'executionPolicy': 'REFERENCE_ONLY'}}
    content = files.get('references/mechanical.md', '# 结构与机械档案\n')
    fence = r'```zhangwen:hardware-mechanical:v1\s*\n.*?```'
    block = '```zhangwen:hardware-mechanical:v1\n' + json.dumps(declaration, ensure_ascii=False, indent=2) + '\n```'
    content = re.sub(fence, lambda _: block, content, flags=re.S) if re.search(fence, content, re.S) else content.rstrip() + '\n\n' + block
    content = re.sub(r'\n<!-- web-mechanical-notes -->.*?<!-- /web-mechanical-notes -->', '', content, flags=re.S)
    # Notes are plain text and cannot inject a second machine-readable fence.
    notes = request.notes.replace('```', '｀｀｀').replace('<!--', '＜!--')
    content += '\n\n<!-- web-mechanical-notes -->\n' + notes + '\n<!-- /web-mechanical-notes -->\n'
    return skills.update_mechanical_files(name, updates=[('references/mechanical.md', content), ('models/cadquery.py', source)],
                               expected_revision=request.expectedRevision)


def context(skills, component_ids):
    result = []
    for component in dict.fromkeys(filter(None, component_ids)):
        detail = skills.get_active_by_component_id(component)
        result.append({'componentId': component, 'skillName': detail.skillName, 'revision': detail.revision,
                       'name': detail.displayName, 'mechanicalProfile': detail.mechanicalProfile,
                       'documentation': next((f.content for f in detail.files if f.path == 'references/mechanical.md'), ''),
                       'missing': [] if detail.mechanicalProfile else ['外形尺寸、安装孔、开口与避让资料尚未提供']})
    return result


def cad_profile(profile, component, image=''):
    """Data-only adapter to the existing enclosure worker's profile contract."""
    mounting = profile['mounting']
    return {'id': profile['profile_id'], 'name': profile['display_name'], 'componentId': component,
            'revision': profile['revision'], 'category': profile['category'], 'roles': profile['roles'],
            'thumbnail_url': image, 'dimensions_mm': profile['dimensions'], 'coordinate_system': profile['coordinate_system'],
            'mounting': {'mode': 'screw_holes' if mounting['holes'] else 'envelope_only',
                         'preferred_enclosure_surface': mounting['preferred_surface'],
                         'mating_hardware_face': mounting.get('mating_hardware_face') or '-Z',
                         'clearance_mm': mounting['clearance'],
                         'holes': [{'x': h['center']['x'], 'y': h['center']['y'], 'diameter_mm': h['diameter']} for h in mounting['holes']]},
            'opening': [dict(id=o['opening_id'], type='round_hole' if o['kind'] == 'circle' else 'rectangular_cutout',
                             basis='module_document', preferred_face=o['preferred_face'], clearance_mm=o['clearance'],
                             center_mm={**o['center'], 'z': o['center_z']},
                             **({'diameter_mm': o['diameter']} if o['kind'] == 'circle' else {'size_mm': {'width': o['size_u'], 'height': o['size_v']}})) for o in profile['openings']],
            'keepouts': [{'id': k['keepout_id'], 'shape': 'box', 'center_mm': k['center'], 'size_mm': k['size']} for k in profile['keepouts']],
            'cad_reference': {'shape': 'box'}, 'source_status': '模块机械档案声明；实物适配待核对'}
