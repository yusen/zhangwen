"""Board-specific code references, kept separate from immutable legacy packages."""
import ast
from pathlib import Path

SKILLS = {"hw_labplus_mpython_v2": "mpython-v2", "hw_labplus_mpython_esp32s3_v3": "mpython-v3"}


def programming_context(board_id: str) -> str:
    if board_id == 'hw_seed_unihiker_k10':
        root = Path(__file__).with_name('programming-skills') / 'unihiker-k10'
        original = Path(__file__).resolve().parents[1] / 'hardware/board-skills/unihiker-k10'
        return (root / 'SKILL.md').read_text(encoding='utf-8') + '\n' + '\n'.join(
            (original / file).read_text(encoding='utf-8') for file in
            ('references/03-screen-api.md', 'templates/01_screen_shapes.py'))
    name = SKILLS.get(board_id)
    if not name:
        return ""
    root = Path(__file__).with_name("programming-skills") / name
    return "\n".join((root / file).read_text(encoding="utf-8") for file in ("SKILL.md", "references/api.md"))


def _k10_calls(tree):
    aliases = {}

    def path(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            parent = path(node.value)
            return parent + '.' + node.attr if parent else None
        return None

    nodes = sorted(ast.walk(tree), key=lambda node: (getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0)))
    for node in nodes:
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name == 'unihiker_k10':
                    aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom) and node.module == 'unihiker_k10':
            for item in node.names:
                aliases[item.asname or item.name] = 'unihiker_k10.' + item.name
        elif isinstance(node, ast.Assign):
            value = path(node.value)
            if value:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        aliases[target.id] = value
    return [(node, path(node.func)) for node in nodes if isinstance(node, ast.Call)]


def _mpython_raw_pins(tree):
    """Only unshadowed machine.Pin calls with literal/single constant 0 or 1.

    These are possible P-number mistakes, not proof: intentional raw GPIO use
    stays a warning. Dynamic values and locally shadowed names are left alone.
    """
    stores, imports = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for item in node.names:
                bound = item.asname or item.name.split('.')[0]
                imports[bound] = imports.get(bound, 0) + 1
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores[node.id] = stores.get(node.id, 0) + 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stores[node.name] = stores.get(node.name, 0) + 1
        elif isinstance(node, ast.arg):
            stores[node.arg] = stores.get(node.arg, 0) + 1
    aliases, constants = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                bound = item.asname or item.name
                if item.name == 'machine' and bound not in stores and imports.get(bound) == 1:
                    aliases[item.asname or item.name] = 'machine'
        elif isinstance(node, ast.ImportFrom) and node.module == 'machine':
            for item in node.names:
                if item.name == 'Pin' and (item.asname or item.name) not in stores and imports.get(item.asname or item.name) == 1:
                    aliases[item.asname or item.name] = 'machine.Pin'
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if stores.get(name) == 1 and name not in imports and isinstance(node.value, ast.Constant) and type(node.value.value) is int:
                constants[name] = node.value.value
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        path = aliases.get(func.id) if isinstance(func, ast.Name) else (
            aliases.get(func.value.id, '') + '.' + func.attr
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else None)
        if path != 'machine.Pin':
            continue
        arg = node.args[0]
        value = arg.value if isinstance(arg, ast.Constant) and type(arg.value) is int else (
            constants.get(arg.id) if isinstance(arg, ast.Name) else None)
        if value in (0, 1):
            found.append((arg, value))
    return sorted(found, key=lambda item: (item[0].lineno, item[0].col_offset))


def repair_mpython_pins(code: str, board_id: str) -> str:
    """Preview only: interpret the flagged 0/1 as board P0/P1, preserving modes."""
    if board_id != 'hw_labplus_mpython_v2':
        raise ValueError('P号修复仅适用于掌控板2.0。')
    tree = ast.parse(code)
    found = _mpython_raw_pins(tree)
    if not found:
        raise ValueError('未发现可可靠定位的 machine.Pin(0/1) 调用，动态引脚或重绑定请手动核对；原代码保留。')
    starts, offset = [], 0
    for line in code.encode('utf-8').splitlines(keepends=True):
        starts.append(offset)
        offset += len(line)
    data = code.encode('utf-8')
    for node, value in reversed(found):
        start, end = starts[node.lineno-1]+node.col_offset, starts[node.end_lineno-1]+node.end_col_offset
        # Keep the user's P-number variable effective when switching P0/P1.
        replacement = ('{0: 33, 1: 32}[' + node.id + ']' if isinstance(node, ast.Name) else str((33, 32)[value]))
        data = data[:start]+replacement.encode()+data[end:]
    note = '# 掌控板2.0引脚修复预览：原始Pin构造已映射P0=GPIO33、P1=GPIO32；变量映射仅含P0/P1。\n'
    result = note + data.decode('utf-8')
    if len(result.encode('utf-8')) > 65536:
        raise ValueError('修复后程序超过64KiB；原代码保留。')
    ast.parse(result)
    return result


def programming_diagnostics(code: str, board_id: str) -> list[dict]:
    """Bounded source checks for known board API/pin mistakes; never execute."""
    if board_id not in {'hw_seed_unihiker_k10', 'hw_labplus_mpython_v2'}:
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    if board_id == 'hw_labplus_mpython_v2':
        return [{'severity': 'WARNING', 'repair': 'mpython-pins', 'line': node.lineno,
                 'message': f'machine.Pin({value}) 操作原始 GPIO{value}，不是板上 P{value}。掌控板2.0 P0=GPIO33、P1=GPIO32；若接的是板上P口，请用 MPythonPin(P号, PinMode.OUT).Pin。可按P号预览修复；若刻意使用原始GPIO则保留原稿。错误引脚上的超时/上拉读数不能证明传感器损坏。'}
                for node, value in _mpython_raw_pins(tree)]
    calls = {name for _,name in _k10_calls(tree)} - {None}
    errors = []
    if any(call.startswith('unihiker_k10.draw.') or call in {
            'unihiker_k10.screen.text', 'unihiker_k10.screen.canvas.text'} for call in calls):
        errors.append({'severity':'FAIL', 'repair':'k10-screen', 'message':'K10 屏幕调用不符合当前官方参考：请用 screen.draw_text(text=…, x=…, y=…, font_size=…, color=…)；不使用 draw.text() 或 screen.text()。'})
    drawing = any(call.startswith('unihiker_k10.screen.draw_') for call in calls)
    if (drawing or 'unihiker_k10.screen.clear' in calls) and 'unihiker_k10.screen.init' not in calls:
        errors.append({'severity':'WARNING', 'message':'当前程序未发现 screen.init(dir=2)。K10 绘制/清除前应先初始化一次，否则可能报 canvas 不存在；请核对初始化流程。'})
    if drawing and 'unihiker_k10.screen.show_draw' not in calls:
        errors.append({'severity':'WARNING', 'message':'当前程序未发现 screen.show_draw()。K10 绘制后需要提交画面，否则屏幕可能不更新。'})
    return errors


def repair_k10_screen(code: str, board_id: str) -> str:
    """Return a reviewable deterministic repair. Never save, execute or upload."""
    if board_id != 'hw_seed_unihiker_k10':
        raise ValueError('屏幕修复仅适用于行空板 K10。')
    tree = ast.parse(code)
    prefix = '_zw_k10_display'
    if any((isinstance(node, ast.Name) and node.id.startswith(prefix))
           or (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name.startswith(prefix))
           for node in ast.walk(tree)):
        raise ValueError('程序已有屏幕修复辅助函数，请先检查现有版本；原代码保留。')
    calls = _k10_calls(tree)
    wrong = {'unihiker_k10.draw.text', 'unihiker_k10.screen.text', 'unihiker_k10.screen.canvas.text'}
    changes = []
    repaired = 0
    lines = code.encode('utf-8').splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1]+len(line))
    for node, name in calls:
        replacement = None
        if name in wrong:
            names = ['text','x','y','color']
            if not 3 <= len(node.args) <= 4 or node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
                raise ValueError('此处文字参数无法可靠转换，请按官方draw_text关键字参数手动修改；原代码保留。')
            values = [f'{key}={ast.get_source_segment(code,value)}' for key,value in zip(names,node.args)]
            replacement = prefix+'_text('+', '.join(values)+')'
            repaired += 1
        elif name == 'unihiker_k10.screen.clear' and not node.args and not node.keywords:
            replacement = prefix+'_clear()'
        elif name == 'unihiker_k10.screen.init':
            # Preserve supported orientation; lazily initialize once even when
            # the old program called init repeatedly from its drawing function.
            if node.args or any(kw.arg != 'dir' for kw in node.keywords):
                raise ValueError('屏幕初始化参数超出已核对格式，请手动核对；原代码保留。')
            arguments = ', '.join('dir='+ast.get_source_segment(code,kw.value) for kw in node.keywords)
            replacement = prefix+'_prepare('+arguments+')'
        if replacement is not None:
            changes.append((starts[node.lineno-1]+node.col_offset,
                            starts[node.end_lineno-1]+node.end_col_offset, replacement.encode('utf-8')))
    if not repaired:
        raise ValueError('未发现可直接修复的旧文字接口，原代码保留；请查看具体检查提示。')
    helpers = '''
# K10屏幕修复：独立于传感器驱动，初始化一次，绘制后提交显示。
_zw_k10_display_ready = False


def _zw_k10_display_prepare(dir=2):
    global _zw_k10_display_ready
    from unihiker_k10 import screen as _zw_screen
    if not _zw_k10_display_ready:
        _zw_screen.init(dir=dir)
        _zw_k10_display_ready = True
    return _zw_screen


def _zw_k10_display_clear():
    display = _zw_k10_display_prepare()
    display.clear()
    display.show_bg(color=0x000000)


def _zw_k10_display_text(text, x, y, color=0xFFFFFF):
    display = _zw_k10_display_prepare()
    display.draw_text(text=text, x=x, y=y, font_size=24, color=color)
    display.show_draw()

'''
    insertion = 0
    for node in tree.body:
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                or isinstance(node, ast.ImportFrom) and node.module == '__future__'):
            insertion = starts[node.end_lineno]
        else:
            break
    changes.append((insertion, insertion, helpers.encode('utf-8')))
    output = code.encode('utf-8')
    for start,end,value in sorted(changes, reverse=True):
        output = output[:start]+value+output[end:]
    result = output.decode('utf-8')
    if len(output) > 65536:
        raise ValueError('修复后程序超过64KiB，请精简后重试；原代码保留。')
    ast.parse(result)
    return result
