# artifact_export

## 用途

写入当前任务目录，生成 2D/调试预览资产、metadata、`artifact.json`、`design-state.json`、`checks.json` 和 8 个 workflow 产物。

## 何时调用

- 所有预建模校验通过后。
- 同一任务重生成时，复用当前 `ZW-PRODUCT-*` 目录并覆盖受管产物。

## 输入格式

```json
{
  "prepared": {},
  "taskId": "ZW-PRODUCT-20260623-120000"
}
```

## 输出格式

```json
{
  "status": "artifact",
  "design_state": {},
  "exports": [],
  "checks": []
}
```

## 失败状态

导出文件写入失败不应阻断主体 artifact，但必须写入 warning 和 failed export entry。
