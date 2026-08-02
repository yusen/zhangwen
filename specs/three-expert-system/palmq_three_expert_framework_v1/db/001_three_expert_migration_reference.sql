-- 参考迁移脚本。Codex 应按现有 ORM/SQLite 表名适配，不应直接盲目执行。

BEGIN TRANSACTION;

-- 1. 为历史角色保留来源
ALTER TABLE expert_workspaces ADD COLUMN legacy_expert_type TEXT;
ALTER TABLE conversation_threads ADD COLUMN legacy_expert_type TEXT;
ALTER TABLE artifacts ADD COLUMN legacy_owner_expert TEXT;

-- 2. 工作区映射
UPDATE expert_workspaces
SET legacy_expert_type = expert_type,
    expert_type = CASE expert_type
      WHEN 'ideator' THEN 'problem_guide'
      WHEN 'educator' THEN 'problem_guide'
      WHEN 'open_hardware_designer' THEN 'smart_engineer'
      WHEN 'three_d_structure_designer' THEN 'structure_engineer'
      ELSE expert_type
    END
WHERE expert_type IN (
  'ideator',
  'educator',
  'open_hardware_designer',
  'three_d_structure_designer'
);

-- 3. 对话映射，保留独立线程
UPDATE conversation_threads
SET legacy_expert_type = expert_type,
    expert_type = CASE expert_type
      WHEN 'ideator' THEN 'problem_guide'
      WHEN 'educator' THEN 'problem_guide'
      WHEN 'open_hardware_designer' THEN 'smart_engineer'
      WHEN 'three_d_structure_designer' THEN 'structure_engineer'
      ELSE expert_type
    END
WHERE expert_type IN (
  'ideator',
  'educator',
  'open_hardware_designer',
  'three_d_structure_designer'
);

-- 4. 产物映射
UPDATE artifacts
SET legacy_owner_expert = owner_expert,
    owner_expert = CASE owner_expert
      WHEN 'ideator' THEN 'problem_guide'
      WHEN 'educator' THEN 'problem_guide'
      WHEN 'open_hardware_designer' THEN 'smart_engineer'
      WHEN 'three_d_structure_designer' THEN 'structure_engineer'
      ELSE owner_expert
    END
WHERE owner_expert IN (
  'ideator',
  'educator',
  'open_hardware_designer',
  'three_d_structure_designer'
);

COMMIT;
