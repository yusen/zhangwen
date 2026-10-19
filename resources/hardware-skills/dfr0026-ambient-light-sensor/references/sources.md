# DFR0026 资料来源

## 来源优先级

1. DFRobot 官方产品 Wiki：电气参数、引脚说明、MicroPython 最小示例和 K10 连接说明。
2. DFRobot 官方商城产品页：SKU、3.3–5 V供电、15 μs响应、1–6000 lux、20 × 30 mm标称尺寸和当前价格。
3. 用户提供的光线传感器建模文档：30 × 22 mm PCB、孔位、接线口、感光器件简化体和10 mm接线避让。
4. 用户提供的掌问 Hardware Skill 模板：目录、单一事实源、机械模型、图片、SHA-256与revision要求。

## 记录

- `dfrobot-wiki:dfr0026`
  - 页面：https://wiki.dfrobot.com.cn/_SKU_DFR0026_%E6%A8%A1%E6%8B%9F%E7%8E%AF%E5%A2%83%E5%85%89%E7%BA%BF%E4%BC%A0%E6%84%9F%E5%99%A8
  - 访问日期：2026-07-16
  - 用途：电气、接口、MicroPython示例、K10连接。
- `dfrobot-product:dfr0026`
  - 页面：https://www.dfrobot.com.cn/goods-75.html
  - 访问日期：2026-07-16
  - 用途：产品规格、标称尺寸、响应时间、量程、价格。
- `dfrobot-image:dfr0026-v2`
  - 原始图片：https://imgtest.dfrobot.com.cn/DFRobotCnWikiImage/DFR0026V2.JPG
  - 权利人：DFRobot
  - 使用边界：用于产品识别和本地硬件库展示；公开再分发前需确认 DFRobot 图片授权。
- `user-model:dfr0026-2026-07-16`
  - 文件：`光线传感器.txt`
  - 用途：机械档案和 CadQuery 参考模型。
- `user-template:hardware-skill-2026-07-16`
  - 文件：`b98ca944-452a-4a68-84bf-54cd820fae3c.md`
  - 用途：最新模板要求。

## 冲突处理

- 电气事实以 DFRobot 官方资料为准。
- 当前精细机械档案以用户模型为准，但明确保留官方20 × 30 mm与模型30 × 22 mm的冲突。
- 未经实物卡尺验证，不把参考模型描述为可直接量产的制造模型。
