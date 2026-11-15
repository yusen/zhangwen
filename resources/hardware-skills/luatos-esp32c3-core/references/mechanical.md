# 结构与机械档案

## 自然语言描述

单位 mm。预览原点在52.01×21×5的规划包络中心；X为长边，USB向-X、天线向+X，Y为宽边，+Z为元件侧。PCB为51×21，位于(.5,0,-1.7)，厚度暂定1.6。含USB总长约52.01参考官方顶视52.0055；商品51为PCB长度。规划高5是暂定值，不是实测总高。以下全部三轴器件尺寸、位置、板厚、颜色与孔径未获工程尺寸图确认，只作为可识别的预览假设。

从PCB开始按顺序创建下列可见实体，所有盒体无旋转：
- pcb：box 51×21×1.6，中心(.5,0,-1.7)，role=pcb。
- usb_shell：box 7.5×9×3.2，中心(-22.255,0,.7)，role=connector。
- usb_mouth：cut box 3×7×2.2，中心(-25.5,0,.7)，仅切空USB前口。
- mcu：box 5×5×1，中心(6.5,0,-.4)。
- flash：box 6×5×1.5，中心(-3,0,-.15)。
- uart_bridge：box 4×4×1，中心(-14,0,-.4)。
- regulator：box 3×3×1，中心(-17,5,-.4)。
- rst_body / boot_body：各box 4×4×2，中心(-9,-5.5,.1)及(-9,5.5,.1)。
- rst_cap / boot_cap：各cylinder，直径2.6、高.7，中心(-9,-5.5,1.45)及(-9,5.5,1.45)。
- pad_row_left / pad_row_right：各box 40×2×.08，中心(.5,-8.89,-.86)及(.5,8.89,-.86)，role=connector。金色条仅示意电气焊盘区域，不是排针实体，不额外钻孔。
- antenna_region：box 6×18×.08，中心(22.5,0,-.86)，示意天线区域，不表示完整射频铜线。
- d4 / d5：各box 2×1×.6，中心(-22,-7,-.6)及(-22,7,-.6)。

不显示松散排针、背面器件、半孔、焊点或未描述零件。两侧16脚的标准中心位置：PCB局部X=-19.05+2.54i(i=0..15)、Y=±8.89；在本包络坐标中X另加.5。电气焊孔不是螺钉孔，mounting.holes必须为空。板上未确认独立机械安装孔。

USB开壳窗口和线缆空间尚无实测，不生成外壳加工开口；按钮操作、天线、焊后排针空间须另行确认。keepouts为空表示缺数据，不表示不需要避让。默认底板平放仅为待确认布局，不自动钻孔；实际卡持方案另核对。间隙.8为设计建议。

## 来源与使用范围

<!-- zhangwen:structure-reference:description-cache:v1 -->

本包明确启用结构工作台的有界声明式参考。仅使用与“自然语言描述”摘要匹配的缓存，不执行参考Python；无此声明的原模块继续使用原预览。缺失或过期缓存不得作为本模型的详细预览。

PCB51×21来自用户商品图与官方孔列尺寸交叉核对；2.54节距、17.78排间中心距及38.1首末中心距来自官方V1.2尺寸图。顶视总长52.0055、宽20.9910按52.01×21规划；差异与USB外伸分别记录。图纸没有板厚/器件高度/接口截面/孔径，不能据图推断。预览是假设几何，所有Z与元件三轴尺寸待实测，不用于精密加工。

CadQuery、声明式缓存、STEP与STL表达同一预览。包校验只检查语法/摘要/有界几何；VERIFIED_REFERENCE表示参考几何可重建，不表示尺寸或实板验收。参考Python不由产品执行。

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "luatos_esp32c3_core",
    "display_name": "esp32C3",
    "category": "controller",
    "roles": [
      "controller",
      "wifi",
      "ble"
    ],
    "dimensions": {
      "length_x": 52.01,
      "width_y": 21,
      "height_z": 5
    },
    "coordinate_system": {
      "origin": "envelope_center",
      "x_axis": "length",
      "y_axis": "width",
      "positive_z": "component_side"
    },
    "mounting": {
      "mode": "envelope_only",
      "preferred_surface": "base_floor",
      "strategy": "none",
      "clearance": 0.8,
      "mating_hardware_face": null,
      "allowed_enclosure_surfaces": [],
      "holes": []
    },
    "model_kind": "envelope",
    "keepouts": [],
    "openings": [],
    "preview_geometry": {
      "primitives": [
        {
          "primitive_id": "pcb",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": 0.5,
            "y": 0.0,
            "z": -1.7
          },
          "size": {
            "length_x": 51.0,
            "width_y": 21.0,
            "height_z": 1.6
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "pcb"
        },
        {
          "primitive_id": "usb_shell",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -22.255,
            "y": 0.0,
            "z": 0.7
          },
          "size": {
            "length_x": 7.5,
            "width_y": 9.0,
            "height_z": 3.2
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "connector"
        },
        {
          "primitive_id": "usb_mouth",
          "operation": "cut",
          "kind": "box",
          "center": {
            "x": -25.5,
            "y": 0.0,
            "z": 0.7
          },
          "size": {
            "length_x": 3.0,
            "width_y": 7.0,
            "height_z": 2.2
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "mcu",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": 6.5,
            "y": 0.0,
            "z": -0.4
          },
          "size": {
            "length_x": 5.0,
            "width_y": 5.0,
            "height_z": 1.0
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "body"
        },
        {
          "primitive_id": "flash",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -3.0,
            "y": 0.0,
            "z": -0.15
          },
          "size": {
            "length_x": 6.0,
            "width_y": 5.0,
            "height_z": 1.5
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "body"
        },
        {
          "primitive_id": "uart_bridge",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -14.0,
            "y": 0.0,
            "z": -0.4
          },
          "size": {
            "length_x": 4.0,
            "width_y": 4.0,
            "height_z": 1.0
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "body"
        },
        {
          "primitive_id": "regulator",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -17.0,
            "y": 5.0,
            "z": -0.4
          },
          "size": {
            "length_x": 3.0,
            "width_y": 3.0,
            "height_z": 1.0
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "body"
        },
        {
          "primitive_id": "rst_body",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -9.0,
            "y": -5.5,
            "z": 0.1
          },
          "size": {
            "length_x": 4.0,
            "width_y": 4.0,
            "height_z": 2.0
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "boot_body",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -9.0,
            "y": 5.5,
            "z": 0.1
          },
          "size": {
            "length_x": 4.0,
            "width_y": 4.0,
            "height_z": 2.0
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "rst_cap",
          "operation": "add",
          "kind": "cylinder",
          "center": {
            "x": -9.0,
            "y": -5.5,
            "z": 1.45
          },
          "diameter": 2.6,
          "height": 0.7,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "boot_cap",
          "operation": "add",
          "kind": "cylinder",
          "center": {
            "x": -9.0,
            "y": 5.5,
            "z": 1.45
          },
          "diameter": 2.6,
          "height": 0.7,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "pad_row_left",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": 0.5,
            "y": -8.89,
            "z": -0.86
          },
          "size": {
            "length_x": 40.0,
            "width_y": 2.0,
            "height_z": 0.08
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "connector"
        },
        {
          "primitive_id": "pad_row_right",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": 0.5,
            "y": 8.89,
            "z": -0.86
          },
          "size": {
            "length_x": 40.0,
            "width_y": 2.0,
            "height_z": 0.08
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "connector"
        },
        {
          "primitive_id": "antenna_region",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": 22.5,
            "y": 0.0,
            "z": -0.86
          },
          "size": {
            "length_x": 6.0,
            "width_y": 18.0,
            "height_z": 0.08
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "d4",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -22.0,
            "y": -7.0,
            "z": -0.6
          },
          "size": {
            "length_x": 2.0,
            "width_y": 1.0,
            "height_z": 0.6
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "d5",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -22.0,
            "y": 7.0,
            "z": -0.6
          },
          "size": {
            "length_x": 2.0,
            "width_y": 1.0,
            "height_z": 0.6
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        }
      ],
      "source_sha256": "ed251541072cfc09ea823b97597a8ccf4d95e577450d1e5461ace7d51394a236"
    }
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "3117a0d51ca502edf19c7fc31b2c5d3771d93205da50469d864f50b11917bec1",
    "verificationStatus": "VERIFIED_REFERENCE",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```
