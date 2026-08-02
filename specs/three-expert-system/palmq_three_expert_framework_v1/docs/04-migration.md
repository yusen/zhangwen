# 四专家到三师迁移

## ID 映射

```ts
const LEGACY_EXPERT_MAPPING = {
  ideator: "problem_guide",
  educator: "problem_guide",
  open_hardware_designer: "smart_engineer",
  three_d_structure_designer: "structure_engineer",
} as const
```

## 对话迁移

创想家和教育家都映射到问题引导师，但历史线程不合并：
- 保留原 threadId
- ownerExpert 更新为 problem_guide
- 添加 legacyExpertType
- 添加 archivedLegacyThread=true
- 新项目使用问题引导师的新主线程

## 产物迁移

- 保留 creatorLegacyExpert
- ownerExpert 使用新专家
- 不修改旧版本内容
- 重新计算可见分类
- 为依赖关系补充版本引用

## 迁移步骤

1. 新增新专家枚举。
2. 新增 legacy 字段。
3. 回填专家映射。
4. 回填工作区。
5. 修复产物 owner。
6. 修复对话索引。
7. 重建依赖索引。
8. 校验旧项目打开。
9. 移除前端旧角色入口，但保留读取兼容。
10. 迁移完成后保留回滚记录。
