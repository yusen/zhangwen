# ZW-HW-002 — 硬件库图片、可复制模板与默认目录收敛

状态：已完成（2026-07-15，未提交）

## 1. 目标

1. 正式内置硬件库只保留“行空板 K10”；移除其余 12 个历史占位 seed，且不得误删用户自建 Hardware Skill。
2. 在现有“一器件一 Hardware Skill”结构中增加真实图片资源，不建立独立于参数/规则的第二套硬件目录。
3. K10 使用本地缓存的官方产品图展示，记录来源、替代文本、署名、许可/使用说明和内容 SHA-256，不热链、不用生成图冒充实物。
4. 硬件知识库详情和项目硬件选择器都显示封面图；无图或加载失败时保留有文字的类别回退。
5. 提供可复制的 Hardware Skill 模板目录和中文说明，后续按同一结构可添加器件及其图片。

## 2. 重新规划后的目录

```text
<data_dir>/hardware-skills/<skill-name>/
├─ manifest.json
├─ SKILL.md
├─ assets/
│  ├─ cover.webp
│  └─ gallery-01.webp              # 可选，最多 6 张
├─ references/
│  ├─ specifications.md
│  ├─ compatibility-rules.md
│  ├─ integration.md
│  ├─ safety.md
│  └─ sources.md
├─ examples/usage.md
└─ tests/validation-cases.md
```

- `manifest.json.media[]` 只保存展示资源元数据：`path / role / alt / contentType / sha256 /
  sourceUrl / attribution / license`；电气参数和兼容规则仍只来自 Markdown。
- 图片路径只允许 `assets/<安全文件名>`，类型只允许 JPEG/PNG/WebP；单张最多 2 MiB、最多 6 张、媒体合计最多 8 MiB。
- Hardware Skill `revision` 同时覆盖八个 Markdown 文件和媒体元数据/已校验 SHA；换图必须产生新 revision。
- 图片 API 继续要求登录 Bearer 会话；桌面使用认证请求获取 Blob，不把用户图片公开为匿名静态目录。

## 3. 清理边界

- 正式 seed 只创建 `hw_seed_unihiker_k10`。
- 清理目标仅限旧清单明确列出的 12 个 `hw_seed_*` 占位器件及其 `MIGRATED/BUNDLED` 生成包。
- 用户自建 ID、UPLOAD/DIALOGUE/MANUAL 包、项目事实和数据库迁移备份不删除。
- 为避免升级时静默破坏用户曾编辑的旧迁移包，产品代码将旧 seed 从当前目录中退役到数据目录内的可恢复归档，而不是触碰项目历史快照；当前工作区按同一规则执行。

## 4. 图片与来源边界

- K10 封面来源：DFRobot 官方产品页 `https://www.dfrobot.com/product-2904.html`，SKU `DFR0992-EN`。
- 官方图片缓存到包内，应用不依赖第三方热链。署名为 DFRobot；公开再分发前仍需由发布方确认图片使用授权。
- 模板不得接受无来源、含隐私、超限、扩展名与真实 MIME 不一致或 SHA 不匹配的资源。

## 5. 实施里程碑

- [x] M1：先补媒体契约、K10-only seed、媒体读取与 UI 失败回归。
- [x] M2：实现 manifest 兼容媒体、受控读取、认证图片 API 与 revision 保护。
- [x] M3：缓存 K10 官方封面，收敛旧 seed，并提供可复制模板。
- [x] M4：知识库与项目选择器接入认证图片、回退和响应式布局。
- [x] M5：运行后端/前端/契约/构建、隔离浏览器三档验收，更新 docs/HANDOFF。

## 6. Decision Log

- 2026-07-15：图片是展示资源，不进入电气参数、规则或三师工程事实；避免图片目录成为第二硬件真值。
- 2026-07-15：图片使用本地缓存和认证读取，不使用远程热链；实际产品图不能由生成模型替代。
- 2026-07-15：模板与运行包同构，后续添加器件时必须同时给出来源与使用权说明。
- 2026-07-15：默认目录只保留 K10，但用户创建包和历史项目快照不属于旧占位 seed 清理范围。

## 7. Progress

- 2026-07-15：完成只读审计。确认正式数据与 Web QA 数据均由 13 个旧 seed 组成，除 K10 外的 12 项均为占位样例；现有契约没有媒体字段，两个硬件卡片使用类别字形。
- 2026-07-15：确认 K10 官方产品页与官方产品图地址，决定缓存并记录来源，不使用生成图。
- 2026-07-15：后端媒体/清理/模板专项 `3 passed`；前端图片专项 `2 passed`；TypeScript 严格检查通过；前端全量 `172 passed`。
- 2026-07-15：旧多器件行为测试改用显式测试夹具，生产默认契约保持 K10-only；原失败模块复跑 `63 passed`。最终后端全量为 `541 passed / 1 failed / 1 warning`；唯一失败是与本任务无关的 CAD intake 既有错误码断言（实际 `CAD_INTAKE_REVISED`，旧预期 `CAD_PROJECT_PROFILE_SELECTION_STALE`）。
- 2026-07-15：`services/local-api/.data`、`.data/web-fake`、`.data/web-paid`、`.data/web-progress-qa` 的活动数据库与 Hardware Skill 均收敛为唯一 K10；前两者各把 12 个旧生成包移入 `retired-hardware-seeds`，后两者没有旧目录可迁移。四套 K10 均有 1 张封面。
- 2026-07-15：隔离浏览器完成注册登录、公共知识和分析后项目硬件选择验收。`1280x800`、`720x800`、`390x844` 均为 1 个 K10 条目、图片自然尺寸 `830x554`、无页面/对话框横向溢出，`main === 1`、`CenterChat === 1`、右侧固定三 Tab，控制台无 warning/error；进程、页面与临时数据已清理。

## 8. 主要交付路径

- 可复制模板：`services/local-api/zhangwen/hardware/hardware-skill-template/README.md`
- K10 本地封面：`services/local-api/zhangwen/hardware/catalog-assets/unihiker-k10-cover.webp`
- 媒体契约与仓储：`services/local-api/zhangwen/hardware/{models,hardware_skills,router}.py`
- 桌面认证图片组件：`apps/desktop/src/components/hardware/HardwareMediaImage.tsx`
- 回归：`services/local-api/tests/test_hardware_catalog_media.py`、`apps/desktop/src/__tests__/HardwareCatalogMedia.test.tsx`
