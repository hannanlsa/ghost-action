# GhostAction 👻

**让机器做机器该做的事**

Desktop RPA Tool: Record, Replay, Share

## 宗旨

GhostAction 的初衷很简单：**把人从重复的、机械的劳动中解放出来。**

那些每天重复几十遍的表单填写、数据录入、界面操作——本不该由人来完成。GhostAction 致力于让这类工作自动化，把时间还给更有价值的事。

## 关于本项目

- **代码全程由 AI 编写**，从第一行到最后一行，无人为手写代码参与。
- **源码完全公开**，采用 [GPL-3.0](LICENSE) 协议，需要的自取，随缘而已。
- 本工具因自用而起，随性而为，不设 KPI，不承诺路线图。

## 核心能力：通用型桌面自动化

GhostAction 不局限于特定应用或特定场景，其设计目标是**操作一切可见之物**：

| 识别方式 | 适用范围 | 原理 |
|---------|---------|------|
| **Accessibility API** | 原生应用（Safari、Finder、系统偏好设置等） | 直接读取系统无障碍元素树，精准定位控件 |
| **OCR 文字识别** | 任何可见界面（网页、Electron 应用、跨平台工具等） | 识别屏幕文字作为锚点，定位操作目标 |
| **视觉模板匹配** | 任何可截图的界面（游戏、远程桌面、虚拟机等） | 截取目标区域图像，运行时全屏搜索匹配 |
| **CGEvent 事件注入** | 全局有效 | 向任意窗口发送鼠标/键盘事件，模拟真实操作 |

三种识别方式自动回退：Accessibility → OCR → 视觉匹配，无需手动选择，系统自动择优。

**数据驱动回放**：录制一次操作模板，绑定 CSV/Excel/JSON 数据源，即可批量回放成百上千行数据——填表、录入、批量操作，一键完成。

**点选构建模式**：无需录制，直接点选屏幕元素，自动识别并添加操作步骤，逐步构建自动化脚本。

## 跨平台

当前版本支持 **macOS**。**Windows 版本正在规划中**，将在 macOS 版本稳定后启动开发。

两个平台共享相同的核心设计理念（多模态识别 + 数据驱动 + 点选构建），底层事件注入和窗口管理适配各平台原生 API。

## Quick Start

### macOS

1. Download latest `GhostAction.dmg` from [Releases](https://github.com/hannanlsa/ghost-action/releases)
2. Drag to Applications
3. Open (right-click → Open on first launch)
4. Grant Accessibility & Screen Recording permissions when prompted

### From Source

```bash
git clone https://github.com/hannanlsa/ghost-action.git
cd ghost-action
pip install -r requirements.txt
python main.py
```

## How It Works

```
Record → Events (click/type/scroll) + OCR anchors + Visual templates + Accessibility elements
  ↓
Edit → Human-readable logic chain + Window grouping + Step management
  ↓
Replay → Visual match → OCR locate → Accessibility press → Coordinate fallback
  ↓
Share → Upload to Gist → Others download → Smart merge
```

## 免责声明

GhostAction 的通用性设计覆盖了广泛的应用场景，但**不保证对所有软件、所有界面、所有操作系统的普适性**。

原因很简单：

- 作者个人使用，**测试样本有限**，无法覆盖所有应用和所有场景
- 不同应用的界面架构、渲染方式、权限模型差异巨大，部分场景可能无法正常识别或操作
- macOS 系统更新可能导致 API 行为变化

**遇到问题属于正常现象**，而非缺陷。如果你在使用中发现不适配的场景，欢迎通过以下方式参与：

- 📋 提交 [Issue](../../issues)，附上目标应用名称、操作描述、错误日志
- 📤 上传需求或日志到 [Discussions](../../discussions)
- 🔧 提交 Pull Request，一起维护本仓库

**众人拾柴火焰高**——样本越多，适配越广，工具越强。期待你的参与。

## Requirements

- macOS 12+ (Monterey or later)
- Python 3.10+ (bundled in DMG)
- Accessibility permission (System Settings → Privacy & Security)
- Screen Recording permission (for visual matching)

## License

[GPL-3.0](LICENSE)
