# WORKSPACE.md

## 工作空间简介

本工作空间是 **SVN 工具箱** 项目，一个 macOS 原生 SVN GUI 客户端，基于 Python Tkinter + PyInstaller 打包。提供仓库自动扫描、文件状态管理、提交/更新/撤销/解决冲突等常用 SVN 操作，全部通过复选框交互，支持逐个文件精确控制。

## 工作流规范

**「先计划，后执行」** —— 详细规则见 `plan-first-workflow` Skill 和 `~/.workbuddy/MEMORY.md`。关键原则：

- 任何涉及文件修改的请求，必须先输出执行计划，等待用户确认后才能动手
- 例外：纯信息查询、简单问答可以直接执行
- 用户说 `执行` / `开始` / `确认` / `符合` / `没问题` 才表示可以动手

## 文件清单

| 文件 | 角色 | 说明 |
|------|------|------|
| `README.md` | 项目首页 | 目录结构、快速开始、开发指南 |
| `WORKSPACE.md` | 本文件 | 工作空间说明，供其他 AI agent 读取 |
| `svntool_gui.py` | 主程序源码 | 单文件 Python Tkinter 应用（~780 行） |
| `dist/SVN工具箱.app` | 最终产物 | PyInstaller --onefile 打包的 macOS 独立应用 |
| `dist/SVN工具箱` | 可执行文件 | 命令行可直接运行的无后缀版本 |
| `icon3-3.icns` | 图标 | App 图标（ICNS 格式） |
| `icon3-3.png` | 图标源 | 图标原始 PNG 文件 |
| `使用说明.md` | 中文手册 | 面向用户的使用文档 |
| `UserManual.md` | 英文手册 | English user manual |

## 当前功能

| 功能 | 说明 |
|------|------|
| 仓库自动扫描 | 启动时后台扫描当前目录及子目录（深度 3 层）的 .svn 工作副本 |
| 仓库切换 | 左侧列表 + ↑↓ 键盘切换 + 自动清屏刷新 svn st |
| 刷新状态 | svn st + 状态码转中文 + 对齐输出 |
| 更新 | svn up（流式实时输出，完成后自动刷新状态） |
| 提交 | 复选弹框：分类筛选（?/M/!/A/D/~/L）+ 全选 + 按状态自动 add/rm 后 ci |
| 撤销 | 复选弹框：全选 + 逐文件 svn revert |
| 解决冲突 | 复选弹框：全选 + theirs-full / mine-full |
| 刷新仓库列表 | 重新扫描 .svn 目录 |

### 不提供的功能

- svn checkout（需通过命令行检出）
- svn log（不在本工具范围内）
- 分支/合并操作

### 提交逻辑

| 状态 | 预处理 | 提交 |
|------|--------|------|
| `?` | svn add | svn ci |
| `!` | svn rm | svn ci |
| `M`/`A`/`D`/`~`/`L` | — | svn ci |
| `C` | 不出现在提交列表，需先解决冲突 |
| `X` | 不出现，不可直接提交 |

## 技术栈

- **语言**：Python 3.13（tkinter 内建模块）
- **UI 框架**：Tkinter + ttk 主题
- **异步执行**：svn 命令通过后台线程 + Queue 实现流式输出，UI 不阻塞
- **弹框**：Toplevel 窗口，Canvas + 滚动 Frame + 复选框交互
- **鼠标滚轮**：Enter/Leave 事件动态绑/解绑，方向法 ±1 兼容 macOS 触控板
- **编码**：所有 subprocess 传入 `env={"LANG": "en_US.UTF-8"}` 防止中文乱码
- **布局**：左右 PanedWindow（仓库列表 + 输出面板），按钮栏右侧
- **窗口**：初始 900×600，resizable(True, True)，最小 900×600
- **日志框**：wrap=NONE（不换行），只读，垂直滚动条隐藏
- **启动优化**：先显示界面 + "SVN仓库列表中…"，后台线程扫描

## 打包流程

```bash
# 1. 准备 Python 环境（需 tkinter 支持）
pip install pyinstaller

# 2. 打包
pyinstaller --onefile --windowed --icon=icon3-3.icns --name "SVN工具箱" svntool_gui.py

# 3. 产物在 dist/SVN工具箱.app
# 4. 清理
rm -rf build SVN工具箱.spec
```

> ⚠️ --onedir 模式在 WorkBuddy 沙箱内因 PyInstaller 缓存权限问题无法打包，仅支持 --onefile。

## 转换 PNG → ICNS

```bash
mkdir icns.iconset
for s in 16 32 128 256 512; do
  sips -z $s $s src.png --out "icns.iconset/icon_${s}x${s}.png"
  s2=$((s*2))
  sips -z $s2 $s2 src.png --out "icns.iconset/icon_${s}x${s}@2x.png"
done
iconutil -c icns icns.iconset -o output.icns && rm -rf icns.iconset
```

## 重要约定

1. **所有弹框 parent=self.root** — 弹窗相对主窗口居中
2. **切换仓库清空日志** — 不同仓库间隔离
3. **日志分块格式** — 每段 `[类型] YYYY-MM-DD HH:MM:SS` 开头，段落间空行隔开
4. **操作开始反馈** — 点击按钮立即输出 `[操作] 时间 开始XX...`，避免用户以为卡顿
5. **仓库列表排序** — 按首字母排序
6. **异步加载** — 仓库扫描不阻塞启动，先显示界面再填充列表
7. **svn 依赖检查** — 启动时找不到 svn 命令行弹出友好提示
