# WORKSPACE.md

## 工作空间简介

本工作空间是一个**SVN 工具箱**项目，提供终端 CLI 和桌面 GUI 两种形态的 SVN 操作工具。核心产物是 `svntool.command`（CLI 版）和 `SVN工具箱.app`（GUI 版），均支持多仓库扫描和 7 项常用 SVN 操作。

## 工作流规范

**「先计划，后执行」** —— 详细规则见 `README.md`。关键原则：
- 任何涉及文件修改的请求，必须先输出执行计划，等待用户确认后才能动手
- 例外：纯信息查询、简单问答可以直接执行
- 用户说 `执行` / `开始` / `确认` 才表示可以动手

## 文件清单

| 文件                    | 角色      | 说明                               |
| --------------------- | ------- | -------------------------------- |
| `README.md`           | 规范文档    | 工作流规范，所有 AI agent 必须遵守           |
| `WORKSPACE.md`        | 本文件     | 工作空间说明，供其他 AI agent 读取           |
| `svntool.command`     | CLI 工具  | zsh 交互式菜单，双击终端运行                 |
| `svntool.md`          | 文档      | CLI 版功能说明 + 完整代码                 |
| `svntool_gui.py`      | GUI 源码  | Python Tkinter 应用，CLI 版的 GUI 实现  |
| `svntool_gui.command` | GUI 启动器 | shell 包装 + Python heredoc，双击源码启动 |
| `dist/SVN工具箱.app`     | 独立应用    | PyInstaller 打包的 macOS 独立应用       |
| `icon3-3.icns`        | 图标      | GUI 版自定义图标（ICNS 格式）              |
| `icon3-3.png`         | 图标源     | 图标原始 PNG 文件                      |

## SVN 工具箱功能

CLI 版（`svntool.command`）和 GUI 版（`SVN工具箱.app`）功能完全对应：

| 功能 | SVN 命令 | CLI | GUI | 说明 |
|------|----------|-----|-----|------|
| 查看状态 | `svn st` | ✅ | ✅ | 输出面板展示变更，空输出时提示"没有变更" |
| 更新代码 | `svn up` | ✅ | ✅ | 无更新时提示"已经是最新版本" |
| 提交变更 | `svn ci` | ✅ | ✅ | 冲突检测 + 备注默认时间戳 |
| 扫描变更 | add & rm | ✅ | ✅ | 扫描 `?`/`!` 文件，分类展示，二次确认后执行 |
| 撤销修改 | `svn revert` | ✅ | ✅ | 扫描 `M` 文件，二次确认后撤销 |
| 查看日志 | `svn log -v` | ✅ | ✅ | 自定义条数，显示变更文件列表 |
| 刷新列表 | — | ✅ | ✅ | 重新扫描子目录中的工作副本 |

## 智能启动

- **放在 SVN 工作副本内** → 直接进入工具箱（CLI）/ 自动选中该仓库（GUI）
- **放在多个工作副本的父目录** → 自动递归扫描子目录（深度 3 层），列出清单供选择
- **未发现任何工作副本** → 提示退出

## GUI 版技术栈

- **语言**：Python 3.13（tkinter 内建模块）
- **UI 框架**：Tkinter + ttk 主题
- **异步执行**：svn 命令用后台线程执行，实时输出到队列，UI 不阻塞
- **确认/输入**：`messagebox.askyesno`、`simpledialog.askstring/askinteger`，全部传入 `parent=self.root` 实现居中对齐
- **编码**：所有 subprocess 调用传入 `env={"LANG": "en_US.UTF-8"}` 防止中文乱码
- **布局**：左右 PanedWindow（仓库列表 180px + 输出面板），按钮栏在右侧底部与面板左对齐

## 打包流程

```bash
# 1. 准备 Python 环境（需 tkinter 支持）
python3 -m venv /path/to/venv
pip install pyinstaller

# 2. 打包
pyinstaller --onefile --windowed --icon=icon3-3.icns --name "SVN工具箱" svntool_gui.py

# 3. 产物在 dist/SVN工具箱.app
# 4. 清理
rm -rf build SVN工具箱.spec
```

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

1. **所有对话框 parent=self.root** —— 弹窗相对主窗口居中
2. **日志追加不清除** —— 只有"清空面板"按钮清除输出
3. **日志分块格式** —— 每段 `[类型] YYYY-MM-DD HH:MM:SS` 开头，段落间空行隔开
4. **仓库列表排序** —— 按首字母排序
5. **启动无闪跳** —— `withdraw()` → 布局 → 定位 → `deiconify()`
