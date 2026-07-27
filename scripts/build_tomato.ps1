# 从 third_party 源码构建 Tomato 引擎
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python (Join-Path $PSScriptRoot "build_tomato.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
