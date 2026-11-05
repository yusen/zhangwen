"""Saved project evidence for a user-requested review. No files or tools for the model."""
import difflib
import json

from .workflow_models import Baseline, ProjectReview, Proposal, ReviewSource, digest


def records(value):
    # Discussions, private reflections and attachments do not affect engineering evidence.
    return digest({key: value[key] for key in ('definitions', 'conditions', 'cases', 'runs', 'changes')})


def clipped(text, limit):
    return {'text': text[:limit], 'truncated': len(text) > limit, 'characters': len(text)}


def saved_code(repo, pid, ref):
    if ref['mode'] == 'none': return ''
    if ref['mode'] == 'lua':
        from .lua_coding import load
        v = next((v for v in load(repo, pid).versions if v.revision == ref['revision'] and v.source == 'saved'), None)
        return v.code if v else ''
    if ref['mode'] == 'idea':
        from .idea import load
        v = next((v for v in load(repo, pid).versions if v.revision == ref['revision']), None)
        return '\n'.join('--- ' + f.path + '\n' + f.content for f in v.files) if v else ''
    v = next((v for v in repo.versions(pid) if v['revision'] == ref['revision'] and v.get('source') != 'ai'), None)
    return v['code'] if v else ''


def saved_structure(repo, pid, ref):
    if not ref: return ''
    with repo.connect() as conn:
        rows = conn.execute('SELECT preview_json FROM artifact_versions WHERE artifact_id=? ORDER BY version DESC', (repo.artifact_id(pid, 'structure'),)).fetchall()
    for row in rows:
        v = json.loads(json.loads(row[0])['code'])
        if v['revision'] != ref['revision']: continue
        result = v['result']
        # Include specifications, dimensions and checks, never meshes, photos or asset bytes.
        allowed = ('title', 'message', 'questions', 'design_state', 'parameters', 'checks', 'designSpec',
                   'hardwareInstallations', 'templateEdit', 'templateParts', 'build', 'bom', 'designKind')
        return json.dumps({k: result[k] for k in allowed if k in result}, ensure_ascii=False, indent=2)
    return ''


def sources(repo, pid, state):
    current = state['current']; codes = state['codeVersions']; structures = state['structureVersions']
    code = saved_code(repo, pid, current['code'])
    previous_code = next((v for v in codes if v['mode'] == current['code']['mode'] and v['revision'] < (current['code']['revision'] or 0)), None)
    structure = saved_structure(repo, pid, current['structure'])
    previous_structure = next((v for v in structures if current['structure'] and v['revision'] < current['structure']['revision']), None)

    def comparison(before, after):
        # Bound diff inputs as well as output. Truncation is explicit to the model and reader.
        a, b = before[:20000], after[:20000]
        diff = ''.join(difflib.unified_diff(a.splitlines(keepends=True), b.splitlines(keepends=True), fromfile='上一保存版本', tofile='当前保存版本', n=2))
        return {**clipped(diff, 6000), 'inputTruncated': len(before) > 20000 or len(after) > 20000}

    return {'program': {'reference': current['code'], **clipped(code, 16000), 'previous': previous_code,
                        'changes': comparison(saved_code(repo, pid, previous_code), code) if previous_code else None},
            'structure': {'reference': current['structure'], **clipped(structure, 16000), 'previous': previous_structure,
                          'changes': comparison(saved_structure(repo, pid, previous_structure), structure) if previous_structure else None}}


def source(state, stamp, method):
    current = state['current']; value = state['checkpoint']
    active = [c for c in value['cases'] if c['active']]
    states = [s for s in state['caseStates'] if s['id'] in {c['id'] for c in active}]
    counts = {k: sum(s['status'] == k for s in states) for k in ('passed', 'failed', 'blocked', 'stale', 'unrecorded')}
    facts = [f"作品目标：{'已确认 V' + str(current['definitionRevision']) if current['definitionRevision'] else '尚未确认'}",
             f"程序：{'已保存 V' + str(current['code']['revision']) if current['code']['revision'] else '尚无已保存程序'}",
             f"结构：{'已保存 V' + str(current['structure']['revision']) if current['structure'] else '尚无已生成结构'}",
             f"当前测试共{len(active)}项：记录通过{counts['passed']}项、未通过{counts['failed']}项、暂无法测试{counts['blocked']}项、需重测{counts['stale']}项、未记录{counts['unrecorded']}项。",
             '测试状态来自用户填写的观察；保存文件和模型检查不能证明实物可用。']
    return ReviewSource(baseline=Baseline.model_validate(current), records=records(value), checkedAt=stamp, facts=facts, method=method)


def record_review(state):
    current = state['current']; active = [c for c in state['checkpoint']['cases'] if c['active']]
    gaps = []
    if not current['definitionRevision']: gaps.append('还没有确认作品目标，先说清作品应完成什么。')
    if not current['code']['revision']: gaps.append('还没有已保存的程序；如果作品需要控制功能，请先完成程序。')
    if not current['structure']: gaps.append('还没有已生成的结构；是否需要外壳或机构，由你决定。')
    if not active: gaps.append('还没有测试清单，无法判断作品是否达到目标。')
    for s in state['caseStates']:
        c = next((c for c in active if c['id'] == s['id']), None)
        if c and s['status'] != 'passed':
            label = {'stale': '条件有变化，需要重测', 'failed': '观察记录未通过', 'blocked': '暂时无法测试', 'unrecorded': '还没有观察记录'}[s['status']]
            gaps.append(c['title'] + '：' + label + ('（' + '、'.join(s['reasons']) + '）' if s['reasons'] else ''))
    review = ProjectReview(conclusion='已核对保存与测试记录；' + ('还有待补充或验证的内容。' if gaps else '当前测试均有用户填写的通过记录，展示前请再核对实物。'),
        comparison='本次只核对已有记录。尚未使用 AI 比较程序逻辑与结构尺寸，也未验证实物；配置造物统筹师的 AI 后可再次检查。',
        gaps=gaps[:10], nextSteps=['查看下方检查依据，按待完成项补充资料或动手测试。'],
        decisions=['决定是否需要结构设计，以及接下来请哪位伙伴协作。'])
    return Proposal(summary=review.conclusion, question=None, definition=None, tests=[], review=review)
