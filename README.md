# 番茄小说下载插件

通过本机 Tomato Official-API 签名网关下载番茄/常读小说为 TXT。
下载前会先发送书籍卡片（书名/作者/章节/平台 + 封面图）。

## 安装

1. 将整个 番茄小说下载插件 目录复制到 MaiBot 插件目录。
2. 确认 in/TomatoNovelDownloader-Win64-v2.4.13.exe 存在。
3. 热加载 / 重启 MaiBot。

## 指令

`	ext
#小说 帮助
#小说 信息 <链接|book_id>     # 只发卡片，不下载
#小说 下载 <链接|book_id>     # 先发卡片，再后台下载
#小说 状态 [任务ID]
#小说 列表
`

同义前缀：#番茄 / #fanqie / #novel

## 卡片样式

`	ext
📖 《书名》
✍️ 作者：xxx
📚 共 N 章
🔖 平台：番茄小说
`
+封面图（send.hybrid / send.image）

## 配置要点

| 项 | 默认 | 说明 |
|---|---|---|
| downloader.tomato_exe | 插件内 in/...exe | 本机签名引擎 |
| downloader.gateway_addr | http://127.0.0.1:18423 | 网关地址 |
| downloader.try_send_file | 	rue | 下载完成后尝试发文件 |
| security.allow_public | 	rue | 非管理员可否下载 |
