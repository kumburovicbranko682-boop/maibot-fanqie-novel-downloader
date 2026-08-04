# 番茄小说下载插件

通过本机 Tomato 引擎（`--server` 网关）下载番茄/常读小说为 TXT。

**自动检测：** 聊天中出现番茄/常读链接后，若配置时间内无人回复，则自动发送书籍卡片（书名/作者/章节/平台 + 封面）。

## 安装（一键）

1. 将本仓库克隆/复制到 MaiBot 的 `plugins/` 目录（例如 `plugins/github_kumburovicbranko682-boop_fanqie-novel-downloader`）。
2. 在 WebUI 启用插件，或确认 `config.toml` 里 `[plugin] enabled = true`。
3. 重启 / 热加载 MaiBot。

**无需预编译 exe，也无需本机安装 Rust。**  
首次加载（或首次下载）时，插件会按当前系统自动从上游 GitHub Releases 拉取对应引擎到 `bin/`。

可选：若 GitHub 访问慢，在配置里填写 `downloader.engine_download_url` 指向镜像。

高级用户仍可本机构建：见 [BUILD_TOMATO.md](BUILD_TOMATO.md)。

## 平台

| 系统 | 自动下载资产 |
|---|---|
| Windows x64 | `TomatoNovelDownloader-Win64-v2.4.13.exe` |
| Linux amd64 | `TomatoNovelDownloader-Linux_amd64-v2.4.13` |
| Linux arm64 / macOS | 同版本对应资产 |

## 用法

### 自动卡片（默认开启）

```text
https://fanqienovel.com/page/7322690665316371518
https://changdunovel.com/t/8ROF4ofKDwc/
```

默认等待 **30 秒**无人回复后再发卡片；期间若有人说话则取消发送。

### 手动指令

```text
#小说 帮助
#小说 信息 <链接|book_id>
#小说 下载 <链接|book_id>
#小说 状态 [任务ID]
#小说 列表
```

同义前缀：`#番茄` / `#fanqie` / `#novel`

## 配置

| 项 | 默认 | 说明 |
|---|---|---|
| `auto_detect.enabled` | `true` | 自动检测链接 |
| `auto_detect.delay_seconds` | `30` | 链接发出后无人回复多久再发卡片（秒），0=立即发 |
| `auto_detect.cooldown_seconds` | `120` | 同一聊天流对同一书的发送冷却 |
| `downloader.auto_fetch_engine` | `true` | 引擎缺失时自动下载 |
| `downloader.engine_version` | `v2.4.13` | 自动下载版本 |
| `downloader.engine_download_url` | 空 | 自定义/镜像下载地址 |
| `downloader.tomato_exe` | `bin/tomato-novel-downloader` | 本机引擎路径 |
| `downloader.try_send_file` | `true` | 下载完后尝试发文件 |
| `security.allow_public` | `true` | 非管理员可否下载 |

网关日志：`data/tomato-data/logs/server.stdout.log` / `server.stderr.log`。

## License

MIT。第三方 Tomato-Novel-Downloader 亦为 MIT，见 `third_party/`。
