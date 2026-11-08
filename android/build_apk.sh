#!/usr/bin/env bash
# 号海捞珍 — 无 Gradle 极简 APK 构建管线
# 用法: bash build_apk.sh   （需要 JDK + tools/android 内的 build-tools/platform）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"           # .../bili/android
SDK="$(cd "$HERE/../tools/android" && pwd)"     # .../bili/tools/android
BT="$SDK/android-14"                            # build-tools 34
AJ="$SDK/android-34/android.jar"                # android.jar (API 34)
APP="$HERE/app"
WORK="$HERE/build"
OUT="$HERE/dist"

# 跨平台：按文件存在性检测（Windows 有 .exe/.bat，Linux 无后缀）
if [ -f "$BT/apksigner.bat" ]; then
  AAPT2="$BT/aapt2.exe"
  ZIPALIGN="$BT/zipalign.exe"
  APKSIGNER="$BT/apksigner.bat"
else
  AAPT2="$BT/aapt2"
  ZIPALIGN="$BT/zipalign"
  APKSIGNER="$BT/apksigner"
  chmod +x "$AAPT2" "$ZIPALIGN" "$APKSIGNER" 2>/dev/null || true
fi

echo "=== 1/6 编译资源 (aapt2 compile) ==="
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK/classes" "$WORK/dex" "$OUT"
"$AAPT2" compile --dir "$APP/res" -o "$WORK/res.zip"

echo "=== 2/6 链接资源 (aapt2 link) ==="
"$AAPT2" link -o "$WORK/base.apk" \
  -I "$AJ" \
  --manifest "$APP/AndroidManifest.xml" \
  -A "$APP/assets" \
  --min-sdk-version 24 --target-sdk-version 34 \
  --auto-add-overlay \
  "$WORK/res.zip"

echo "=== 3/6 编译 Java (javac) ==="
cd "$HERE"
find app/src -name '*.java' > "$WORK/sources.txt"
javac --release 8 -classpath "$AJ" -d "$WORK/classes" @build/sources.txt

echo "=== 4/6 转 DEX (d8) ==="
java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 --release \
  --lib "$AJ" --output "$WORK/dex" $(find "$WORK/classes" -name '*.class')

echo "=== 5/6 打包对齐 (zip + zipalign) ==="
python - "$WORK/base.apk" "$WORK/dex/classes.dex" <<'PYEOF'
import sys, zipfile, shutil
base, dex = sys.argv[1], sys.argv[2]
import os
print('base.apk 大小:', os.path.getsize(base), '前4字节:', open(base,'rb').read(4))
tmp = base + '.tmp'
with zipfile.ZipFile(base) as zin, zipfile.ZipFile(tmp, 'w') as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        comp = zipfile.ZIP_STORED if item.filename == 'resources.arsc' else zipfile.ZIP_DEFLATED
        zout.writestr(item.filename, data, compress_type=comp)
dex_bytes = open(dex, 'rb').read()
with zipfile.ZipFile(tmp, 'a', compression=zipfile.ZIP_DEFLATED) as zout:
    zout.writestr('classes.dex', dex_bytes)
shutil.move(tmp, base)
print('classes.dex 已注入')
PYEOF
"$ZIPALIGN" -f -p 4 "$WORK/base.apk" "$WORK/aligned.apk"

echo "=== 6/6 签名 (apksigner) ==="
KS="$HERE/sign.keystore"
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias haohai -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass haohai123 -keypass haohai123 \
    -dname "CN=HaoHaiLaoZhen, O=HaoHai" > /dev/null 2>&1
  echo "已生成签名密钥 sign.keystore"
fi
"$APKSIGNER" sign --ks "$KS" --ks-pass pass:haohai123 \
  --out "$OUT/号海捞珍.apk" "$WORK/aligned.apk"
"$APKSIGNER" verify --print-certs "$OUT/号海捞珍.apk" | head -4

echo "=== 完成 ==="
ls -la "$OUT/"
echo "APK: $OUT/号海捞珍.apk"
