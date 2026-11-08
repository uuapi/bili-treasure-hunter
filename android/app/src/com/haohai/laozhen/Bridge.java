package com.haohai.laozhen;

import android.app.Activity;
import android.content.ContentValues;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** JS 桥：联网取数 / 文件导出 / 屏幕常亮 / 提示。 */
public class Bridge {
    private final Activity act;

    Bridge(Activity a) {
        act = a;
    }

    /** 异步取数：完成后通过 evaluateJavascript 回调 window.__httpDone(tag, result)。 */
    @JavascriptInterface
    public void httpGetAsync(final String tag, final String url) {
        new Thread(() -> {
            final String result = httpGet(url);
            act.runOnUiThread(() -> {
                if (act.isFinishing() || act.isDestroyed()) {
                    return;
                }
                String js = result.replace("\\", "\\\\")
                        .replace("'", "\\'")
                        .replace("\n", "\\n")
                        .replace("\r", "");
                web_eval("window.__httpDone('" + tag + "', '" + js + "')");
            });
        }, "hh-http-" + tag).start();
    }

    private String httpGet(String url) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(8000);
            c.setReadTimeout(12000);
            c.setRequestProperty("User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
            c.setRequestProperty("Referer", "https://space.bilibili.com/");
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            StringBuilder sb = new StringBuilder();
            if (in != null) {
                BufferedReader r = new BufferedReader(
                        new InputStreamReader(in, StandardCharsets.UTF_8));
                String line;
                while ((line = r.readLine()) != null) {
                    sb.append(line);
                }
                in.close();
            }
            return "HTTP:" + code + "\n" + sb;
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName() + ":" + e.getMessage();
        }
    }

    private void web_eval(final String js) {
        final WebView w = getWebView();
        if (w != null) {
            act.runOnUiThread(() -> w.evaluateJavascript(js, null));
        }
    }

    private WebView getWebView() {
        try {
            java.lang.reflect.Field f = act.getClass().getDeclaredField("web");
            f.setAccessible(true);
            return (WebView) f.get(act);
        } catch (Exception e) {
            return null;
        }
    }

    /** 导出文件到公共下载目录（API 29+）或应用外部目录。 */
    @JavascriptInterface
    public String saveFile(String name, String content) {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 29) {
                ContentValues v = new ContentValues();
                v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                v.put(MediaStore.MediaColumns.MIME_TYPE,
                        name.endsWith(".csv") ? "text/csv" : "text/plain");
                v.put(MediaStore.MediaColumns.RELATIVE_PATH,
                        Environment.DIRECTORY_DOWNLOADS + "/号海捞珍");
                Uri uri = act.getContentResolver().insert(
                        MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                OutputStream os = act.getContentResolver().openOutputStream(uri);
                os.write(content.getBytes(StandardCharsets.UTF_8));
                os.close();
                return "已保存到 下载/号海捞珍/" + name;
            }
            File d = new File(act.getExternalFilesDir(null), "export");
            if (!d.exists()) {
                d.mkdirs();
            }
            File f = new File(d, name);
            FileOutputStream os = new FileOutputStream(f);
            os.write(content.getBytes(StandardCharsets.UTF_8));
            os.close();
            return "已保存到 " + f.getAbsolutePath();
        } catch (Exception e) {
            return "保存失败: " + e.getMessage();
        }
    }

    /** 扫描期间保持屏幕常亮。 */
    @JavascriptInterface
    public void keepAwake(final boolean on) {
        act.runOnUiThread(() -> {
            Window w = act.getWindow();
            if (on) {
                w.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            } else {
                w.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            }
        });
    }

    /** 竖屏壁纸转 base64 数据 URL（asset 直载被拒时的兜底通道）。 */
    @JavascriptInterface
    public String wallpaperBase64() {
        try {
            InputStream in = act.getAssets().open("978x2160.jpg");
            java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            in.close();
            return "data:image/jpeg;base64,"
                    + android.util.Base64.encodeToString(bos.toByteArray(),
                            android.util.Base64.NO_WRAP);
        } catch (Exception e) {
            return "";
        }
    }

    @JavascriptInterface
    public void toast(String msg) {
        act.runOnUiThread(() ->
                Toast.makeText(act, msg, Toast.LENGTH_SHORT).show());
    }
}
