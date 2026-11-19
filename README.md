<div align="center">

# 虎牙 plus

面向虎牙直播的 LSPosed 模块，提供广告过滤、默认清晰度和每日任务。

[![LSPosed Module](https://img.shields.io/badge/LSPosed-Module-0969da)](https://github.com/Xposed-Modules-Repo/io.github.saycm.huyaplus/releases)
[![GitHub 源码](https://img.shields.io/badge/GitHub-%E6%BA%90%E7%A0%81-24292f)](https://github.com/saycm/huyaplus)
[![Telegram 频道](https://img.shields.io/badge/Telegram-%E9%A2%91%E9%81%93-0969da)](https://t.me/+Gdwx4F3flrwzYzE1)

[![最新版本](https://img.shields.io/github/v/release/Xposed-Modules-Repo/io.github.saycm.huyaplus?label=release)](https://github.com/Xposed-Modules-Repo/io.github.saycm.huyaplus/releases/latest)

[下载模块](#下载模块) · [支持应用](#支持应用) · [环境要求](#环境要求) · [使用教程](#使用教程) · [常见问题](#常见问题) · [社区](#社区) · [说明](#说明)

</div>

## 关于虎牙 plus

虎牙 plus 基于 libxposed API 102 开发。安装后可在模块的虎牙详情页分别设置以下功能：

- **广告过滤**：过滤开屏、推荐页和直播间的指定广告。
- **直播清晰度**：进入直播间时应用预设清晰度，支持手动调整。
- **每日任务**：按开关执行已适配的任务，并记录结果。

## 下载模块

- [安装包与发布说明](https://github.com/Xposed-Modules-Repo/io.github.saycm.huyaplus/releases)
- [完整变更记录](CHANGELOG.md)

## 支持应用

当前适配虎牙直播 **13.5.44**（`117129`），作用域为 `com.duowan.kiwi`。

| 功能 | 支持范围 |
| --- | --- |
| 广告过滤 | 过滤开屏、推荐页、沉浸页和直播间的指定广告，包括部分推广卡片、横幅及浮窗。 |
| 奖励广告 | 支持部分虎粮和小程序奖励入口跳过视频，奖励由虎牙结算。 |
| 直播清晰度 | 可设置默认清晰度。蓝光优先选用当前直播间可用的最高蓝光档位，手动切换后保留本次选择。 |
| 4K 播放（实验） | 适用于部分直播间已提供的 4K 档位，实际可用性受直播源、设备和服务端鉴权影响。 |
| 每日任务 | 支持已有粉丝牌打卡、指定直播间赠送免费虎粮、任务中心签到、自动投骰及已适配的骰子任务。每日赚金币支持整点金币和饭点补贴。 |
| 功能开关与日志 | 在虎牙详情页设置功能和任务开关，在任务日志中查看执行结果及跳过原因。 |

## 环境要求

| 项目 | 版本或范围 |
| --- | --- |
| 模块版本 | 1.18（`19`） |
| Android | Android 10 及以上（API 29+） |
| 框架 | 支持 libxposed API 102 的 LSPosed |
| 模块包名 | `io.github.saycm.huyaplus` |

## 使用教程

从旧包名 `io.github.saycm.huya.skipad` 换装时，请在 LSPosed 中停用旧模块，再启用新模块并重新设置作用域。

1. 安装虎牙 plus，在 LSPosed 中启用模块。
2. 在作用域中勾选虎牙直播（`com.duowan.kiwi`）。
3. 打开虎牙 plus，进入「虎牙 → 详情」设置所需功能。自动任务默认关闭，赠送功能使用免费虎粮库存。
4. 强制停止虎牙直播，再重新打开。自动任务在每天首次打开虎牙且登录就绪后触发。任务设置详见 [虎牙任务中心](docs/task-center.md)。

## 常见问题

**为什么打开虎牙后，功能没有生效？** 先检查模块启用状态、作用域和虎牙版本。修改设置后，强制停止虎牙再打开。

**怎么确认任务是否执行？** 在虎牙详情页打开任务日志，查看成功、失败、跳过和待确认状态。奖励结果以虎牙服务端确认为准。

**怎么反馈问题？** 请附上虎牙版本、模块版本、Android 版本、复现步骤和脱敏后的相关日志。

## 社区

- [Telegram 频道](https://t.me/+Gdwx4F3flrwzYzE1)
- [Telegram 讨论组](https://t.me/+fFxFjUupwRllYWM1)

## 说明

- 虎牙 plus 是独立开发的 LSPosed 模块，采用 MIT 许可证开放源代码。
- 模块免费使用，赞赏完全自愿。
- 适配范围见本页。虎牙版本更新后，部分功能可能需要重新适配，欢迎在讨论组反馈。

## 赞助打赏

如果模块对你有帮助，可以用微信扫描下方赞赏码。谢谢支持。

<a href="docs/assets/wechat-appreciation.png"><img src="docs/assets/wechat-appreciation.png" width="240" alt="微信赞赏码"></a>

## 构建与测试

构建需要 Python 3、JDK 17、Android SDK Platform 36 和 Build Tools 36.0.0。

```powershell
$env:ANDROID_HOME = "C:\Android\Sdk"
$env:JAVA_HOME = "C:\Java\jdk-17"
python tools\build.py
```

运行回归测试：

```powershell
python tests\test_huya_api102_metadata.py
python tests\test_huya_loader_lifecycle.py
python tests\test_huya_display_ads.py
python tests\test_huya_miniapp_rewards.py
python tests\test_huya_vip_playback.py
python -m unittest discover -s tests -p "test_*automation*.py"
```

## 许可证

本项目采用 [MIT License](LICENSE)。
