"""Read-only project resource copies; never import/execute exported Skill code."""
import base64
import hashlib
import json

from fastapi import HTTPException
from . import hardware_resources


def project_resources(repo, structure, project_id):
    project = repo.get(project_id)
    modules, total = [], 0
    workspace = structure.get(project_id)
    selected = {i for version in workspace['versions'] for i in version['selectedIds']}
    live = {p['id']: p for p in structure.live_profiles()} if selected else {}

    def add_module(identity, name, files, **metadata):
        nonlocal total
        records = []
        for path, raw in sorted(files.items()):
            total += len(raw)
            if total > 12 * 1024 * 1024:
                raise HTTPException(413, '硬件资料超过12MiB，未截断或覆盖项目文件夹。')
            records.append(dict(path=path.split('/'), content=base64.b64encode(raw).decode(),
                                sha256=hashlib.sha256(raw).hexdigest()))
        revision = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
        modules.append(dict(id=identity, name=name, revision=revision, files=records, **metadata))

    components = list(dict.fromkeys(filter(None, [project['boardId'], *project['componentIds'],
        *(p['componentId'] for p in live.values() if p['id'] in selected and p.get('componentId'))])))
    for component in components:
        detail = repo.skills.get_active_by_component_id(component)
        # Runtime package includes the user's maintained wiring, examples and geometry.
        files = {}
        for item in detail.files:
            if item.path.startswith('references/'):
                category = '结构' if item.path == 'references/mechanical.md' else '约束与参考'
                path = category + '/' + item.path.split('/', 1)[1]
            elif item.path.startswith(('examples/', 'models/')):
                path = ('编程/' if item.path.startswith('examples/') else '结构/参考模型/') + item.path.split('/', 1)[1]
            else:
                path = item.path
            files[path] = item.content.encode('utf-8')
        record = hardware_resources.index()['modules'].get(detail.skillName)
        if record and record['componentId'] == component:
            for relative, digest in record['files'].items():
                if relative == 'structure/README.md' or relative == 'examples/reviewed.md':
                    continue  # Runtime usage already contains reviewed and user examples.
                raw = hardware_resources.resource_path(f'hardware-skills/{detail.skillName}/{relative}').read_bytes()
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise HTTPException(422, '模块资源摘要不一致，未导出。')
                path = relative.replace('programming/', '编程/主控API/', 1).replace('structure/', '结构/参考外形/', 1)
                files[path] = raw
        if detail.mechanicalProfile:
            files['结构/机械档案.json'] = (json.dumps(detail.mechanicalProfile, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        notes = ('本目录是保存时当前模块资料的只读副本，不会自动安装、上传或运行。\n'
                 '修改副本不会改变平台约束。历史加工文件保留在项目的结构版本目录。\n'
                 '参考模型不是经过加工验收的结构件；尺寸、孔位与接线应核对准确型号和实物。\n')
        if not detail.mechanicalProfile:
            notes += '尚无结构化机械档案，请补充外形、安装孔、接口开口与避让数据，不得从图片推断。\n'
        files['结构/资料说明.md'] = notes.encode('utf-8')
        files['模块资料.json'] = (json.dumps(dict(componentId=component, skillName=detail.skillName,
            packageRevision=detail.revision, name=detail.displayName, snapshotKind='current_reference_copy'), ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        add_module(detail.skillName, detail.displayName, files, componentId=component)

    # Structure-only parts selected in this project's history remain separate identities.
    for entry in hardware_resources.index()['structure']['profiles']:
        if entry['id'] not in selected or entry['componentId'] in {m['componentId'] for m in modules}:
            continue
        profile = live[entry['id']]
        files = {'结构/profile.json': hardware_resources.resource_bytes(entry['path'])}
        if entry.get('thumbnail'):
            files['结构/' + entry['thumbnail'].rsplit('/', 1)[1]] = hardware_resources.resource_bytes(entry['thumbnail'])
        add_module('part_' + entry['id'], profile['name'], files, componentId=entry['componentId'])
    custom = {}
    for version in workspace['versions']:
        for profile in version['customProfiles']:
            if profile['id'] not in version['selectedIds']:
                continue
            name, files = custom.setdefault(profile['id'], (profile.get('name') or profile['id'], {}))
            files[f'结构/历史/V{version["revision"]:03}/profile.json'] = (json.dumps(profile, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    for identity, (name, files) in sorted(custom.items()):
        add_module('part_' + identity, name, files, componentId=None)
    return dict(schemaVersion=1, modules=modules)
