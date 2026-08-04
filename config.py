"""番茄小说下载插件配置。"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from maibot_sdk import Field, PluginConfigBase

CONFIG_VERSION = "1.4.1"
PLUGIN_DIR = Path(__file__).resolve().parent


def _default_tomato_exe() -> str:
    """Prefer locally built artifact; fall back to legacy Release filename."""
    import os

    names = (
        "tomato-novel-downloader.exe" if os.name == "nt" else "tomato-novel-downloader",
        "tomato-novel-downloader",
        "TomatoNovelDownloader-Win64-v2.4.13.exe",
    )
    candidates = []
    for name in names:
        candidates.append(PLUGIN_DIR / "bin" / name)
    release = PLUGIN_DIR / "third_party" / "Tomato-Novel-Downloader" / "target" / "release"
    for name in names:
        candidates.append(release / name)
    for path in candidates:
        if path.is_file():
            return str(path)
    return str(PLUGIN_DIR / "bin" / names[0])


DEFAULT_EXE = _default_tomato_exe()
DEFAULT_OUTPUT = str(PLUGIN_DIR / "data" / "output")
DEFAULT_TOMATO_DATA = str(PLUGIN_DIR / "data" / "tomato-data")


class PluginSection(PluginConfigBase):
    __ui_label__: ClassVar[str] = "插件"
    __ui_icon__: ClassVar[str] = "book-open"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(default=True, description="是否启用番茄小说下载插件。")
    config_version: str = Field(
        default=CONFIG_VERSION,
        description="配置结构版本。",
        json_schema_extra={"hidden": True, "disabled": True},
    )


class DownloaderSection(PluginConfigBase):
    __ui_label__: ClassVar[str] = "下载器"
    __ui_icon__: ClassVar[str] = "download"
    __ui_order__: ClassVar[int] = 1

    tomato_exe: str = Field(
        default=DEFAULT_EXE,
        description="本机引擎路径。默认 bin/tomato-novel-downloader；缺失时可自动从 GitHub Releases 拉取。",
    )
    auto_fetch_engine: bool = Field(
        default=True,
        description="引擎缺失时自动从 GitHub Releases 下载（仓库不内置 exe）。",
    )
    engine_version: str = Field(
        default="v2.4.13",
        description="自动下载使用的上游引擎版本标签。",
    )
    engine_download_url: str = Field(
        default="",
        description="可选：自定义引擎下载 URL（镜像）。留空则按平台自动拼接上游 Release 地址。",
    )
    engine_sha256: str = Field(
        default="",
        description="可选：下载后校验 SHA256；留空则跳过校验。",
    )
    tomato_data_dir: str = Field(
        default=DEFAULT_TOMATO_DATA,
        description="签名引擎数据目录。",
    )
    output_dir: str = Field(
        default=DEFAULT_OUTPUT,
        description="小说 TXT 输出目录。",
    )
    gateway_addr: str = Field(
        default="http://127.0.0.1:18423",
        description="本机签名网关地址。",
    )
    gateway_password: str = Field(
        default="local123",
        description="本机签名网关密码。",
    )
    max_workers: int = Field(default=6, ge=1, le=16, description="下载并发数。")
    try_send_file: bool = Field(
        default=True,
        description="完成后尝试通过 send.custom 发送 TXT 文件（取决于适配器是否支持）。",
    )


class SecuritySection(PluginConfigBase):
    __ui_label__: ClassVar[str] = "权限"
    __ui_icon__: ClassVar[str] = "shield"
    __ui_order__: ClassVar[int] = 2

    allow_public: bool = Field(
        default=True,
        description="是否允许非管理员发起下载。",
    )
    administrators: list[str] = Field(
        default_factory=list,
        description="管理员列表，格式 user_id 或 platform:user_id。",
    )
    inherit_plugin_management_permissions: bool = Field(
        default=True,
        description="是否继承 MaiBot plugin.permission 管理员。",
    )




class AutoDetectSection(PluginConfigBase):
    __ui_label__: ClassVar[str] = "\u81ea\u52a8\u68c0\u6d4b"
    __ui_icon__: ClassVar[str] = "link"
    __ui_order__: ClassVar[int] = 3

    enabled: bool = Field(
        default=True,
        description="\u68c0\u6d4b\u5230\u756a\u8304/\u5e38\u8bfb\u94fe\u63a5\u65f6\u81ea\u52a8\u53d1\u9001\u4e66\u7c4d\u5361\u7247\uff08\u53ef\u914d\u7f6e\u5ef6\u8fdf\uff09\u3002",
    )
    delay_seconds: int = Field(
        default=30,
        ge=0,
        le=3600,
        description="\u68c0\u6d4b\u5230\u94fe\u63a5\u540e\uff0c\u7b49\u5f85\u591a\u5c11\u79d2\u65e0\u4eba\u56de\u590d\u518d\u53d1\u5361\u7247\uff1b0 \u8868\u793a\u7acb\u5373\u53d1\u9001\u3002",
    )
    cooldown_seconds: int = Field(
        default=120,
        ge=0,
        le=86400,
        description="\u540c\u4e00\u804a\u5929\u6d41\u5bf9\u540c\u4e00 book_id \u7684\u53d1\u9001\u51b7\u5374\uff08\u79d2\uff09\uff0c0 \u8868\u793a\u4e0d\u51b7\u5374\u3002",
    )


class FanqieNovelDownloaderConfig(PluginConfigBase):
    plugin: PluginSection = Field(default_factory=PluginSection)
    downloader: DownloaderSection = Field(default_factory=DownloaderSection)
    security: SecuritySection = Field(default_factory=SecuritySection)
    auto_detect: AutoDetectSection = Field(default_factory=AutoDetectSection)
