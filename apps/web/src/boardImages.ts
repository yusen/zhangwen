import esp32c3 from './assets/boards/esp32-c3-devkitm-1.webp';
import xiaoSense from './assets/boards/xiao-esp32s3-sense.webp';
import mpythonV2 from './assets/boards/mpython-v2.webp';

/** Display assets only. Controller identity and capabilities still come from Hardware Skill. */
export const boardImages: Partial<Record<string, {src: string; alt: string; caption?: string}>> = {
  hw_esp32_generic_c3: {src: esp32c3, alt: 'Espressif ESP32-C3-DevKitM-1 产品图（通用 C3 开发板示例）', caption: 'ESP32-C3 开发板示例'},
  hw_seeed_xiao_esp32s3_sense: {src: xiaoSense, alt: 'Seeed Studio XIAO ESP32S3 Sense 产品图，含摄像头扩展板'},
  hw_labplus_mpython_v2: {src: mpythonV2, alt: '掌控板 2.0 官方正反面产品示意图'},
};
