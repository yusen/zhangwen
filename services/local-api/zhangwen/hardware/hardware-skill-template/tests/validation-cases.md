# 本地验证用例

```zhangwen:hardware-validation:v1
{
  "schema": "zhangwen.hardware-validation/v1",
  "cases": [
    {
      "id": "canonical-self-smoke",
      "components": ["$self"],
      "expectedOverall": ["PASS", "WARNING", "FAIL"]
    }
  ]
}
```

- 电压或逻辑电平不兼容时必须阻止规划通过。
- 机械 schema、模型 SHA 或 Python 语法无效时整包必须拒绝保存。
- 图片缺失或哈希不一致时包校验必须失败。
