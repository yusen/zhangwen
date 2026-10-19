# 行空板 K10 本地验证用例

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

- 结构模型 SHA、Python 语法或机械 schema 不一致时，整包校验必须失败。
- K10 包络必须保持 83.2 × 51.3 × 10.6 mm 的受信身份门禁。
- 保存成功后，硬件目录与机械档案必须指向同一个 Hardware Skill revision。

