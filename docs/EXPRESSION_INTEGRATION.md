# 表情系统集成说明

独立项目 `Multi-character Hardware Expression System` 维护 Bluebot 和小Q的表情画面。
产品仓在 `vendor/hardware_expression_system/` 保存一份固定版本。该目录不含产品密钥。

小Q当前使用的 `cute` 和 `neon` 代码已迁入 `characters/xiaoq_visuals.py`。
内容包括眼嘴参数、配色、渲染器、氛围层和视觉特效。
产品主程序仍负责语音、云台、业务流程和小Q状态调度。
旧文件 `cute_face.py` 不是当前产品中 `cute` 风格的代码来源。

## 本地命令

向现有地址 `ws://127.0.0.1:8766` 发送 JSON：

```json
{"type":"character_set","name":"bluebot"}
{"type":"mobilework_status","status":"HUMAN_INTERVENTION"}
{"type":"character_set","name":"xiaoq"}
```

系统默认显示小Q。状态命令不会自动切换角色。启用 Bluebot 后，它的表情画面优先于旧的 MobileWork 聊天和 GIF 画面。
如果 Bluebot 绘制失败，系统关闭 Bluebot，并在同一帧恢复旧画面。
小Q的 `cute` 和 `neon` 人格切换保持不变。

状态命令只接受 `MobileWorkStatus` 定义的 16 个值。无效状态不会改变当前表情。
产品业务代码必须在状态变化时发送命令。本次接入不从聊天文字或语音状态推断业务状态。

## 修改边界

不要直接修改 `vendor/` 中的眼睛、嘴巴、颜色或动效代码。
先在独立项目修改，再完成测试和画面复核。之后按固定版本更新产品仓，并单独提交审核。
集成同事只需使用上述命令和产品侧适配器。

部署前运行 `python tools/check_expression_snapshot.py`。CI 也执行同一项检查。
`CODEOWNERS` 指定 `@1005John` 审核表情相关文件。
仓库管理员还必须为 `main` 开启规则：要求 PR、代码所有者审核，以及 `verify-expression-runtime` 检查通过。
**仅有 `CODEOWNERS` 文件不能阻止他人改动。**

## 树莓派验收

在 1280 × 720 实屏上运行产品主程序。检查小Q两种风格、Bluebot 开关、16 个状态、转场、聊天显示优先级、失败回退、触控和持续帧率。
本地虚拟屏幕测试不能代替实屏验收。
