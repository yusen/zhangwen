import { normalizeString, normalizeStringArray } from './pipeline/shared.js';

const PLANT_CARE_PATTERNS = [
  /智能.{0,8}(浇花|浇水|灌溉)/i,
  /自动.{0,8}(浇花|浇水|灌溉)/i,
  /植物.{0,8}(照看|看护|浇水|养护|护理|护理仪|看护仪)/i,
  /(浇花|浇水|灌溉).{0,8}(系统|装置|设备|产品|盒子|外壳|方案)/i,
  /plant\s*(care|caregiver|watering|irrigation)/i,
  /(smart|automatic)\s*(plant|flower).{0,16}(watering|irrigation|care)/i,
];

const SMART_PENDANT_PATTERNS = [
  /智能.{0,6}项链/i,
  /AI\s*项链/i,
  /带摄像头.{0,10}项链/i,
  /语音助手.{0,10}项链/i,
  /项链.{0,12}(摄像头|语音|助手|AI|智能)/i,
  /ai\s*pendant/i,
  /smart\s*pendant/i,
  /camera\s*pendant/i,
  /voice\s*assistant\s*pendant/i,
];

const PHOTO_ALBUM_PATTERNS = [
  /电子.{0,4}相册/i,
  /数码.{0,4}相册/i,
  /数字.{0,4}相框/i,
  /照片.{0,4}相框/i,
  /智能.{0,4}相册/i,
  /相册/i,
  /photo\s*album/i,
  /digital\s*photo\s*frame/i,
  /smart\s*photo\s*frame/i,
];

export const UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID = 'unihiker_light_effect_cup_v1';
export const UNIHIKER_HANDHELD_FAN_TEMPLATE_ID = 'unihiker_handheld_fan_v1';
export const MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID = 'mpython_board_enclosure_v1';
export const UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID = 'unihiker_auto_open_lid_box_v1';

export const BATCH_MODEL_TEMPLATE_IDS = Object.freeze([
  UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID,
  UNIHIKER_HANDHELD_FAN_TEMPLATE_ID,
  MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID,
  UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID,
]);

const LIGHT_EFFECT_CUP_PATTERNS = [
  /光效(?:水杯|杯)/i,
  /(?:行空板|K10).{0,10}(?:光效|RGB|LED|灯环|灯光).{0,8}(?:水杯|杯子)/i,
  /(?:水杯|杯子).{0,10}(?:光效|RGB|LED|灯环|灯光)/i,
  /(?:RGB|LED|灯环|灯珠|灯光).{0,10}(?:水杯|杯子)/i,
  /(?:light[\s-]*effect|rgb|led)\s*(?:water\s*)?(?:cup|mug)/i,
];

const HANDHELD_FAN_PATTERNS = [
  /手持(?:式)?(?:小)?风扇/i,
  /便携(?:式)?(?:小)?风扇/i,
  /(?:行空板|K10).{0,10}(?:手持|便携|小型|小).{0,6}风扇/i,
  /(?:手持|便携|小型|小).{0,6}风扇.{0,10}(?:行空板|K10)/i,
  /(?:handheld|portable)\s*(?:mini\s*)?fan/i,
];

const MPYTHON_BOARD_ENCLOSURE_PATTERNS = [
  /掌控板(?:\s*3(?:\.0)?)?\s*(?:的|专用)?\s*(?:外壳|保护壳|机壳|盒体)/i,
  /(?:给|为)?\s*掌控板(?:\s*3(?:\.0)?)?\s*(?:做|设计|生成|建模)(?:一个|一套|个)?\s*(?:外壳|保护壳|机壳|盒体)/i,
  /(?:外壳|保护壳|机壳|盒体)\s*(?:用于|适配|保护)?\s*掌控板(?:\s*3(?:\.0)?)?/i,
  /mpython(?:\s*board)?(?:\s*3(?:\.0)?)?\s*(?:的|专用)?\s*(?:外壳|保护壳|机壳|盒体)/i,
  /mpython(?:\s*board)?(?:\s*3(?:\.0)?)?.{0,6}(?:enclosure|case|shell)/i,
  /(?:enclosure|case|shell).{0,6}mpython(?:\s*board)?/i,
];

const AUTO_OPEN_LID_BOX_PATTERNS = [
  /行空板自动感应开盖智能盒子/i,
  /(?:行空板|K10).{0,12}(?:自动|感应|智能).{0,8}开盖.{0,8}(?:智能)?(?:盒子|盒|收纳盒)/i,
  /(?:自动|感应).{0,8}开盖.{0,8}(?:智能)?(?:盒子|盒|收纳盒)/i,
  /(?:智能盒子|智能盒|收纳盒).{0,10}(?:自动|感应).{0,8}开盖/i,
  /automatic\s*(?:sensor|sensing|smart)?\s*(?:open|opening)[\s-]*(?:lid|cover)\s*(?:box|case)/i,
];

const XIAO_PATTERNS = [
  /\bxiao\b/i,
  /seeed/i,
  /esp32s3/i,
  /esp32-s3/i,
];

const MPYTHON_PATTERNS = [
  /掌控板/,
  /\bmpython\b/i,
];

const UNIHIKER_PATTERNS = [
  /行空板/,
  /unihiker/i,
  /\bk10\b/i,
];

const PRODUCT_DEFINITIONS = Object.freeze({
  unihiker_plant_caregiver: {
    id: 'unihiker_plant_caregiver',
    name: '植物养护系统',
    product_name: '行空板植物养护系统',
    hardware_system: 'unihiker',
    status: 'available',
    model_status: 'implemented',
    template_id: 'unihiker_smart_watering_system_v1',
    description: '基于行空板 K10 的植物养护系统内置确定性产品。',
    hardware: [
      {
        hardware_id: 'battery_18650_holder',
        name: '18650 电池座',
        role: 'battery',
        hardware_system: 'common',
        function: '为主控、继电器和水泵控制链路提供电源。',
        why_needed: '植物养护系统需要独立电池盒作为供电硬件。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_k10',
        name: '行空板K10',
        role: 'controller',
        hardware_system: 'unihiker',
        function: '主控计算和交互显示',
        why_needed: '内置植物看护仪固定使用行空板 K10 作为主控。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_k10_io_expansion_board',
        name: 'micro:bit掌控IO扩展板子',
        role: 'controller_expansion',
        hardware_system: 'unihiker',
        function: '提供 K10 外接执行器和传感器的 IO 扩展能力。',
        why_needed: '用户指定 K10 与 K10 扩展板拼合置于盒子右侧旁边。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_sci_acquisition_module',
        name: 'SCI采集模块',
        role: 'data_acquisition',
        hardware_system: 'unihiker',
        function: '采集土壤湿度等传感器信号',
        why_needed: '参考项目通过 SCI 采集模块接入外部传感器。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_soil_moisture_sensor',
        name: '土壤湿度传感器',
        role: 'soil_moisture_sensor',
        hardware_system: 'unihiker',
        function: '土壤湿度检测',
        why_needed: '植物养护系统需要检测土壤湿度来判断是否需要供水。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_dc_water_pump',
        name: '直流水泵',
        role: 'water_pump',
        hardware_system: 'unihiker',
        function: '出水控制',
        why_needed: '植物养护系统需要水泵提供供水执行能力。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_relay_module',
        name: '继电器模块',
        role: 'pump_driver',
        hardware_system: 'unihiker',
        function: '水泵电源通断控制',
        why_needed: '主控需要通过继电器模块控制直流水泵通断。',
        profile_status: 'builtin',
      },
    ],
  },
  unihiker_photo_album: {
    id: 'unihiker_photo_album',
    name: '相册',
    product_name: '行空板相册',
    hardware_system: 'unihiker',
    status: 'available',
    model_status: 'implemented_stage_9_5',
    template_id: 'unihiker_photo_album_v1',
    description: '行空板 K10 相册确定性产品分支；已确认的相册 stage 9-5 CadQuery 模型，固定使用行空板 K10 和行空板聚合物锂电池；硬件实体和细节安装结构后续补充。',
    hardware: [
      {
        hardware_id: 'unihiker_k10',
        name: '行空板K10',
        role: 'display_controller',
        hardware_system: 'unihiker',
        function: '照片显示、触控交互和相册主控。',
        why_needed: '相册内置产品固定使用 K10 的屏幕作为照片显示和交互界面。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_polymer_lipo_battery',
        name: '行空板聚合物锂电池',
        role: 'battery',
        hardware_system: 'unihiker',
        function: '为相册提供便携供电。',
        why_needed: '相册需要一块内置电池；行空板体系优先使用体系专属聚合物锂电池。',
        profile_status: 'builtin',
      },
    ],
  },
  light_effect_cup: {
    id: 'light_effect_cup',
    name: '光效水杯',
    product_name: '行空板光效水杯',
    hardware_system: 'unihiker',
    status: 'available',
    model_status: 'implemented_template_case',
    template_id: UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID,
    template_case: true,
    design_mode: 'template_case',
    model_contract: 'template_parts_v1',
    template_case_type: 'single_printable_body_with_hardware_references',
    source_filename: `${UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID}.cq.py`,
    source_sha256: '6eccb944ea677d2cd3bdcc2002bcddaf81f9bba8dac5f91d37fc747de2ff27fa',
    aliases: [
      '光效水杯',
      '行空板光效水杯',
      'RGB水杯',
      'LED灯环水杯',
      '灯光水杯',
    ],
    description: '来自批量小模型案例的行空板光效水杯模板，保留案例中的杯体、把手和三件硬件参考摆放。',
    functions: [
      '水杯主体和把手',
      'RGB 灯环光效展示',
      '行空板 K10 控制',
      '聚合物锂电池供电',
    ],
    hardware: [
      {
        hardware_id: 'unihiker_k10',
        name: '行空板K10',
        role: 'controller',
        hardware_system: 'unihiker',
        function: '控制 RGB 灯环并提供交互能力。',
        why_needed: '原始光效水杯案例固定使用行空板 K10 作为主控。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_polymer_lipo_battery',
        name: '行空板聚合物锂电池',
        role: 'battery',
        hardware_system: 'unihiker',
        function: '为水杯中的 K10 和灯环提供便携供电。',
        why_needed: '原始光效水杯案例固定包含行空板聚合物锂电池。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_rgb12_led_ring',
        name: 'RGB12灯珠灯环',
        role: 'rgb_led_ring',
        hardware_system: 'unihiker',
        function: '在杯体正面展示 RGB 光效。',
        why_needed: '原始光效水杯案例固定使用 RGB12 灯珠灯环作为发光部件。',
        profile_status: 'builtin',
      },
    ],
  },
  handheld_fan: {
    id: 'handheld_fan',
    name: '手持小风扇',
    product_name: '行空板手持小风扇',
    hardware_system: 'unihiker',
    status: 'available',
    model_status: 'implemented_template_case',
    template_id: UNIHIKER_HANDHELD_FAN_TEMPLATE_ID,
    template_case: true,
    design_mode: 'template_case',
    model_contract: 'template_parts_v1',
    template_case_type: 'single_printable_body_with_hardware_references',
    source_filename: `${UNIHIKER_HANDHELD_FAN_TEMPLATE_ID}.cq.py`,
    source_sha256: '29a323d62f667c7a47d47cc3354a1731652a0a7a841729ac002093f4adccc248',
    aliases: [
      '手持小风扇',
      '手持风扇',
      '便携小风扇',
      '行空板小风扇',
      '行空板手持风扇',
    ],
    description: '来自批量小模型案例的行空板手持小风扇模板，保留手柄主体、顶部安装孔和三件硬件参考摆放。',
    functions: [
      '手持风扇主体',
      '直流电机风扇送风',
      '行空板 K10 控制',
      '聚合物锂电池供电',
    ],
    hardware: [
      {
        hardware_id: 'unihiker_k10',
        name: '行空板K10',
        role: 'controller',
        hardware_system: 'unihiker',
        function: '控制风扇并提供交互能力。',
        why_needed: '原始手持小风扇案例固定使用行空板 K10 作为主控。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_polymer_lipo_battery',
        name: '行空板聚合物锂电池',
        role: 'battery',
        hardware_system: 'unihiker',
        function: '为 K10 和直流电机风扇提供便携供电。',
        why_needed: '原始手持小风扇案例固定包含行空板聚合物锂电池。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_dc_motor_fan',
        name: '直流电机风扇',
        role: 'fan',
        hardware_system: 'unihiker',
        function: '提供送风功能。',
        why_needed: '原始手持小风扇案例固定使用直流电机风扇作为执行器。',
        profile_status: 'builtin',
      },
    ],
  },
  mpython_board_enclosure: {
    id: 'mpython_board_enclosure',
    name: '掌控板外壳',
    product_name: '掌控板外壳',
    hardware_system: 'mpython',
    status: 'available',
    model_status: 'implemented_template_case',
    template_id: MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID,
    template_case: true,
    design_mode: 'template_case',
    model_contract: 'template_parts_v1',
    template_case_type: 'multi_printable_enclosure',
    source_filename: `${MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID}.cq.py`,
    source_sha256: 'f30e5ebc66f27ab8259c7ce78c29613386877b0552753914f52fd2d46c9e35a4',
    aliases: [
      '掌控板外壳',
      '掌控板保护壳',
      '掌控板3.0外壳',
      '掌控板盒体',
      'mPython外壳',
    ],
    description: '来自批量小模型案例的掌控板 3.0 外壳模板，包含可独立导出的底壳和上盖。',
    functions: [
      '掌控板 3.0 保护',
      '底壳固定结构',
      '独立上盖',
      '接口和交互区域避让',
    ],
    hardware: [
      {
        hardware_id: 'mpython_board_3_0',
        name: '掌控板3.0',
        role: 'controller',
        hardware_system: 'mpython',
        function: '作为外壳适配和固定的目标主控。',
        why_needed: '原始掌控板外壳案例的全部尺寸和固定结构均针对掌控板 3.0。',
        profile_status: 'builtin',
      },
    ],
  },
  auto_open_lid_box: {
    id: 'auto_open_lid_box',
    name: '自动感应开盖智能盒子',
    product_name: '行空板自动感应开盖智能盒子',
    hardware_system: 'unihiker',
    status: 'available',
    model_status: 'implemented_template_case',
    template_id: UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID,
    template_case: true,
    design_mode: 'template_case',
    model_contract: 'template_parts_v1',
    template_case_type: 'multi_printable_hinged_enclosure_with_hardware_references',
    source_filename: `${UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID}.cq.py`,
    source_sha256: '8608f82b54577cea5837cb34f8651b6525dfb8883e09b1985f84e6db7544312f',
    aliases: [
      '行空板自动感应开盖智能盒子',
      '行空板自动开盖盒',
      '自动感应开盖智能盒',
      '自动开盖智能盒子',
      '超声波感应开盖盒',
    ],
    description: '来自批量小模型案例的行空板自动感应开盖智能盒子模板，包含底壳、铰链上盖及固定硬件参考布局。',
    functions: [
      '超声波距离感应',
      '舵机驱动开盖',
      'K10 主控和 IO 扩展',
      '外置铰链上盖',
    ],
    hardware: [
      {
        hardware_id: 'unihiker_k10',
        name: '行空板K10',
        role: 'controller',
        hardware_system: 'unihiker',
        function: '处理距离检测并控制开盖动作。',
        why_needed: '原始自动开盖盒案例固定使用行空板 K10 作为主控。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_k10_io_expansion_board',
        name: 'micro:bit掌控IO扩展板子',
        role: 'controller_expansion',
        hardware_system: 'unihiker',
        function: '连接 K10、舵机和超声波传感器。',
        why_needed: '原始自动开盖盒案例固定使用 K10 IO 扩展板连接执行器和传感器。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_servo',
        name: '舵机',
        role: 'servo',
        hardware_system: 'unihiker',
        function: '驱动上盖开启和关闭。',
        why_needed: '原始自动开盖盒案例固定使用舵机作为开盖执行器。',
        profile_status: 'builtin',
      },
      {
        hardware_id: 'unihiker_ultrasonic_distance_sensor',
        name: '超声波测距传感器',
        role: 'distance_sensor',
        hardware_system: 'unihiker',
        function: '检测接近目标并触发开盖。',
        why_needed: '原始自动开盖盒案例固定使用超声波测距传感器作为触发输入。',
        profile_status: 'builtin',
      },
    ],
  },
  xiao_smart_pendant: {
    id: 'xiao_smart_pendant',
    name: '智能项链',
    product_name: 'XIAO智能项链',
    hardware_system: 'xiao',
    status: 'available',
    model_status: 'implemented',
    template_id: 'xiao_smart_pendant_v1',
    description: 'XIAO smart pendant deterministic template with camera, microphone, LED ring, and compact battery.',
    hardware: [
      {
        hardware_id: 'xiao_esp32s3_sense',
        name: 'XIAO ESP32S3 Sense camera and microphone controller',
        role: 'camera_microphone_controller',
        hardware_system: 'xiao',
        function: 'Main control, camera capture, and microphone voice input.',
        why_needed: 'The smart pendant needs one compact XIAO controller that already includes the camera and microphone.',
        profile_status: 'assumed_future_profile',
      },
      {
        hardware_id: 'xiao_rgb_led_ring',
        name: 'XIAO RGB LED ring',
        role: 'rgb_led_ring',
        hardware_system: 'xiao',
        function: 'Front status and assistant feedback lighting.',
        why_needed: 'The reference pendant uses a front light ring around the camera.',
        profile_status: 'assumed_future_profile',
      },
      {
        hardware_id: 'compact_lipo_battery',
        name: '方形锂电池',
        role: 'battery',
        hardware_system: 'common',
        function: 'Portable power supply for the pendant.',
        why_needed: 'A wearable pendant needs a compact internal battery.',
        profile_status: 'builtin',
      },
    ],
  },
  xiao_plant_caregiver: {
    id: 'xiao_plant_caregiver',
    name: '植物看护仪',
    product_name: 'XIAO植物看护仪',
    hardware_system: 'xiao',
    status: 'placeholder',
    description: 'XIAO 版本植物看护仪占位符，后续补确定性模型。',
    hardware: [],
  },
  mpython_plant_caregiver: {
    id: 'mpython_plant_caregiver',
    name: '植物看护仪',
    product_name: '掌控板植物看护仪',
    hardware_system: 'mpython',
    status: 'placeholder',
    description: '掌控板版本植物看护仪占位符，后续补确定性模型。',
    hardware: [],
  },
});

const TEMPLATE_PROJECT_CATALOG = Object.freeze([
  {
    id: 'unihiker_smart_watering_system',
    product_id: 'unihiker_plant_caregiver',
    name: '行空板植物养护系统',
    summary: '监测土壤湿度并控制水泵完成植物养护。',
    prompt: '做一个行空板植物养护系统',
    thumbnail_url: '/assets/templates/unihiker-plant-care-system.png',
    preview_hardware_ids: [
      'unihiker_k10',
      'unihiker_soil_moisture_sensor',
      'unihiker_dc_water_pump',
    ],
  },
  {
    id: 'unihiker_photo_album',
    product_id: 'unihiker_photo_album',
    name: '行空板相册',
    summary: '使用行空板 K10 和专用聚合物锂电池组成电子相册。',
    prompt: '做一个行空板电子相册产品',
    thumbnail_url: '/assets/templates/unihiker-photo-album.png',
    preview_hardware_ids: [
      'unihiker_k10',
      'unihiker_polymer_lipo_battery',
    ],
  },
  {
    id: UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID,
    product_id: 'light_effect_cup',
    name: '光效水杯',
    summary: '使用行空板 K10、聚合物锂电池和 RGB12 灯环组成带把手的光效水杯案例。',
    prompt: '使用模板生成一个行空板光效水杯',
    thumbnail_url: '/assets/templates/unihiker-light-effect-cup.png',
    preview_hardware_ids: [
      'unihiker_k10',
      'unihiker_polymer_lipo_battery',
      'unihiker_rgb12_led_ring',
    ],
  },
  {
    id: UNIHIKER_HANDHELD_FAN_TEMPLATE_ID,
    product_id: 'handheld_fan',
    name: '手持小风扇',
    summary: '使用行空板 K10、聚合物锂电池和直流电机风扇组成手持风扇案例。',
    prompt: '使用模板生成一个行空板手持小风扇',
    thumbnail_url: '/assets/templates/unihiker-handheld-fan.png',
    preview_hardware_ids: [
      'unihiker_k10',
      'unihiker_polymer_lipo_battery',
      'unihiker_dc_motor_fan',
    ],
  },
  {
    id: MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID,
    product_id: 'mpython_board_enclosure',
    name: '掌控板外壳',
    summary: '为掌控板 3.0 提供带固定结构的底壳和独立上盖。',
    prompt: '使用模板生成一个掌控板3.0外壳',
    thumbnail_url: '/assets/templates/mpython-board-enclosure.png',
    preview_hardware_ids: [
      'mpython_board_3_0',
    ],
  },
  {
    id: UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID,
    product_id: 'auto_open_lid_box',
    name: '自动感应开盖智能盒子',
    summary: '使用行空板 K10、IO 扩展板、舵机和超声波传感器组成自动开盖智能盒。',
    prompt: '使用模板生成一个行空板自动感应开盖智能盒子',
    thumbnail_url: '/assets/templates/unihiker-auto-open-lid-box.png',
    preview_hardware_ids: [
      'unihiker_k10',
      'unihiker_k10_io_expansion_board',
      'unihiker_servo',
      'unihiker_ultrasonic_distance_sensor',
    ],
  },
]);

export function listDeterministicTemplateProjects() {
  return TEMPLATE_PROJECT_CATALOG.map((entry) => {
    const product = PRODUCT_DEFINITIONS[entry.product_id];
    return {
      ...entry,
      template_id: product.template_id,
      hardware_system: product.hardware_system,
      status: product.status,
      template_case: product.template_case === true,
      design_mode: product.design_mode || 'deterministic_template',
      model_contract: product.model_contract || '',
      source_filename: product.source_filename || '',
      source_sha256: product.source_sha256 || '',
      aliases: [...(product.aliases || [])],
      hardware_ids: product.hardware.map((item) => item.hardware_id),
      preview_hardware_ids: [...entry.preview_hardware_ids],
    };
  });
}

export function detectDeterministicProduct(body = {}) {
  const text = deterministicDetectionText(body);
  if (!text) return null;

  const selectedIds = normalizeStringArray(body.selectedHardwareIds || body.selected_hardware_ids);
  const selectedText = selectedIds.join(' ');
  const combined = `${text} ${selectedText}`;

  const templateCaseDetection = detectBatchModelTemplateCase(text, combined);
  if (templateCaseDetection) return templateCaseDetection;

  if (PLANT_CARE_PATTERNS.some((pattern) => pattern.test(text))) {
  if (XIAO_PATTERNS.some((pattern) => pattern.test(combined))) {
    return buildDetection(PRODUCT_DEFINITIONS.xiao_plant_caregiver, '用户需求命中植物看护类内置产品，并指定 XIAO 体系。');
  }
  if (MPYTHON_PATTERNS.some((pattern) => pattern.test(combined))) {
    return buildDetection(PRODUCT_DEFINITIONS.mpython_plant_caregiver, '用户需求命中植物看护类内置产品，并指定掌控板体系。');
  }
  if (UNIHIKER_PATTERNS.some((pattern) => pattern.test(combined))) {
    return buildDetection(PRODUCT_DEFINITIONS.unihiker_plant_caregiver, '用户需求命中植物看护类内置产品，并指定行空板体系。');
  }
  return buildDetection(PRODUCT_DEFINITIONS.unihiker_plant_caregiver, '用户需求命中植物看护类内置产品，未指定硬件体系，默认使用行空板版本。');
  }

  if (PHOTO_ALBUM_PATTERNS.some((pattern) => pattern.test(text))) {
    const explicitlyUnihiker = UNIHIKER_PATTERNS.some((pattern) => pattern.test(combined));
    const explicitlyOtherSystem = XIAO_PATTERNS.some((pattern) => pattern.test(combined))
      || MPYTHON_PATTERNS.some((pattern) => pattern.test(combined));
    if (explicitlyUnihiker || !explicitlyOtherSystem) {
      return buildDetection(PRODUCT_DEFINITIONS.unihiker_photo_album, '用户需求命中相册/数字相框类内置产品，默认使用行空板 K10 版本。');
    }
  }

  if (SMART_PENDANT_PATTERNS.some((pattern) => pattern.test(text))) {
    const explicitlyXiao = XIAO_PATTERNS.some((pattern) => pattern.test(combined));
    const explicitlyOtherSystem = MPYTHON_PATTERNS.some((pattern) => pattern.test(combined))
      || UNIHIKER_PATTERNS.some((pattern) => pattern.test(combined));
    if (explicitlyXiao || !explicitlyOtherSystem) {
      return buildDetection(PRODUCT_DEFINITIONS.xiao_smart_pendant, 'User request matched the XIAO smart pendant deterministic product template.');
    }
  }

  return null;
}

function detectBatchModelTemplateCase(text, combined = text) {
  const candidates = [
    {
      patterns: LIGHT_EFFECT_CUP_PATTERNS,
      product: PRODUCT_DEFINITIONS.light_effect_cup,
      reason: '用户需求明确命中批量小模型中的光效水杯模板案例。',
    },
    {
      patterns: HANDHELD_FAN_PATTERNS,
      product: PRODUCT_DEFINITIONS.handheld_fan,
      reason: '用户需求明确命中批量小模型中的手持小风扇模板案例。',
    },
    {
      patterns: MPYTHON_BOARD_ENCLOSURE_PATTERNS,
      product: PRODUCT_DEFINITIONS.mpython_board_enclosure,
      reason: '用户需求明确命中批量小模型中的掌控板外壳模板案例。',
    },
    {
      patterns: AUTO_OPEN_LID_BOX_PATTERNS,
      product: PRODUCT_DEFINITIONS.auto_open_lid_box,
      reason: '用户需求明确命中批量小模型中的自动感应开盖智能盒子模板案例。',
    },
  ];

  const explicitlyUnihiker = UNIHIKER_PATTERNS.some((pattern) => pattern.test(combined))
    || /\bunihiker_/i.test(combined);
  const explicitlyXiao = XIAO_PATTERNS.some((pattern) => pattern.test(combined))
    || /\bxiao_/i.test(combined);
  const explicitlyMpython = MPYTHON_PATTERNS.some((pattern) => pattern.test(combined))
    || /\bmpython_/i.test(combined);
  const matched = candidates.find((candidate) => {
    if (!candidate.patterns.some((pattern) => pattern.test(text))) return false;
    if (candidate.product.hardware_system === 'unihiker') {
      return !explicitlyXiao && !explicitlyMpython;
    }
    if (candidate.product.hardware_system === 'mpython') {
      return !explicitlyUnihiker && !explicitlyXiao;
    }
    if (candidate.product.hardware_system === 'xiao') {
      return !explicitlyUnihiker && !explicitlyMpython;
    }
    return true;
  });
  return matched ? buildDetection(matched.product, matched.reason) : null;
}

export function buildDeterministicProductResponse(detection, body = {}) {
  if (!detection?.product) return null;
  const product = detection.product;
  if (product.status === 'placeholder') {
    return buildPlaceholderResponse(product, detection, body);
  }
  return buildAvailableProductResponse(product, detection, body);
}

export function maybeBuildDeterministicProductResponse(body = {}) {
  const detection = detectDeterministicProduct(body);
  return detection ? buildDeterministicProductResponse(detection, body) : null;
}

export function deterministicDetectionText(body = {}) {
  return [
    body.prompt,
    body.latestUserMessage,
    body.latest_user_message,
    ...(Array.isArray(body.userAnswers) ? body.userAnswers : []),
    ...(Array.isArray(body.user_answers) ? body.user_answers : []),
    body.intent?.product_name,
    ...(Array.isArray(body.intent?.functions) ? body.intent.functions : []),
  ].map(normalizeString).filter(Boolean).join('\n');
}

function buildAvailableProductResponse(product, detection, body) {
  const bom = product.hardware.map((item) => ({
    hardware_id: item.hardware_id,
    name: item.name,
    role: item.role,
    hardware_system: item.hardware_system,
    quantity: 1,
    required_or_optional: 'required',
    function: item.function,
    why_needed: item.why_needed,
    profile_status: item.profile_status,
    ...(item.variant_status ? { variant_status: item.variant_status } : {}),
    ...(item.variant_note ? { variant_note: item.variant_note } : {}),
    mounting_intent: {
      preferred_surface: product.template_case === true
        ? 'template_defined'
        : defaultSurfaceForRole(item.role),
      opening_count: product.template_case === true ? 0 : openingCountForRole(item.role),
    },
  }));
  const isTemplateCase = product.template_case === true;
  const isPhotoAlbum = product.id === 'unihiker_photo_album';
  const partialIntent = isTemplateCase
    ? buildTemplateCaseIntent(product, body)
    : isPhotoAlbum
      ? buildPhotoAlbumIntent(product, body)
      : buildPlantCareIntent(product, body);
  const pendingContent = isTemplateCase
    ? buildTemplateCasePendingContent(product)
    : isPhotoAlbum
      ? buildPhotoAlbumPendingContent(product)
      : buildPlantCarePendingContent(product);
  const response = {
    status: 'deterministic_product',
    title: `${product.product_name} 内置模型`,
    message: pendingContent.message,
    deterministic_product: summarizeProduct(product, detection),
    partial_intent: partialIntent,
    partial_bom: bom,
    bom,
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    next_step: pendingContent.next_step,
    assumptions: pendingContent.assumptions,
    warnings: pendingContent.warnings,
    questions: pendingContent.questions,
    blocking_reason: isTemplateCase
      ? 'deterministic_template_case_builder_unavailable'
      : 'deterministic_product_model_pending',
    source: 'deterministic_product',
    intent_analysis: {
      source: 'deterministic_product',
      status: 'ok',
      model_status: 'skipped',
      reason: detection.reason,
      confidence: detection.confidence,
      conversation_route: body.conversation_route || body.conversationRoute || null,
      revision_intent: body.revision_intent || body.revisionIntent || null,
    },
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
  };
  response.generation_trace = buildDeterministicProductTrace(response);
  return response;
}

function buildPlaceholderResponse(product, detection, body) {
  const response = {
    status: 'deterministic_product',
    title: `${product.product_name} 内置模型占位`,
    message: `已命中${product.product_name}内置确定性产品占位符。该版本后续会补专用硬件组合和模型；本次命中后按内置分支短路，不回落到通用流程。`,
    deterministic_product: summarizeProduct(product, detection),
    partial_intent: buildPlaceholderIntent(product, body),
    partial_bom: [],
    bom: [],
    selected_hardware_ids: [],
    next_step: '后续补齐该硬件体系的植物看护仪确定性模型。',
    assumptions: [
      '占位符用于验证工作流分支，不生成通用模型。',
    ],
    warnings: [
      {
        id: 'deterministic_product_placeholder',
        status: 'pending',
        message: `${product.product_name}确定性模型尚未实现。`,
      },
    ],
    questions: [
      '请后续补齐该版本的硬件组合和专用建模规则。',
    ],
    blocking_reason: 'deterministic_product_placeholder',
    source: 'deterministic_product',
    intent_analysis: {
      source: 'deterministic_product',
      status: 'ok',
      model_status: 'skipped',
      reason: detection.reason,
      confidence: detection.confidence,
      conversation_route: body.conversation_route || body.conversationRoute || null,
      revision_intent: body.revision_intent || body.revisionIntent || null,
    },
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
  };
  response.generation_trace = buildDeterministicProductTrace(response);
  return response;
}

function buildPlantCarePendingContent() {
  return {
    message: '已命中内置确定性产品「植物看护仪」。本轮将直接使用固定产品意图和固定硬件组合，不再进入通用需求分析、通用 BOM 推断和通用布局链路。',
    next_step: '硬件 profile 已补齐，后续实现植物看护仪专用 CAD 结构、线束和水管模型。',
    assumptions: [
      'SCI采集模块、直流水泵、继电器模块 profile 均已补齐。',
      '本次只完成内置产品分支和工作流短路，不生成最终植物看护仪 CAD。',
    ],
    warnings: [
      {
        id: 'deterministic_product_model_pending',
        status: 'pending',
        message: '植物看护仪专用 CAD 结构尚未实现；当前响应用于固定工作流分支和后续模型入口。',
      },
    ],
    questions: [
      '后续补齐三个硬件 profile 后，可继续实现该内置产品的专用盒体、线束、水管和固定结构。',
    ],
  };
}

function buildPhotoAlbumPendingContent() {
  return {
    message: '已检测到行空板相册类设计，当前使用已确认的 stage 9-5 相册模型生成结构。',
    next_step: '后续继续补充 K10 安装姿态、开孔、支架或盒体规则，并确定行空板聚合物锂电池在相册中的安装位置。',
    assumptions: [
      '相册固定使用行空板 K10 作为照片显示和主控。',
      '相册固定 BOM 使用行空板聚合物锂电池。',
      '已确认的 stage 9-5 相册模型作为当前结构基准；K10 实体、电池和更多安装细节后续补充。',
    ],
    warnings: [
      {
        id: 'photo_album_stage_8_scope',
        status: 'info',
        message: '行空板相册 stage 9-5 CAD 结构已确认；K10 实体、电池和更多安装细节等待后续自然语言补充。',
      },
    ],
    questions: [
      '后续请补充相册外观结构、K10 露出/安装方式、支架或盒体形式，以及行空板聚合物锂电池的安装位置。',
    ],
  };
}

function buildTemplateCasePendingContent(product) {
  return {
    message: `已命中模板案例「${product.product_name}」，固定 BOM 和模型源码均由服务器模板定义提供。`,
    next_step: '当前调用入口未连接模板案例构建器，请通过完整生成流程创建项目副本和导出文件。',
    assumptions: [
      '模板严格沿用原始案例的几何、BOM 和硬件参考摆放，不进入通用盒体布局推断。',
      '模板源码将在项目生成时复制到当前项目目录，后续修改只作用于项目副本。',
    ],
    warnings: [
      {
        id: 'deterministic_template_case_builder_unavailable',
        status: 'pending',
        message: '已识别模板案例，但当前调用入口没有可用的模板案例构建器。',
      },
    ],
    questions: [],
  };
}

function buildPlantCareIntent(product, body) {
  return {
    schema_version: '1.0',
    product_name: product.product_name,
    deterministic_product_id: product.id,
    functions: [
      '主控计算和交互显示',
      '土壤湿度检测',
      '水泵电源通断控制',
      '自动供水养护',
      '植物养护提醒',
    ],
    required_hardware_roles: product.hardware.map((item) => ({
      role: item.role,
      category: categoryForRole(item.role),
      function: item.function,
      label: item.name,
      why_needed: item.why_needed,
    })),
    selected_hardware_ids: product.hardware.map((item) => item.hardware_id),
    mounting_intents: [
      {
        hardware_id: 'unihiker_k10',
        target_face: 'lid_outer',
        interaction_face: 'top',
        user_phrase: '行空板 K10 作为外露交互主控。',
      },
      {
        hardware_id: 'unihiker_sci_acquisition_module',
        target_face: 'lid_outer',
        interaction_face: 'top',
        user_phrase: 'SCI 采集模块作为传感器采集/预处理扩展板，默认安装在上盖外侧面。',
      },
      {
        hardware_id: 'unihiker_soil_moisture_sensor',
        target_face: 'front_inner',
        interaction_face: 'front',
        user_phrase: '土壤湿度传感器外置探针，盒体预留线束出口。',
      },
      {
        hardware_id: 'unihiker_dc_water_pump',
        target_face: 'base_floor',
        interaction_face: 'inside',
        user_phrase: '直流水泵不与盒体固定，仅默认在右侧面预留电源线通道。',
      },
      {
        hardware_id: 'unihiker_relay_module',
        target_face: 'base_floor',
        interaction_face: 'inside',
        user_phrase: '继电器模块固定在盒内用于控制水泵通断。',
      },
    ],
    enclosure_intent: {
      type: 'rectangular_box_with_lid',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'screw_lid',
      allowed_shape: 'rounded_rectangular_box',
      deterministic_model: 'plant_caregiver_v1_pending',
    },
    user_constraints: {
      raw_prompt: normalizeString(body.prompt),
      size_mm: {},
      notes: [
        '命中内置植物看护仪分支。',
        '专用模型和未来硬件 profile 接入后再生成最终 CAD。',
      ],
    },
    unknowns: [],
  };
}

function buildTemplateCaseIntent(product, body) {
  return {
    schema_version: '1.0',
    product_name: product.product_name,
    deterministic_product_id: product.id,
    template_id: product.template_id,
    design_mode: product.design_mode,
    template_case: true,
    model_contract: product.model_contract,
    source_filename: product.source_filename,
    functions: [...(product.functions || [])],
    required_hardware_roles: product.hardware.map((item) => ({
      role: item.role,
      category: categoryForRole(item.role),
      function: item.function,
      label: item.name,
      why_needed: item.why_needed,
    })),
    selected_hardware_ids: product.hardware.map((item) => item.hardware_id),
    mounting_intents: product.hardware.map((item) => ({
      hardware_id: item.hardware_id,
      target_face: 'template_defined',
      interaction_face: 'template_defined',
      user_phrase: '硬件位置严格沿用模板案例源码中的固定摆放。',
    })),
    enclosure_intent: {
      type: product.template_case_type,
      manufacturing: 'fdm_3d_printing',
      lid_strategy: product.id === 'mpython_board_enclosure'
        ? 'separate_top_cover'
        : product.id === 'auto_open_lid_box'
          ? 'external_hinge_lid'
          : 'not_applicable',
      allowed_shape: 'template_defined',
      deterministic_model: product.template_id,
      model_contract: product.model_contract,
    },
    user_constraints: {
      raw_prompt: normalizeString(body.prompt),
      size_mm: {},
      notes: [
        '命中批量小模型模板案例。',
        '固定 BOM、几何和硬件摆放均以模板源码为准。',
      ],
    },
    unknowns: [],
  };
}

function buildPhotoAlbumIntent(product, body) {
  return {
    schema_version: '1.0',
    product_name: product.product_name,
    deterministic_product_id: product.id,
    template_id: product.template_id,
    functions: [
      'K10 照片显示与触控交互',
      '相册浏览与显示控制',
      '行空板聚合物锂电池供电',
    ],
    required_hardware_roles: product.hardware.map((item) => ({
      role: item.role,
      category: categoryForRole(item.role),
      function: item.function,
      label: item.name,
      why_needed: item.why_needed,
      ...(item.variant_status ? { variant_status: item.variant_status } : {}),
      ...(item.variant_note ? { variant_note: item.variant_note } : {}),
    })),
    selected_hardware_ids: product.hardware.map((item) => item.hardware_id),
    mounting_intents: [
      {
        hardware_id: 'unihiker_k10',
        target_face: 'stage_2_slope_l_clip',
        interaction_face: 'front',
        user_phrase: 'K10 作为相册显示和主控；第二阶段已生成斜面 L 形突出卡槽，K10 实体和完整安装姿态后续补充。',
      },
      {
        hardware_id: 'unihiker_polymer_lipo_battery',
        target_face: 'stage_2_not_modeled',
        interaction_face: 'inside',
        user_phrase: '行空板聚合物锂电池作为相册便携供电；第二阶段仍不建电池安装位置和固定结构。',
      },
    ],
    enclosure_intent: {
      type: 'deterministic_photo_album_stage_9',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'not_modeled_in_stage_1',
      allowed_shape: 'flat_base_with_full_width_slope',
      deterministic_model: 'unihiker_photo_album_v1',
    },
    user_constraints: {
      raw_prompt: normalizeString(body.prompt),
      size_mm: {},
      notes: [
        '命中行空板相册内置确定性分支。',
        'stage 9-5 结构已作为确认版相册模型；硬件实体和更多安装细节后续补充。',
      ],
    },
    unknowns: [
      'K10 安装姿态和开孔',
      '行空板聚合物锂电池在相册结构中的安装位置',
    ],
  };
}

function buildPlaceholderIntent(product, body) {
  return {
    schema_version: '1.0',
    product_name: product.product_name,
    deterministic_product_id: product.id,
    functions: [
      '土壤湿度检测',
      '自动供水养护',
      '植物养护提醒',
    ],
    required_hardware_roles: [],
    selected_hardware_ids: [],
    mounting_intents: [],
    enclosure_intent: {
      type: 'rectangular_box_with_lid',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'screw_lid',
      allowed_shape: 'rounded_rectangular_box',
      deterministic_model: 'placeholder',
    },
    user_constraints: {
      raw_prompt: normalizeString(body.prompt),
      size_mm: {},
      notes: ['命中内置植物看护仪占位分支。'],
    },
    unknowns: [],
  };
}

function buildDetection(product, reason) {
  return {
    product,
    reason,
    confidence: product.status === 'available' ? 0.96 : 0.9,
    source: 'deterministic_product_detector',
  };
}

function summarizeProduct(product, detection) {
  return {
    id: product.id,
    name: product.name,
    product_name: product.product_name,
    hardware_system: product.hardware_system,
    status: product.status,
    model_status: product.model_status || (product.status === 'available' ? 'pending' : 'placeholder'),
    template_id: product.template_id || '',
    template_case: product.template_case === true,
    design_mode: product.design_mode || 'deterministic_template',
    model_contract: product.model_contract || '',
    hardware_ids: product.hardware.map((item) => item.hardware_id),
    ...(product.source_filename ? { source_filename: product.source_filename } : {}),
    ...(product.source_sha256 ? { source_sha256: product.source_sha256 } : {}),
    ...(product.aliases ? { aliases: [...product.aliases] } : {}),
    description: product.description,
    matched: true,
    source: detection.source,
    reason: detection.reason,
    confidence: detection.confidence,
  };
}

function buildDeterministicProductTrace(response) {
  return {
    stage: 'deterministic_product',
    status: 'short_circuited',
    deterministic_product: response.deterministic_product,
    intent_analysis: response.intent_analysis,
    bom: response.partial_bom,
    skipped_stages: [
      'model_intent_analysis',
      'requirement_analysis_confirmation',
      'generic_bom_selection',
      'generic_layout_solver',
      'generic_cad_generation',
    ],
  };
}

function defaultSurfaceForRole(role) {
  return {
    battery: 'base_floor',
    display_controller: 'stage_2_slope_l_clip',
    camera_microphone_controller: 'pendant_inner_front',
    rgb_led_ring: 'pendant_lid_inner',
    fan: 'template_defined',
    servo: 'template_defined',
    distance_sensor: 'template_defined',
    controller: 'lid_outer',
    controller_expansion: 'external_right',
    data_acquisition: 'lid_outer',
    soil_moisture_sensor: 'external_scene',
    water_pump: 'external_scene',
    pump_driver: 'base_floor',
  }[role] || 'base_floor';
}

function openingCountForRole(role) {
  return {
    camera_microphone_controller: 2,
    rgb_led_ring: 1,
    display_controller: 1,
    controller: 1,
    soil_moisture_sensor: 1,
    water_pump: 1,
  }[role] || 0;
}

function categoryForRole(role) {
  return {
    battery: 'power',
    display_controller: 'controller',
    camera_microphone_controller: 'controller',
    rgb_led_ring: 'indicator',
    fan: 'actuator',
    servo: 'actuator',
    distance_sensor: 'sensor',
    controller: 'controller',
    controller_expansion: 'controller_expansion',
    data_acquisition: 'sensor_expansion_board',
    soil_moisture_sensor: 'sensor',
    water_pump: 'actuator',
    pump_driver: 'power',
  }[role] || 'hardware';
}
