# design_revision

## 用途

把用户的修改语句转成结构化修改意图，让后端可以从受影响步骤重跑。它负责描述“改什么”，不直接生成 CAD，不直接写坐标。

## 何时调用

- `conversation_route` 输出 `revise_requirement`、`revise_artifact`、`change_mounting_face` 或 `selected_hardware_enclosure` 时。
- 用户提出“把 A 改成 B”“删除某功能”“换成某个传感器”“把某硬件移到底壳/上盖”等需求时。

## 输入格式

```json
{
  "prompt": "把超声波改成人体传感器",
  "currentDesignState": {},
  "selectedHardwareIds": ["grove_ultrasonic_ranger"],
  "hardware_library_summary": []
}
```

## 输出格式

```json
{
  "status": "ok",
  "add_functions": [],
  "remove_functions": [],
  "replace_hardware_roles": [
    {
      "from_hardware_id": "grove_ultrasonic_ranger",
      "to_hardware_id": "grove_digital_pir",
      "role": "proximity_sensor",
      "reason": "用户要求把接近检测改为人体传感器"
    }
  ],
  "remove_hardware_ids": ["grove_ultrasonic_ranger"],
  "force_selected_hardware_ids": ["grove_digital_pir"],
  "hardware_face_overrides": {},
  "parameter_overrides": {}
}
```

## 字段说明

- `add_functions`：新增功能描述。
- `remove_functions`：删除或砍掉的功能描述。
- `replace_hardware_roles`：硬件或角色替换关系。
- `remove_hardware_ids`：本轮应从选中硬件中移除的硬件。
- `force_selected_hardware_ids`：本轮应强制加入选中硬件的硬件。
- `hardware_face_overrides`：硬件安装面覆盖，例如 `{ "grove_passive_buzzer": "base_floor" }`。
- `parameter_overrides`：盒体尺寸、壁厚、间距等参数覆盖。

## 限制边界

- 只能引用硬件库或用户 custom profile 中存在的硬件 id。
- 不允许创造未知硬件尺寸。
- 修改默认在当前 `taskId` 内重算，不新建任务。
- 如果修改内容无法结构化，应返回 `needs_input`，让用户明确要改哪个功能或硬件。

## 验证方式

- “把超声波改成人体传感器”应移除 `grove_ultrasonic_ranger` 并加入 `grove_digital_pir`。
- “把蜂鸣器移到底壳”应输出 `hardware_face_overrides.grove_passive_buzzer = "base_floor"`。
- “给选定硬件做一个盒子”应保留用户已选硬件，生成基于 selected hardware 的外壳意图。
