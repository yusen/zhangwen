# box_feasibility_check

## 用途

计算盒体尺寸，检查当前安装面容量是否能容纳硬件和交互开孔。

## 何时调用

- `orientation_resolve` 成功后。
- 用户调整盒体尺寸、边距、硬件间距或安装面后。

## 输入格式

```json
{
  "oriented_hardware_specs": [],
  "parameters": {},
  "user_constraints": {}
}
```

## 输出格式

```json
{
  "status": "ok",
  "enclosure": {},
  "capacity": {}
}
```

## 失败状态

- `needs_input`：盒体尺寸受用户约束，无法自动增大到可用尺寸。

