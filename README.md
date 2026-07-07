# GhostAction 👻

**Desktop RPA Tool: Record, Replay, Share**

幽灵操作 - 桌面RPA自动化工具，让电脑替你重复干活。

## Features

- 🎯 **One-Click Record** - Record mouse clicks, keyboard input, scrolling
- 🔄 **Smart Replay** - Visual matching + OCR + Accessibility API positioning
- 📋 **Logic Chain** - Auto-generate human-readable operation flow
- 🪟 **Window Awareness** - Group operations by window, filter by target
- 📤 **Script Marketplace** - Share and download scripts via GitHub Gist
- 🖥️ **Cross-Platform** - macOS (now) + Windows (coming soon)

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

## Script Marketplace

Share your automation scripts with the community:

1. Click **📤 Share** in the app
2. Your script is uploaded to GitHub Gist
3. Others can search, download, and merge into their local scripts

## Requirements

- macOS 12+ (Monterey or later)
- Python 3.10+ (bundled in DMG)
- Accessibility permission (System Settings → Privacy & Security)
- Screen Recording permission (for visual matching)

## License

MIT