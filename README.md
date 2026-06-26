# SVN 工具箱

macOS 原生 SVN GUI 客户端，基于 Python Tkinter + PyInstaller 打包。

## 项目结构

```
macOS终端脚本/
├── svntool_gui.py          # 主程序源码（单文件，~780 行）
├── icon3-3.icns            # App 图标（icns 格式）
├── icon3-3.png             # App 图标（png 格式）
├── 使用说明.md              # 中文使用手册
├── UserManual.md           # 英文使用手册
└── README.md               # 本文件（项目首页）
```

## 快速开始

1. 安装 svn 命令行：`brew install svn`
2. 检出工作副本：`svn checkout <url> <path>`
3. 双击 `dist/SVN工具箱.app` 启动

详细步骤见 [`使用说明.md`](./使用说明.md)。

## 开发

### 依赖

- Python 3.13+
- tkinter（Python 标准库）
- PyInstaller（打包用）

### 调试

```bash
python3 svntool_gui.py
```

### 打包

```bash
# 调整工作空间侧边栏宽度
pyinstaller --onefile --windowed --icon=icon3-3.icns --name "SVN工具箱" svntool_gui.py
```

## 功能

| 功能 | 说明 |
|------|------|
| 仓库自动扫描 | 启动时扫描当前目录及子目录（3 层）的 .svn 工作副本 |
| 仓库状态 | svn st + 状态码转中文 |
| 更新 | svn up（流式输出） |
| 提交 | 复选弹框 + 分类筛选 + 自动 add/rm |
| 撤销 | 复选弹框 + svn revert |
| 解决冲突 | 复选弹框 + theirs-full / mine-full |

