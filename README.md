# 号海捞珍

> 在号海之中，捞取属于你的珍宝 —— B 站 UID 寻号、判定与筛选工具（PC 桌面版 + 安卓版）

扫描 B 站 UID 区间，自动判定并筛出「三无神号 / 靓号 / 注册机账号」。
判定引擎在电脑端（Python）与安卓端（JavaScript）为同一套规则的两种实现。

## ✨ 功能

- **全区间扫描**：任意 UID 区间，支持指定尾号（如 0901）
- **靓号类型**：顺子(1234567)、豹子(1111111)、回文(1234321)、交替(1212121)、尾4/尾3
- **连号位数**：5 = 标准靓号，4 = 小靓号
- **数字偏好**：不带 4 / 不带 7 / 不含 0 / 额外排除 / 必含数字，自由组合
- **判定体系**：极品神号 > 神号 > 注册机号 > 乱码名 > 普通（详见下表）
- **断点续扫**：中途停止自动记进度，失败自动重试，数据不丢
- **风控应对**：随机延迟 + 全局冷却退避 + 会话预热（Cookie）+ -352/-412 识别

### 判定等级

| 判定 | 含义 |
|---|---|
| 🏆 极品神号 | 三无（0级/0粉/0关注）+ 规范名 + 乱码名 —— 疑似注册机批量注册后遗弃，顶级目标 |
| ✨ 神号 | 三无 + 规范昵称 |
| 🤖 注册机号 | 乱码名 + 0 级，但已有少量粉丝/关注 |
| ❓ 乱码名 | 乱码名但账号已升级 |
| ─ 普通 | 其他 |

## 🖥 桌面版（Windows）

```
pip install PySide6 requests openpyxl
python bili_hunter_gui.py
```

打包单文件 exe：

```
pip install pyinstaller
pyinstaller --onefile --windowed --name 号海捞珍 bili_hunter_gui.py
```

仅命令行扫描：

```
python bili_hunter_pro.py 1000000 2000000 0901 --threads 4
```

## 📱 安卓版

无需 Gradle / Android Studio，用 `build-tools + javac + apksigner` 极简管线构建签名 APK：

```
# 1. 准备工具链（约 120MB）
#    - Android build-tools r34 → tools/android/android-14/
#    - Platform android-34 的 android.jar → tools/android/android-34/android.jar
# 2. 一键构建（自动生成签名密钥）
cd android && bash build_apk.sh
# 产物: android/dist/号海捞珍.apk
```

详细安装与使用见 [android/使用说明.md](android/使用说明.md)。

## ⚙️ 引擎说明

- **数据源**：B 站公开用户卡片接口（无需登录）
- **判定引擎**：乱码名启发式（辅音占比 / 常见词排除）、规律名识别（纯数字、重复块、键盘序列、字母表连续段、无元音回文）
- **节奏控制**：每线程随机延迟；触发 -352/-412/-799 风控时全体线程同步冷却退避
- **测试**：`python tests/test_hunter.py`（PC 判定引擎 37 项）、`node android/test/engine.test.js`（安卓判定引擎 40 项）

## 🎨 素材版权

`2233/` 目录下的壁纸与图标为哔哩哔哩站相关插画作品，**版权归原作者所有**，
本项目使用仅限学习研究，请勿商用。若您是权利人并要求移除，请提 Issue。

## ⚠️ 免责声明

本工具仅供技术研究与数据分析。请遵守 B 站用户协议与相关法律法规，
勿用于任何恶意用途（包括但不限于批量注册、账号盗取、骚扰他人）；
因使用本工具产生的一切后果由使用者自行承担。

## License

MIT
