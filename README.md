<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:FB7299,100:00AEEC&height=200&section=header&text=%E5%8F%B7%E6%B5%B7%E6%8D%9E%E7%8F%8D&fontSize=48&fontColor=ffffff&animation=twinkling&desc=%E5%9C%A8%E5%8F%B7%E6%B5%B7%E4%B9%8B%E4%B8%AD%EF%BC%8C%E6%8D%9E%E5%8F%96%E5%B1%9E%E4%BA%8E%E4%BD%A0%E7%9A%84%E7%8F%8D%E5%AE%9D&descSize=16&descAlignY=74" width="100%"/>

# **bili-treasure-hunter**

**B 站 UID 寻号 · 判定 · 筛选 —— 桌面版 + 安卓版，全引擎本机运行**

![Release](https://img.shields.io/github/v/release/uuapi/bili-treasure-hunter?style=for-the-badge&color=FB7299)
![Platform](https://img.shields.io/badge/平台-Windows%20%7C%20Android-00AEEC?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge)
![Tests](https://img.shields.io/badge/测试-82%20passing-17994f?style=for-the-badge)
![License](https://img.shields.io/github/license/uuapi/bili-treasure-hunter?style=for-the-badge)
![Stars](https://img.shields.io/github/stars/uuapi/bili-treasure-hunter?style=for-the-badge&color=yellow)

**双端安装包 · 五级判定体系 · 7 类靓号规则 · 82 项自动化测试 · 全引擎本机运行 · 零费用**

[✨ 功能特色](#-功能特色) · [🏆 判定等级](#-判定等级) · [🚀 快速上手](#-快速上手) · [🛠 自行构建](#%EF%B8%8F-自行构建) · [🤖 CI 自动构建](#-ci-自动构建) · [⚠️ 免责声明](#%EF%B8%8F-免责声明)

</div>

---

## ✨ 功能特色

### 🔍 扫描与判定

| 系统 | 描述 |
|---|---|
| **全区间扫描** | 任意 UID 区间 · 指定尾号（如 0901）· 全量模式 |
| **五级判定体系** | 极品神号 → 神号 → 注册机号 → 乱码名 → 普通，每级给出成因解释 |
| **乱码名启发式** | 辅音占比 · 字母数字混杂 · 常见英文/拼音排除 · 识别注册机批量账号 |
| **规律名识别** | 纯数字 · 同字符连发 · 重复块 · 键盘序列 · 字母表连续段 · 无元音回文 |
| **扩展字段采集** | 获赞 / 投稿数随扫随存，注册时间列位预留 |

### 💎 靓号规则

| 系统 | 描述 |
|---|---|
| **顺子** | 连续数字，如 1234567 · 54321 |
| **豹子** | 重复数字，如 1111111 · 88888 |
| **回文** | 正反相同，如 1234321 |
| **交替** | ABAB 交替，如 1212121 |
| **尾4 / 尾3** | 结尾规律（顺子尾 / 豹子尾 / AABB / ABAB） |
| **连号位数** | 3~7 自调 —— 5 = 标准靓号，4 = 小靓号 |
| **数字偏好** | 不带 4 / 不带 7 / 不含 0 / 额外排除 / 必含数字，自由组合 |

### 🛡 稳定保障

| 系统 | 描述 |
|---|---|
| **断点续扫** | 每个 UID 实时落盘，中断后重跑自动跳过已扫部分 |
| **失败自动重试** | `failed` 状态跨运行自动重新入队，永不静默丢号 |
| **风控识别** | 业务码 -352 / -412 / -799 与 HTTP 412/429 全识别 |
| **全局冷却** | 任一线程触发风控，全体线程同步阶梯退避（30~300s） |
| **会话预热** | 启动自动获取 buvid Cookie，降低 -352 拦截概率 |
| **屏幕常亮** | 安卓端扫描期间自动保持前台常亮 |

### 📤 数据导出

| 系统 | 描述 |
|---|---|
| **多格式** | CSV（Excel 直开）· TXT（制表符）· Excel(xlsx) · 纯 UID 列表 |
| **路径自选** | PC 端任意目录 · 安卓端直存 `下载/号海捞珍/` |

## 🏆 判定等级

| 判定 | 含义 |
|---|---|
| 🏆 **极品神号** | 三无（0级/0粉/0关注）+ 规范名 + 乱码名 —— 疑似注册机批量注册后遗弃，顶级收藏目标 |
| ✨ **神号** | 三无 + 规范昵称 —— 从未使用的干净号 |
| 🤖 **注册机号** | 乱码名 + 0 级，但已有少量粉丝/关注 —— 疑似批量生产半成品 |
| ❓ **乱码名** | 名字像机器生成，但账号已升级 |
| ─ **普通** | 不符合以上特征 |

> **名词小课堂**：**三无** = 0级 + 0粉 + 0关注（注册后从未使用）；**规范名** = 小写字母开头、3~18 位英文数字；**乱码名** = 辅音偏多、字母数字混杂、不含常见单词拼音（如 xk7f2m）。

## 🚀 快速上手

### 安装包（推荐）

前往 [**Releases**](../../releases) 下载：

| 平台 | 文件 | 说明 |
|---|---|---|
| 🪟 Windows | `号海捞珍-vX.X.X.exe` | 单文件免安装，双击即用 |
| 📱 Android | `号海捞珍.apk` | 允许未知来源后安装 |

### PC 桌面版

1. 「⚙️ 设置」配好区间、靓号规则、数字偏好
2. 「🚀 开始寻号」—— 进度、命中实时刷新，双击命中行直达 B 站主页
3. 「📦 战果」页统计 + 一键导出

### 安卓版

1. 安装 APK → 「⚙️ 设置」配好规则（并发建议 2~4）
2. 「🚀 寻号」页点开始 —— 屏幕常亮自动开启，保持前台即可
3. 「📦 战果」页导出 CSV 到手机下载目录

### 命令行

```
python bili_hunter_pro.py 1000000 2000000 0901 --threads 4
```

## 🛠 自行构建

<details>
<summary><b>🖥 桌面版 exe（Windows）</b></summary>

```
pip install PySide6 requests openpyxl pyinstaller
pyinstaller --onefile --windowed --name 号海捞珍 --icon "2233/icon.ico" ^
  --add-data "2233/1920x1080.jpg;assets" bili_hunter_gui.py
```
</details>

<details>
<summary><b>📱 安卓 APK（无需 Android Studio / Gradle）</b></summary>

准备工具链（约 120MB）：

| 组件 | 下载 | 放置 |
|---|---|---|
| Build-Tools r34 | [windows](https://dl.google.com/android/repository/build-tools_r34-windows.zip) / [linux](https://dl.google.com/android/repository/build-tools_r34-linux.zip) | `tools/android/` |
| Platform android-34 | [下载](https://dl.google.com/android/repository/platform-34-ext7_r02.zip) | `tools/android/` |
| JDK 11+ | [Adoptium](https://adoptium.net/) | PATH 可用 |

一键构建（自动生成签名密钥）：

```
cd android && bash build_apk.sh
```

管线：`aapt2 编译资源 → 链接 → javac → d8 → 注入 dex → zipalign → apksigner 签名`
产物：`android/dist/号海捞珍.apk`
</details>

## 🤖 CI 自动构建

| 触发 | 动作 |
|---|---|
| 推送到 `main` | 自动构建双端安装包 → Artifacts 可下载 |
| 推送 `v*` 标签 | 自动发布 Release 并附双端安装包 |
| 每次构建 | 先跑 Python 37 项 + JS 40 项测试，全绿才出包 |

> 建议在仓库 Settings → Secrets 中配置 `ANDROID_KEYSTORE_B64`
> （本地 `android/sign.keystore` 的 base64 编码），保证每次构建同一签名，
> 用户可覆盖安装升级。

## 🗂 项目结构

```
bili-treasure-hunter/
├── bili_hunter_gui.py        # PC 玻璃风界面（PySide6）
├── bili_hunter_pro.py        # PC 判定引擎 + CLI
├── tests/test_hunter.py      # Python 引擎测试
├── android/
│   ├── app/assets/           # 竖屏界面 + JS 判定引擎 + 竖屏壁纸
│   ├── app/src/              # Java WebView 壳（联网/存文件/常亮）
│   ├── test/engine.test.js   # JS 引擎测试
│   ├── build_apk.sh          # 无 Gradle 极简构建管线
│   └── 使用说明.md
├── 2233/                     # 壁纸与图标素材
└── .github/workflows/        # CI 双端自动构建
```

## 🧪 测试

| 套件 | 数量 | 覆盖 |
|---|---|---|
| Python 引擎 | 37 项 | 判定体系 · 乱码启发式 · 规律识别 · 尾号取模 · 断点语义 |
| JS 引擎 | 40+ 项 | 与 Python 逐条对齐 · 响应解析 · 靓号标签 · 排序 |
| GUI 端到端 | 45+ 项 | 扫描 worker · 数字偏好 · 筛选预设 · 三格式导出 · 复查 |
| CLI 端到端 | 6 阶段 | 真实网络扫描 · 失败重试 · 断点跳过 · 复查回填 |

## 🎨 素材版权

`2233/` 目录下的插画壁纸与图标为哔哩哔哩相关插画作品，**版权归原作者所有**，
本项目使用仅限学习研究，请勿商用。若您是权利人并要求移除，请提 Issue。

## ⚠️ 免责声明

本工具仅供技术研究与数据分析。请遵守 B 站用户协议与相关法律法规，
勿用于任何恶意用途（包括但不限于批量注册、账号盗取、骚扰他人）；
因使用本工具产生的一切后果由使用者自行承担。

## 📜 许可证

[MIT](LICENSE) © 号海捞珍 contributors
（`2233/` 素材除外，见上方版权说明）

## ⭐ 支持一下

如果这个项目对你有帮助，点一个 Star 就是免费开源项目最大的鼓励 ⭐

<a href="https://star-history.com/#uuapi/bili-treasure-hunter&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=uuapi/bili-treasure-hunter&type=Date&theme=dark"/>
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=uuapi/bili-treasure-hunter&type=Date"/>
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=uuapi/bili-treasure-hunter&type=Date"/>
 </picture>
</a>

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:00AEEC,100:FB7299&height=130&section=footer&text=%E6%84%BF%E4%BD%A0%E6%97%97%E5%BC%80%E5%BE%97%E8%83%9C%EF%BC%8C%E6%AF%8F%E5%8F%91%E7%9A%86%E4%B8%AD%E7%A5%9E%E5%8F%B7&fontSize=20&fontColor=ffffff&animation=blinking" width="100%"/>

</div>
