# SVN Toolbox · User Manual

A native macOS SVN GUI client built with Tkinter and packaged with PyInstaller. Small footprint, intuitive interface.

---

## 1. System Requirements

- macOS 11+ (Big Sur or later)
- SVN working copies must be checked out via the command line (the app does not provide a checkout function)

---

## 2. Environment Setup

### 1. Install Homebrew (if not installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install svn Command Line Tool

```bash
brew install svn
```

> Verify: `svn --version` should print version info normally.

### 3. Check Out an SVN Repository

```bash
svn checkout <repository_url> /path/to/local/repo
```

> ⚠️ The app only recognizes SVN working copies checked out via the command line; it does not provide a checkout function.
> It is recommended to check out repositories as subdirectories of the folder where the app is launched (default scan: current directory and subdirectories, depth 3).

---

## 3. Installing the App

Drag `SVN Toolbox.app` into the `/Applications` folder and double-click to run.

> If you see "cannot be opened because the developer cannot be verified" on first launch, right-click → Open → Open.

---

## 4. Interface Overview

```
┌─────────────────────────────────────────────┐
│ Repo List               Output Panel         │
│ 📁 repo-1            [Repo switched:repo-1]  │
│ 📁 repo-2            ?     Unversioned file1 │
│ 📁 repo-3            M     Modified   file2  │
│                                              │
│  [Refresh List]  [Refresh][Resolve]...        │
│                          [Revert][Up][Commit]│
└─────────────────────────────────────────────┘
```

### Left: Repository List

- Auto-scans current directory and subdirectories (3 levels) for `.svn` working copies
- Async scan at startup; UI is not blocked

### Right: Output Panel

- Real-time operation log, **no line wrapping** — drag the window wider to view long paths
- Auto-clears and refreshes `svn st` when switching repositories

### Bottom Buttons

- **Refresh Repo List** (left) — re-scan `.svn` directories
- **Refresh Status** (right) — re-run `svn st`
- **Resolve Conflict** (right) — resolve conflict files
- **Revert** (right) — revert local modifications
- **Update** (right) — `svn up`
- **Commit** (right) — `svn ci`

---

## 5. Operations in Detail

### 1. Refresh Status

Immediately outputs `Starting to fetch repository status...`, then displays `svn st` results with status codes translated to Chinese labels.

### 2. Update

Immediately outputs `Starting to pull updates...`, then streams the `svn up` process. Auto-refreshes status when complete.

### 3. Commit

In the dialog:
- Top: Select-All checkbox + category filters (`?` Unversioned / `M` Modified / `!` Missing / `A` Added / `D` Deleted / `~` Type Changed / `L` Locked)
- Middle: A checkbox before each file (individually selectable)
- Bottom: Enter commit message (leave blank to use timestamp) → Commit

Logic:
- Selected `?` files are auto `svn add`-ed
- Selected `!` files are auto `svn rm`-ed
- Selected `M` (etc.) files go directly to `svn ci -m "msg" <files>`
- **C conflict files are NOT shown in the commit list** — resolve them first
- **X externals are NOT shown** — not committable

### 4. Revert

Lists all `M` files in the dialog. Check the ones you want to revert, then click "Revert Selected".

> ⚠️ Revert is irreversible!

### 5. Resolve Conflict

Lists all `C` files in the dialog:
- **Use Their Version** — discard local, use repository version
- **Use My Version** — keep local, discard repository changes

After resolution, file status changes from `C` to `M` and can be committed.

---

## 6. Keyboard Shortcuts

| Key | Function |
|-----|----------|
| `↑` `↓` | Switch repository |
| `Enter` | Execute focused button |
| `Esc` | Remove button focus |

> When a dialog is open, shortcuts do not affect the main window.

---

## 7. Status Code Reference

| Code | Label | Handling |
|------|-------|----------|
| `?` | Unversioned | svn add |
| `M` | Modified | commit directly |
| `!` | Missing | svn rm |
| `A` | Added | commit directly |
| `D` | Deleted | commit directly |
| `C` | Conflict | resolve first |
| `~` | Type changed | commit directly |
| `L` | Locked | commit directly |
| `X` | External | not directly committable |

---

## 8. FAQ

### Q1: Repository list is empty after launch?

- Verify the SVN working copy has a `.svn` directory
- Default scan depth is 3 levels; repos outside this range will not be detected
- The app must be launched from a parent directory of the working copy

### Q2: "svn command line tool not detected" on launch?

Follow section 2 above to install svn, then restart the app.

### Q3: Commit failed?

- Conflict files present → resolve them first
- Empty message → leave blank to auto-use timestamp
- Server requires non-empty message → enter actual content

### Q4: Slow startup?

Inherent to PyInstaller `--onefile` packaging — each launch requires decompression. For faster startup, repackage with `--onedir` outside the sandbox.

### Q5: Cannot see full file path in the log panel?

The log does not wrap. Drag the window edge to widen, or use the (hidden) scrollbar via mouse wheel / trackpad.

---

## 9. Feedback

Before reporting issues, verify:
1. `svn --version` works
2. The repo is properly checked out
3. The app is launched from a parent directory of the working copy
