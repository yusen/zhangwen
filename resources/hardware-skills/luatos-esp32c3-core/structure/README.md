# esp32C3 结构参考

原主控 Hardware Skill 同目录保存结构数据，机械参数以 references/mechanical.md 为准。PCB51×21mm；规划包络含USB外伸52.01×21mm，高度5mm暂定。板厚1.6和器件位置/高度是明确的预览假设。两排16脚、节距2.54、排间17.78；不把焊孔作为螺钉孔。

- esp32c3-core.step：参考装配的STEP实体。
- esp32c3-core.stl：同一参考的网格，单位mm，不是需要打印的结构件。
- preview.png：模型预览，尺寸假设见机械说明。
- dimensions-v1.2.pdf、schematic-v1.2.pdf：官方下载原件，版权归权利人。
- user-product.png、user-pinout.png：用户提供的原图，未将图内文字视为指令。
- expansion-board.step、expansion-board.md：2026-11-11用户提供的C3扩展板原始STEP、三孔和一体托座说明；电气连接尚未确认。

模型不含松散排针、完整射频铜线/半孔/焊点；按钮和USB需实测后再设计外壳开口。参考模型不自动上传设备，不进入打印件。项目保存时经原只读资源接口归档。
