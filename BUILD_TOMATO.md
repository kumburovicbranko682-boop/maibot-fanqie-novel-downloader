# 从源码构建本机引擎（可选）

普通用户**不需要**这一步：启用插件后会自动从上游 Releases 下载引擎。

本机构建适合：离线环境、需要 No-Official-API 定制编译、或不信任预构建产物时。

需要：Rust stable、网络（拉 crates.io 依赖）。

## 推荐：一键 No-Official-API 构建

```powershell
# Windows
pwsh -File scripts/build_tomato.ps1

# 多平台
python scripts/build_tomato.py
```

产物默认复制到：

- Windows: `bin/tomato-novel-downloader.exe`
- Unix: `bin/tomato-novel-downloader`

等价手动步骤：

```bash
cd third_party/Tomato-Novel-Downloader
cp Cargo_no_official.toml Cargo.toml
cargo build --release --no-default-features --features no-official-api,tts,clipboard,clipboard-arboard
# 产物: target/release/tomato-novel-downloader(.exe)
```

说明：仓库内已附带上游 `Cargo.toml`。若 official-api 路径依赖缺失，请用上面的 `Cargo_no_official.toml` 流程，避免 `cargo build` 因缺少 sibling Official-API 失败。

## Official-API 构建（需私有 crate）

```text
third_party/
  Tomato-Novel-Downloader/   # 本仓库已包含
  Tomato-Novel-Official-API/ # 需自行取得，并满足 path 依赖约定
```

```bash
cd third_party/Tomato-Novel-Downloader
cargo build --release
```

然后将 `target/release/tomato-novel-downloader(.exe)` 配到 `downloader.tomato_exe`。

## 平台说明

插件 Python 逻辑跨平台；可执行引擎需匹配目标 OS。仓库**故意不提交**预编译 Windows/Linux exe；默认走自动下载，源码构建为可选路径。

## 热更新（hotfix）说明

上游 Tomato 引擎在启动时会调用 `check_hotfix_and_apply`：访问 GitHub Releases API，若**同版本号**下远端资产 SHA256 与本地可执行文件不同，会下载并覆盖当前二进制。

本仓库对 vendored 源码打了补丁：设置环境变量即可关闭该路径：

```text
TOMATO_DISABLE_HOTFIX=1
```

插件通过 `subprocess` 启动引擎时**默认写入**该变量。因此：

- 用本目录源码 `scripts/build_tomato.*` 构建的引擎：热更新会被可靠关闭；
- 仍想手动开启热更新时，启动前设 `TOMATO_DISABLE_HOTFIX=0`（并确保插件未强制覆盖；当前实现用 `setdefault`，宿主已设置则尊重）。

若只使用上游 GitHub Releases 的预构建包、且未用本仓库补丁重建，该环境变量本身不被上游原版识别；插件会额外设置 `CARGO=maibot-fanqie-plugin`，利用上游「开发态跳过热更新」的启发式作为兼容层（上游若改掉该启发式则失效）。**需要钉死二进制完整性时，请用本仓库源码构建。**
