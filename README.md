# 番茄小说下载插件

通过本机 Tomato Official-API 签名网关下载番茄/常读小说为 TXT。

**自动检测：** 聊天中出现番茄/常读链接后，若配置时间内无人回复，则自动发送书籍卡片（书名/作者/章节/平台 + 封面）。

## 安装

1. 将整个目录复制到 MaiBot 插件目录。
2. 确认 `bin/TomatoNovelDownloader-Win64-v2.4.13.exe` 存在。
3. 热加载 / 重启 MaiBot。

## 用法

### 自动卡片（默认开启）

直接发送链接，或聊天里夹带链接：

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

## 卡片样式

```text
📖 《书名》
✍️ 作者：xxx
📚 共 N 章
🔖 平台：番茄小说
```
+封面图

## 配置

| 项 | 默认 | 说明 |
|---|---|---|
| `auto_detect.enabled` | `true` | 自动检测链接 |
| `auto_detect.delay_seconds` | `30` | 链接发出后无人回复多久再发卡片（秒），0=立即发 |
| `auto_detect.cooldown_seconds` | `120` | 同一聊天流对同一书的发送冷却 |
| `downloader.tomato_exe` | 插件内 `bin/...exe` | 本机签名引擎 |
| `downloader.try_send_file` | `true` | 下载完后尝试发文件 |
| `security.allow_public` | `true` | 非管理员可否下载 |

## License

MIT
