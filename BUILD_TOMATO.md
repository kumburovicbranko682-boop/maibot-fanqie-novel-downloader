# 从源码构建本机签名引擎

环境：Rust stable、网络（拉 crates.io 依赖）。

## 推荐：可审计 No-Official-API 构建

```powershell
# Windows
pwsh -File scripts/build_tomato.ps1

# 或跨平台
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

说明：仓库内已附带完整 `Cargo.toml`（含 official-api 路径依赖）。公开环境请优先用上面的 `Cargo_no_official.toml` 流程，否则 `cargo build` 会因缺少 sibling Official-API 失败。

## Official-API 构建（需私有 crate）

```text
third_party/
  Tomato-Novel-Downloader/   # 本仓库已包含
  Tomato-Novel-Official-API/ # 需自行取得，与上游 path 依赖一致
```

```bash
cd third_party/Tomato-Novel-Downloader
cargo build --release
```

然后将 `target/release/tomato-novel-downloader(.exe)` 配置到 `downloader.tomato_exe`。

## 平台说明

本插件逻辑跨平台；可执行引擎需在目标 OS 上自行从本仓库源码构建。仓库**不再内置**预编译 Windows exe。
