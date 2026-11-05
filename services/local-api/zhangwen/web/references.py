"""Bounded project documents in the existing Artifact store; no file/network tools."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import PurePosixPath
from xml.etree import ElementTree

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator, field_validator
from .models import Boundary

MAX_TEXT = 120_000
MAX_ORIGINAL = 1_500_000
TEXT_SUFFIXES = {'.txt', '.md', '.markdown', '.py', '.lua', '.html', '.htm', '.js', '.ts', '.json', '.csv', '.css', '.xml', '.yaml', '.yml', '.ino', '.c', '.h'}


class ReferenceInput(Boundary):
    name: str = Field(min_length=1, max_length=200)
    original: str = Field(max_length=MAX_ORIGINAL)
    encoding: str = Field(pattern='^(text|base64)$')
    mode: str = Field(default='auto', pattern='^(auto|pin|off)$')
    expectedVersion: int = Field(default=0, ge=0)

    @field_validator('name')
    @classmethod
    def path(cls, value):
        parts = value.split('/')
        if (len(parts) > 6 or any(not p or p in {'.', '..'} or p.endswith(('.', ' '))
                                or re.match(r'(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)', p) for p in parts)
                or re.search(r'[\\<>:"|?*\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]', value)):
            raise ValueError('资料名称必须是安全的项目内相对路径。')
        return value


def extract(value: ReferenceInput) -> str:
    suffix = PurePosixPath(value.name).suffix.lower()
    if value.encoding == 'text' and suffix in TEXT_SUFFIXES:
        text = value.original
    elif value.encoding == 'base64' and suffix in {'.docx', '.pdf'}:
        try:
            raw = base64.b64decode(value.original, validate=True)
            if suffix == '.docx':
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    entry = archive.getinfo('word/document.xml')
                    if entry.file_size > 2_000_000 or len(archive.infolist()) > 2000:
                        raise ValueError('Word内容过大')
                    xml = archive.read(entry)
                    if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                        raise ValueError('不支持含实体的文档')
                    root = ElementTree.fromstring(xml)
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    text = '\n'.join(''.join(t.text or '' for t in p.findall('.//w:t', ns)) for p in root.findall('.//w:p', ns))
            else:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(raw), strict=True)
                if reader.is_encrypted or len(reader.pages) > 100:
                    raise ValueError('PDF加密或超过100页')
                pages = [page.extract_text() or '' for page in reader.pages]
                if not any(body.strip() for body in pages):
                    raise ValueError('扫描PDF没有可提取文字，请先OCR后导入')
                text = '\n\n'.join(f'【第{index+1}页】\n' + (body if body.strip() else '[本页未提取到文字，可能为空白或图片；未分析]')
                                    for index, body in enumerate(pages))
        except ImportError as exc:
            raise HTTPException(422, 'PDF解析依赖未准备，请更新安装或先转换为TXT。') from exc
        except Exception as exc:
            raise HTTPException(422, '文档无法解析：请使用未加密的文本PDF或DOCX；扫描件需先OCR，单文件最多约1MiB。') from exc
    else:
        raise HTTPException(422, '暂支持文本/代码、文本PDF和DOCX；图片、扫描件及旧DOC请先转换。')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if not text.strip() or '\x00' in text or len(text) > MAX_TEXT or '\ufffd' in text:
        raise HTTPException(422, '未提取到完整有效文字，或超过12万字符；请拆分文档或转换为UTF-8文本。')
    return text


class ReferenceVersion(Boundary):
    id: str = Field(pattern=r'^ref_[a-f0-9]{32}$')
    version: int = Field(ge=1, le=1000)
    name: str
    text: str = Field(max_length=MAX_TEXT)
    original: str = Field(max_length=MAX_ORIGINAL)
    encoding: str
    mode: str
    checksum: str = Field(pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def integrity(self):
        value = ReferenceInput(name=self.name, original=self.original, encoding=self.encoding, mode=self.mode)
        if extract(value) != self.text or digest(self.text) != self.checksum:
            raise ValueError('资料内容或摘要不一致。')
        return self


class Citation(Boundary):
    id: str = Field(pattern=r'^ref_[a-f0-9]{32}$')
    version: int = Field(ge=1)
    name: str = Field(max_length=200)
    startLine: int = Field(ge=1)
    endLine: int = Field(ge=1)
    text: str = Field(max_length=4000)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def list_references(repo, project_id, *, history=False):
    repo.get(project_id)
    with repo.connect() as conn:
        rows = conn.execute('''SELECT v.preview_json FROM artifacts a JOIN artifact_versions v ON v.artifact_id=a.id
            WHERE a.project_id=? AND a.source_agent_id='zhangwen-reference'
            AND (? OR a.current_version_id=v.id) ORDER BY a.id, v.version''', (project_id, history)).fetchall()
    return [json.loads(json.loads(row[0])['code']) for row in rows]


def insert_reference(conn, project_id, value, now):
    artifact = f'project_reference_{project_id}_{value["id"]}'
    version_id = f'{artifact}_v{value["version"]}'
    conn.execute('''INSERT INTO artifacts(id,project_id,title,kind,status,source_agent_id,current_version_id,created_at,updated_at)
        VALUES(?,?,?,'DOCUMENT','DRAFT','zhangwen-reference',?,?,?) ON CONFLICT(id) DO UPDATE SET
        title=excluded.title,current_version_id=excluded.current_version_id,updated_at=excluded.updated_at''',
        (artifact, project_id, value['name'], version_id, now, now))
    preview = json.dumps({'kind': 'TEXT', 'summary': '项目参考资料，仅供分析', 'code': json.dumps(value, ensure_ascii=False)}, ensure_ascii=False)
    conn.execute('''INSERT INTO artifact_versions(id,artifact_id,project_id,version,status,mime_type,preview_json,
        dependencies_json,source_entity_type,source_entity_id,checksum,created_at)
        VALUES(?,?,?,?,'DRAFT','text/plain',?,'[]','zhangwen_reference',?,?,?)''',
        (version_id, artifact, project_id, value['version'], preview, value['id'], value['checksum'], now))


def save_reference(repo, project_id, request):
    text = extract(request)
    with repo.lock:
        current = list_references(repo, project_id)
        previous = next((r for r in current if r['name'] == request.name), None)
        if request.expectedVersion != (previous['version'] if previous else 0):
            raise HTTPException(409, '同名资料已存在或已变更，请刷新后明确更新，未覆盖。')
        if not previous and len(current) >= 20:
            raise HTTPException(413, '每项目最多20份资料。')
        item = dict(id=previous['id'] if previous else 'ref_' + uuid.uuid4().hex,
                    version=previous['version']+1 if previous else 1, name=request.name, text=text,
                    original=request.original, encoding=request.encoding, mode=request.mode, checksum=digest(text))
        history = list_references(repo, project_id, history=True)
        if len(history) >= 200 or sum(len(json.dumps(r, ensure_ascii=False).encode()) for r in history + [item]) > 12_000_000:
            raise HTTPException(413, '资料历史已达容量上限，请保留当前项目并新建项目整理。')
        ReferenceVersion.model_validate(item)
        with repo.connect() as conn:
            insert_reference(conn, project_id, item, datetime.now(UTC).isoformat())
        return item


def terms(text):
    lower = text.lower()
    result = set(re.findall(r'[a-z0-9_./:-]{2,}', lower))
    for run in re.findall(r'[\u4e00-\u9fff]+', lower):
        result.update(run[i:i+2] for i in range(max(1, len(run)-1)))
    return result


def select_references(items, query, budget=12000):
    candidates = []
    query_terms = terms(query)
    for item in items:
        if item['mode'] == 'off':
            continue
        lines = item['text'].splitlines()
        # Preserve line coordinates even for long minified code lines.
        for start in range(0, len(lines), 20):
            text = '\n'.join(lines[start:start+30])
            score = len(query_terms & terms(item['name'] + '\n' + text))
            if score or item['mode'] == 'pin':
                for offset in range(0, len(text), 3000):
                    candidates.append((item['mode'] == 'pin', score, item['name'], start, offset, item, text[offset:offset+3000], min(len(lines), start+30)))
    candidates.sort(key=lambda c: (-int(c[0]), -c[1], c[2], c[3], c[4]))
    selected, used, seen = [], 0, set()
    for _, _, _, start, offset, item, text, end in candidates:
        key = (item['id'], start, offset)
        cost = len(text) + len(item['name']) + 100
        if key in seen or used + cost > budget:
            continue
        seen.add(key); used += cost
        selected.append(dict(id=item['id'], version=item['version'], name=item['name'], startLine=start+1, endLine=end, text=text))
    notice = '仅发送所列片段；未引用的资料未发送给模型。'
    if candidates and len(selected) < len(candidates):
        notice += '资料较长，本轮按相关性选取，未全文发送；可缩小问题或拆分资料。'
    if items and not selected:
        notice = '本轮未匹配到启用的资料片段；可在项目资料中设为优先参考。'
    return selected, notice


def context_text(citations):
    return '\n\n'.join(f'[{i+1}] {r["name"]} V{r["version"]} 第{r["startLine"]}–{r["endLine"]}行\n{r["text"]}' for i, r in enumerate(citations))


def router(repo):
    routes = APIRouter()

    @routes.post('/api/reference-preview')
    def preview(request: ReferenceInput):
        return {'text': extract(request)}

    @routes.get('/api/projects/{project_id}/references')
    def listing(project_id: str, history: bool = False):
        return {'references': list_references(repo, project_id, history=history)}

    @routes.post('/api/projects/{project_id}/references')
    def save(project_id: str, request: ReferenceInput):
        return save_reference(repo, project_id, request)

    return routes
