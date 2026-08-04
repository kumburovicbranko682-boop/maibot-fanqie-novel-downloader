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
