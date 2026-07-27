# 第三方组件说明

## Tomato-Novel-Downloader

| 项 | 值 |
|---|---|
| 上游 | https://github.com/zhongbai2333/Tomato-Novel-Downloader |
| 钉住版本 | `v2.4.13`（目录快照，无嵌套 `.git`） |
| 许可证 | MIT（见本目录 `Tomato-Novel-Downloader/LICENSE`） |
| 本插件用途 | 以 `--server` 启动本机 Web UI / 签名网关，供插件调用 localhost API |

### 关于 Official-API

上游默认 feature `official-api` 依赖私有路径 crate `../Tomato-Novel-Official-API`，**该 crate 未开源**，公开仓库无法完整复现 Official-API 构建。

本插件提供的**可复现公开构建**使用上游文档中的 **No-Official-API** 模式（`Cargo_no_official.toml` / `--features no-official-api`）：目录与书信息走网页解析，正文走第三方 API 地址池。详见 `BUILD_TOMATO.md`。

若你自有 Official-API 源码，可按上游 README 放在 sibling 目录后执行默认 `cargo build --release`，再将产物路径填入插件配置 `downloader.tomato_exe`。
