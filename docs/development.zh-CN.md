# 开发与网站检查

[English](development.md) · [文档目录](README.zh-CN.md)

下面的命令都在项目根目录运行。先把 `DATA_ROOT` 设为源码之外的绝对路径，可以从已有工作区配置读取，也可以明确指定一个外部目录。开发环境和需要保留的测试输出放在那里。

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:DATA_ROOT "2026-quant-competition/environments/dev"
```

## Python 检查

项目使用 Python 3.12 和已提交的 `uv.lock`。GitHub Actions 会检查代码、运行测试、编译 Python 文件，并扫描完整 Git 历史中的密钥泄露。这些检查不会连接数据服务或 IB Gateway。

```powershell
uv sync --locked --extra test --extra ibkr
uv run --locked ruff check .
uv run --locked pytest -q
uv run --locked python -m compileall -q src
```

两个基础研究包有独立环境和测试，具体入口见[研究包说明](../research/README.zh-CN.md)。独立记账包的检查见[记账对照](research/accounting-comparison.zh-CN.md)。

## 构建网站

网站使用 Astro 和 Node.js 24，默认显示英文，简体中文页面在 `/zh-CN/`。首页介绍股票和加密研究路线，展示示例输入、演示命令和已有结果。切换研究路线只会改变网页展示，不会在浏览器里运行回测。

```powershell
npm --prefix site ci
npm --prefix site run build
npx --prefix site playwright install chromium
npm --prefix site test
uv run --locked python -m competition_tools.check_pages_content --source-dir site --built-dir site/dist
```

构建产物位于 `site/dist/`，Pages 工作流检查通过后发布这个目录。工作流还会检查格式，并检查源码和产物中是否混入不应公开的文件或敏感值。

翻译文字在 `site/src/i18n/`，两种语言共用渲染逻辑，保持命令和样例数值一致。网站默认跟随系统明暗设置，也可以手动选择浅色、深色或跟随系统。浏览器允许存储时，这个选择会在两种语言之间保留。禁用 JavaScript 后仍会跟随系统配色。

浏览器测试覆盖主题设置、系统主题变化、中英文、移动端，以及文字、表格和图表的对比度。要保留浏览器测试产物，把 `PAGES_TEST_OUTPUT` 设为配置的数据目录下的任务专用路径；未设置时使用系统临时目录。
