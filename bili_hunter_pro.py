#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilibili 靓号/神号/注册机号 UID 探测器（Pro 最终版）

= v2 引擎 + melodytik/bilibili_uid_checker 的乱码名判定逻辑 =

【账号判定体系】（CSV「判定」列，按价值从高到低）
  极品神号  : 三无(Lv0/0粉/0关注) + 规范昵称 + 乱码名 —— 最优目标
  神号      : 三无 + 规范昵称（小写字母开头、3~18位英数）
  注册机号  : 乱码名 + Lv.0 —— 疑似注册机批量注册的弃养号（melodytik 项目目标）
  乱码名    : 乱码名但等级>0
  (空)      : 普通账号

【乱码名判定】（来自 melodytik 项目，原样保留参数）
  1. 仅含小写字母和数字
  2. 必须同时含字母和数字
  3. 不能有 3 位连续数字
  4. 长度 6~12
  5. 辅音占比 > 0.60（随机字符串辅音偏多）
  6. 不含常见英文单词/拼音子串（见 COMMON_SUBSTRINGS）

【保留的引擎能力】
  - 靓号本地预筛（不联网）：顺子/豹子/回文/交替，--types 选择类型
  - 目标 = 靓号 ∪ 尾号，按价值排序：顺子 → 尾号 → 豹子 → 交替 → 回文
  - 多线程（--threads），每线程独立延迟，触发 -412 时全局同步冷却退避
  - 命中结果实时落盘 CSV + .done 断点续扫
  - 兼容升级：v2 旧 CSV（神号列）自动迁移为新判定列

用法：
    python bili_hunter_pro.py 1000000 9999999 0901 --types 顺子 --list-only
    python bili_hunter_pro.py 1000000 9999999 0901 --types 顺子 --threads 4
"""

import argparse
import csv
import os
import queue
import random
import re
import sys
import threading
import time

import requests

STRICT_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9]{2,17}$')
CSV_FIELDS = ["UID", "昵称", "关注数", "粉丝数", "账号等级", "标记", "判定",
              "注册时间", "获赞", "投稿数"]
OLD_CSV_FIELDS = ["UID", "昵称", "关注数", "粉丝数", "账号等级", "标记", "神号"]
PRETTY_TYPES = ('顺子', '豹子', '回文', '交替', '尾4', '尾3')
SCAN_ORDER = ('顺子', '尾号', '豹子', '交替', '回文', '尾4', '尾3')

# ---- melodytik/bilibili_uid_checker 的乱码名判定参数 ----
# 常见英文子串/拼音：用户名里包含这些说明可能是"正常人取的名字"
COMMON_SUBSTRINGS = [
    "the", "ing", "tion", "ment", "able", "ness", "ful", "less",
    "game", "love", "cool", "star", "fire", "dark", "blue", "king",
    "play", "hero", "wolf", "fox", "cat", "dog", "sky", "moon",
    "sun", "ice", "war", "pro", "max", "boy", "girl", "man",
    "fan", "god", "ace", "top", "big", "red", "hot", "old",
    "new", "one", "two", "day", "way", "eye", "her", "his",
    "you", "not", "all", "can", "out", "use", "how", "its",
    "may", "did", "get", "has", "him", "see", "now", "come",
    "than", "like", "just", "over", "know", "back", "only",
    "good", "some", "time", "very", "when", "with", "make",
    "hand", "high", "keep", "last", "long", "much", "own",
    "say", "she", "too", "any", "same", "tell", "each",
    "bilibili", "bili", "video", "anime", "music", "live",
    "chen", "wang", "zhang", "yang", "huang", "zhao", "zhou",
    "chun", "xiao", "ming", "hong", "feng", "jing", "ying",
    "qing", "long", "ping", "ling", "dong", "song", "tang",
]
VOWELS = set("aeiou")

_print_lock = threading.Lock()
_log_fh = None          # 运行日志文件句柄（--log 落盘）

session = requests.Session()
session.trust_env = False  # 不受系统代理干扰；显式 --proxy 仍然生效
session.headers.update({
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    'Referer': 'https://space.bilibili.com/',
})


def is_gibberish_name(name: str) -> bool:
    """乱码名判定（melodytik 逻辑）：识别注册机批量注册的随机用户名。"""
    if not re.fullmatch(r'[a-z0-9]+', name):
        return False
    if not (re.search(r'[a-z]', name) and re.search(r'\d', name)):
        return False
    if re.search(r'\d{3}', name):
        return False
    if not 6 <= len(name) <= 12:
        return False
    consonant_ratio = sum(1 for ch in name if ch not in VOWELS) / len(name)
    if consonant_ratio <= 0.60:
        return False
    low = name.lower()
    if any(sub in low for sub in COMMON_SUBSTRINGS):
        return False
    return True


def _digit_windows(n):
    """n 位连续数字窗口（升/降），用于规律名判定。"""
    asc = [''.join(str(d + i) for i in range(n)) for d in range(11 - n)]
    dsc = [''.join(str(d - i) for i in range(n)) for d in range(9, n - 2, -1)]
    return asc, dsc


def is_block_repeat(s, min_len=1):
    """整体是否为某个块的重复（如 abcabc = abc×3）。"""
    L = len(s)
    for bl in range(min_len, L // 2 + 1):
        if L % bl == 0 and s == s[:bl] * (L // bl):
            return True
    return False


KB_SEQUENCES = ('qwerty', 'qwer', 'rewq', 'asdf', 'fdsa', 'zxcv', 'xcvb',
                'vcxz', 'hjkl', 'qaz', 'wsx', 'edc', '1qaz', '2wsx')

# 昵称规律用【字母表】连续段（UID 目标生成才用数字窗口，勿混淆）
ASC_LETTERS = [''.join(chr(c + i) for i in range(4))
               for c in range(ord('a'), ord('w') + 1)]
DSC_LETTERS = [''.join(chr(c - i) for i in range(4))
               for c in range(ord('d'), ord('z') + 1)]


def pattern_reason(name):
    """昵称规律判定：返回违规原因字符串；无规律返回 None。"""
    n = name.lower()
    if n.isdigit():
        return '纯数字'
    if not re.fullmatch(r'[a-z0-9]+', n):
        return None
    if re.search(r'(.)\1{2,}', n):
        return '同字符连3+'
    if any(w in n for w in ASC_LETTERS + DSC_LETTERS):
        return '字母表连续4段'
    if any(k in n for k in KB_SEQUENCES):
        return '键盘序列'
    if is_block_repeat(n):
        return '整体重复块'
    letters = re.sub(r'[^a-z]', '', n)
    if len(letters) >= 4 and is_block_repeat(letters):
        return '去数字后字母重复块'
    if len(n) >= 6 and n == n[::-1] and not any(v in n for v in 'aeiou'):
        return '无元音回文'
    return None


def classify(is_shen: bool, is_gib: bool, level: int) -> str:
    """按优先级给出判定：极品神号 > 神号 > 注册机号 > 乱码名 > 普通。"""
    if is_shen and is_gib:
        return '极品神号'
    if is_shen:
        return '神号'
    if is_gib and level == 0:
        return '注册机号'
    if is_gib:
        return '乱码名'
    return ''


def verdict_for(card: dict) -> str:
    """根据 API 卡片数据给出判定。"""
    uname = card.get('name', '')
    level = (card.get('level_info') or {}).get('current_level', 0)
    fans = card.get('fans', 0)
    following = card.get('attention', 0)
    is_shen = (level == 0 and fans == 0 and following == 0
               and bool(STRICT_NAME_PATTERN.match(uname)))
    return classify(is_shen, is_gibberish_name(uname), level)


def _init_log_file(path):
    """开启文件日志（带时间戳），与控制台输出同步。"""
    global _log_fh
    try:
        _log_fh = open(path, 'a', encoding='utf-8')
    except OSError:
        _log_fh = None


def _ts():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def log(msg):
    with _print_lock:
        sys.stdout.write('\r' + ' ' * 120 + '\r')
        print(msg)
        sys.stdout.flush()
        if _log_fh:
            _log_fh.write(f'[{_ts()}] {msg}\n')
            _log_fh.flush()


def draw_progress(done, total, recorded, uid, rate):
    if total <= 0:
        return
    with _print_lock:
        eta = max(total - done, 0) * rate
        line = (f"⏳ {done / total * 100:6.2f}% ({done}/{total}) "
                f"记录:{recorded} 当前:{uid} {rate:4.1f}s/个 "
                f"剩余~{int(eta // 3600)}h{int(eta % 3600 // 60):02d}m")
        sys.stdout.write('\r' + line.ljust(110))
        sys.stdout.flush()
        if _log_fh:
            _log_fh.write(f'[{_ts()}] {line.strip()}\n')
            _log_fh.flush()


_query_reason = {'msg': '-'}


def _set_reason(msg):
    _query_reason['msg'] = msg


def session_warmup():
    """预热会话：访问 B 站主页获取 buvid 等风控 Cookie，显著降低 -352 拦截概率。"""
    try:
        session.get('https://www.bilibili.com/', timeout=6)
        log(f'🍪 会话预热完成，已持有 Cookie {len(session.cookies)} 枚')
    except Exception as e:
        log(f'⚠️ 会话预热失败: {str(e)[:60]}（不影响继续扫描）')


def query_uid(uid, timeout):
    """返回 (status, card)：ok / empty / blocked / error。"""
    url = f"https://api.bilibili.com/x/web-interface/card?mid={uid}&photo=true"
    try:
        resp = session.get(url, timeout=timeout)
    except requests.exceptions.Timeout:
        _set_reason('请求超时')
        return 'error', None
    except requests.exceptions.RequestException as e:
        _set_reason(f'连接异常({type(e).__name__})')
        return 'error', None

    if resp.status_code in (412, 429):
        _set_reason(f'HTTP {resp.status_code}')
        return 'blocked', None
    try:
        data = resp.json()
    except ValueError:
        _set_reason(f'HTTP {resp.status_code} 非 JSON 响应')
        return ('error', None) if resp.status_code >= 500 else ('blocked', None)

    code = data.get('code')
    if code == 0:
        payload = data.get('data') or {}
        card = payload.get('card') or {}
        if not card:
            return 'empty', None
        # 附加注册机判定所需的扩展字段
        card['_like_num'] = payload.get('like_num', '')
        card['_archive_count'] = payload.get('archive_count', '')
        return 'ok', card
    if code in (-412, -799, -352):
        _set_reason(f'风控拦截(业务码 {code})')
        return 'blocked', None
    if code in (-400, -402, -404):
        return 'empty', None
    _set_reason(f'未知业务码 {code}')
    return 'error', None


class RateCtl:
    """线程共享的节奏控制器：每线程独立延迟 + 全局风控冷却 + 自适应放大。"""

    def __init__(self, lo, hi):
        self.lo = lo
        self.hi = hi
        self.lock = threading.Lock()
        self.cool_until = 0.0
        self.consec = 0

    def wait_turn(self, stop_event):
        """请求前的等待：个人随机延迟 + 全局冷却。返回 False 表示要求停止。"""
        with self.lock:
            factor = 1.0 + 0.5 * min(self.consec, 6)
        if stop_event.wait(random.uniform(self.lo, self.hi) * factor):
            return False
        while True:
            with self.lock:
                remain = self.cool_until - time.monotonic()
            if remain <= 0:
                return True
            if stop_event.wait(min(remain, 1.0)):
                return False

    def report_blocked(self, attempt):
        """某线程触发风控：全局冷却，所有线程同步退避。"""
        with self.lock:
            self.consec += 1
            cool = min(30 + 30 * attempt + random.randint(0, 30), 300)
            self.cool_until = max(self.cool_until, time.monotonic() + cool)
        return cool

    def report_ok(self):
        with self.lock:
            self.consec = 0


def check_uid(uid, args, rate, stop_event):
    """带重试的单 UID 检查。返回 (status, card)：ok / empty / failed / stopped。"""
    for attempt in range(args.max_retries):
        if not rate.wait_turn(stop_event):
            return 'stopped', None
        status, card = query_uid(uid, args.timeout)
        if status in ('ok', 'empty'):
            rate.report_ok()
            return status, card
        if status == 'blocked':
            cool = rate.report_blocked(attempt)
            log(f"⚠️ UID {uid} 触发风控，全体冷却 {cool}s"
                f"（第 {attempt + 1}/{args.max_retries} 次尝试）")
        else:
            log(f'⚠️ UID {uid} 请求异常: {_query_reason["msg"]}'
                f'（第 {attempt + 1}/{args.max_retries} 次）')
            if stop_event.wait(random.uniform(3, 6)):
                return 'stopped', None
    return 'failed', None


def build_targets(start, end, suffix):
    """尾号目标：取模直接定位，返回 (uid序列, 总数)。"""
    if not suffix:
        rng = range(start, end + 1)
        return rng, len(rng)
    step = 10 ** len(suffix)
    mod = int(suffix)
    first = start + ((mod - start) % step)
    if first > end:
        return None, 0
    rng = range(first, end + 1, step)
    return rng, len(rng)


def build_matchers(min_run):
    """生成长度为 min_run 的顺子/豹子窗口正则。

    任何 >=min_run 的连号必然包含一个长度恰好为 min_run 的窗口，
    所以只需要匹配 min_run 长度的窗口。
    """
    asc = [''.join(str(d) for d in range(a, a + min_run))
           for a in range(0, 11 - min_run)]
    desc = [''.join(str(d) for d in range(a, a - min_run, -1))
            for a in range(min_run - 1, 10)]
    rep = [str(d) * min_run for d in range(10)]
    straight_re = re.compile('|'.join(map(re.escape, asc + desc)))
    rep_re = re.compile('|'.join(map(re.escape, rep)))
    return straight_re, rep_re


def collect_pretty(start, end, min_run, tail_rules=False):
    """本地遍历区间找靓号（纯 CPU，不联网），返回 [(uid, [标签...]), ...]。

    tail_rules=True 时追加尾部规律类型：
      尾4 = 末4位为顺子4/豹子4/AABB/ABAB
      尾3 = 末3位为三连豹子/顺子3段（升或降）
    """
    straight_re, rep_re = build_matchers(min_run)
    if tail_rules:
        asc4 = [''.join(str(d + i) for i in range(4)) for d in range(7)]
        dsc4 = [''.join(str(d - i) for i in range(4)) for d in range(9, 2, -1)]
        rep4 = [str(d) * 4 for d in range(10)]
        asc3 = [''.join(str(d + i) for i in range(3)) for d in range(8)]
        dsc3 = [''.join(str(d - i) for i in range(3)) for d in range(9, 1, -1)]
        rep3 = [str(d) * 3 for d in range(10)]
    total = end - start + 1
    out = []
    t0 = time.monotonic()
    for uid in range(start, end + 1):
        s = str(uid)
        tags = []
        if straight_re.search(s):
            tags.append('顺子')
        if rep_re.search(s):
            tags.append('豹子')
        if len(s) >= 5 and s == s[::-1]:
            tags.append('回文')
        if (len(s) >= 6 and s[0] != s[1]
                and s == (s[:2] * ((len(s) + 1) // 2))[:len(s)]):
            tags.append('交替')
        if tail_rules and len(s) >= 4:
            tail4, tail3 = s[-4:], s[-3:]
            if (tail4 in asc4 + dsc4 + rep4
                    or (tail4[0] == tail4[1] != tail4[2] == tail4[3])
                    or (tail4[0] == tail4[2] != tail4[1] == tail4[3])):
                tags.append('尾4')
            if tail3 in rep3 + asc3 + dsc3:
                tags.append('尾3')
        if tags:
            out.append((uid, tags))
        if (uid - start) % 500000 == 0 and uid != start:
            sys.stdout.write(f"\r🔍 本地筛选 {uid - start:,}/{total:,} "
                             f"已发现 {len(out):,} 个靓号 "
                             f"({time.monotonic() - t0:4.0f}s)  ")
            sys.stdout.flush()
    sys.stdout.write('\n')
    sys.stdout.flush()
    return out


def tag_base(tag):
    """'尾号0901' -> '尾号'，用于归类扫描顺序。"""
    return tag[:2] if tag.startswith('尾号') else tag


def order_targets(uids, mark_map):
    """按价值排序：顺子优先，其次 尾号→豹子→交替→回文；同类内按 UID 升序。"""
    def key(uid):
        tags = mark_map.get(uid, '')
        cat_idx = len(SCAN_ORDER)
        if tags:
            for t in tags.split('|'):
                base = tag_base(t)
                if base in SCAN_ORDER:
                    cat_idx = min(cat_idx, SCAN_ORDER.index(base))
        return (cat_idx, uid)
    return sorted(uids, key=key)


class ResultStore:
    def __init__(self, csv_path, failed_path):
        self.csv_path = csv_path
        self.failed_path = failed_path
        self._fh = None
        self._writer = None
        self._lock = threading.Lock()

    def append_row(self, row):
        with self._lock:
            if self._fh is None:
                exists = os.path.exists(self.csv_path) \
                    and os.path.getsize(self.csv_path) > 0
                enc = 'utf-8' if exists else 'utf-8-sig'
                self._fh = open(self.csv_path, 'a', newline='', encoding=enc)
                self._writer = csv.DictWriter(self._fh, fieldnames=CSV_FIELDS)
                if not exists:
                    self._writer.writeheader()
            self._writer.writerow(row)
            self._fh.flush()

    def append_failed(self, uid):
        with self._lock:
            with open(self.failed_path, 'a', encoding='utf-8') as f:
                f.write(f"{uid}\n")

    def close(self):
        with self._lock:
            if self._fh:
                self._fh.close()
                self._fh = None


class DoneLog:
    """已处理 UID 的追加日志，行格式 `uid` 或 `uid\\t状态`（同行后者覆盖前者）。

    状态: ok/empty = 已正常处理（续扫跳过）；failed = 重试耗尽（续扫自动重试）。
    兼容旧格式（纯 uid 行视为 ok）。
    """

    def __init__(self, path):
        self.path = path
        self.status = {}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if not parts or not parts[0]:
                        continue
                    try:
                        uid = int(parts[0])
                    except ValueError:
                        continue  # 忽略可能的半行
                    self.status[uid] = parts[1] if len(parts) > 1 else 'ok'
        self._fh = None
        self._lock = threading.Lock()

    @property
    def done(self):
        return self.status.keys()

    def add(self, uid, status='ok'):
        with self._lock:
            if self._fh is None:
                self._fh = open(self.path, 'a', encoding='utf-8')
            self.status[uid] = status
            self._fh.write(f'{uid}\t{status}\n')
            self._fh.flush()

    def close(self):
        with self._lock:
            if self._fh:
                self._fh.close()
                self._fh = None


def migrate_csv_if_needed(csv_path):
    """v2 旧 CSV（神号列）→ Pro 新 CSV（判定列）：按昵称/等级重新分类。"""
    if not os.path.exists(csv_path):
        return
    try:
        with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f))
    except OSError:
        return
    if not rows or rows[0] != OLD_CSV_FIELDS:
        return  # 已经是新格式或其他格式，不动
    log('🔧 检测到 v2 旧格式 CSV，自动迁移为「判定」列…')
    out = [CSV_FIELDS]
    for r in rows[1:]:
        if len(r) != len(OLD_CSV_FIELDS):
            continue
        uid, uname, following_s, fans_s, level_s, mark, _old = r

        def _int(s):
            try:
                return int(s)
            except (TypeError, ValueError):
                return -1
        level, fans, following = _int(level_s), _int(fans_s), _int(following_s)
        is_shen = (level == 0 and fans == 0 and following == 0
                   and bool(STRICT_NAME_PATTERN.match(uname)))
        verdict = classify(is_shen, is_gibberish_name(uname), max(level, 0))
        out.append([uid, uname, following_s, fans_s, level_s, mark, verdict])
    tmp = csv_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
        csv.writer(f).writerows(out)
    os.replace(tmp, csv_path)
    log(f'🔧 迁移完成：{len(out) - 1} 行已转换为判定列。')


def feeder(seq, q, stop_event, n_workers):
    """把目标序列喂进队列，结束后投放哨兵让工作线程退出。"""
    try:
        for uid in seq:
            if stop_event.is_set():
                break
            q.put(uid)
    finally:
        for _ in range(n_workers):
            try:
                q.put(None, timeout=5)
            except queue.Full:
                pass


def worker(wid, q, args, rate, store, done_log, mark_map, marks_provided,
           tag_stat, hits, shared, stat_lock, stop_event):
    while not stop_event.is_set():
        try:
            uid = q.get(timeout=2)
        except queue.Empty:
            continue
        if uid is None:
            return
        if uid in done_log.done and done_log.status.get(uid) != 'failed':
            continue  # 断点续扫：跳过已完成的 UID（failed 的自动重试）
        mark = mark_map.get(uid, '') if marks_provided else ''
        status, card = check_uid(uid, args, rate, stop_event)
        if status == 'stopped':
            continue
        with stat_lock:
            if status == 'ok':
                shared['exists'] += 1
                uname = card.get('name', '')
                level = (card.get('level_info') or {}).get('current_level', 0)
                fans = card.get('fans', 0)
                following = card.get('attention', 0)
                reg_str = ''
                try:
                    if int(card.get('regtime', 0)) > 0:
                        reg_str = time.strftime(
                            '%Y-%m-%d', time.localtime(int(card['regtime'])))
                except (TypeError, ValueError):
                    reg_str = ''
                is_shen = (level == 0 and fans == 0 and following == 0
                           and bool(STRICT_NAME_PATTERN.match(uname)))
                verdict = classify(is_shen, is_gibberish_name(uname), level)
                if verdict.endswith('神号'):
                    shared['shen'] += 1
                elif verdict == '注册机号':
                    shared['bot'] += 1
                elif verdict == '乱码名':
                    shared['gib'] += 1
                row = {'UID': uid, '昵称': uname, '关注数': following,
                       '粉丝数': fans, '账号等级': level, '标记': mark,
                       '判定': verdict, '注册时间': reg_str,
                       '获赞': card.get('_like_num', ''),
                       '投稿数': card.get('_archive_count', '')}
                store.append_row(row)
                for t in mark.split('|') if mark else ():
                    tag_stat[t][1] += 1
                    if verdict.startswith('神号'):
                        tag_stat[t][2] += 1
                if verdict:
                    hits.append(row)
                    if verdict in ('神号', '神号·乱码', '注册机号'):
                        log(f'🎯 UID:{uid} [{verdict}] 昵称:{uname} '
                            f'Lv.{level} 关注:{following} 粉丝:{fans} 标记[{mark}]')
            elif status == 'empty':
                shared['empty'] += 1
            elif status == 'failed':
                shared['failed'] += 1
                store.append_failed(uid)
                log(f'❌ UID {uid} 重试 {args.max_retries} 次仍失败，已记入失败清单')
            done_log.add(uid, status)
            shared['done'] += 1
            rate_now = (time.monotonic() - shared['t0']) \
                / max(shared['done'] - shared['skipped'], 1)
            draw_progress(shared['done'], shared['total'], shared['exists'],
                          uid, rate_now)


def parse_args():
    p = argparse.ArgumentParser(description="Bilibili 靓号/神号/注册机号 探测器（Pro）")
    p.add_argument('start', type=int, nargs='?', help='起始 UID')
    p.add_argument('end', type=int, nargs='?', help='结束 UID')
    p.add_argument('suffix', nargs='?', default='',
                   help='尾号后缀（如 0901）；留空且未关闭靓号模式时仅扫靓号')
    p.add_argument('--types', default='顺子,豹子,回文,交替',
                   help='靓号类型，逗号分隔（顺子,豹子,回文,交替），默认全部')
    p.add_argument('--min-run', type=int, default=5,
                   help='顺子/豹子最小连号长度（3-7，默认 5；越小目标越多）')
    p.add_argument('--tail-rules', action='store_true',
                   help='启用尾部规律：尾4(顺子4/豹子4/AABB/ABAB)+尾3(三连/顺子3段)')
    p.add_argument('--recheck-file', default='',
                   help='复查模式：重新查询指定结果文件(csv/txt)中的账号并输出变化清单')
    p.add_argument('--threads', type=int, default=3,
                   help='并发线程数（1-16，默认 3；越大越快但风控风险越高）')
    p.add_argument('--no-pretty', action='store_true',
                   help='关闭靓号筛选（配空尾号即为全量扫描）')
    p.add_argument('--list-only', action='store_true',
                   help='只列出目标清单与统计，不联网')
    p.add_argument('--yes', action='store_true', help='跳过超长任务确认')
    p.add_argument('--min-delay', type=float, default=2.0, help='每线程最小请求间隔秒数')
    p.add_argument('--max-delay', type=float, default=5.0, help='每线程最大请求间隔秒数')
    p.add_argument('--timeout', type=float, default=5.0, help='单次请求超时秒数')
    p.add_argument('--max-retries', type=int, default=4, help='单个 UID 最大尝试次数')
    p.add_argument('--proxy', default='', help='HTTP 代理，如 http://127.0.0.1:7890')
    p.add_argument('--out-dir', default='.', help='结果输出目录')
    p.add_argument('--no-resume', action='store_true', help='忽略断点，从头重新扫描')
    args = p.parse_args()

    while args.start is None or args.end is None:
        try:
            if args.start is None:
                args.start = int(input('⌨️ 请输入【开始】的 UID: ').strip())
            if args.end is None:
                args.end = int(input('⌨️ 请输入【结束】的 UID: ').strip())
            if args.start > args.end:
                print('❌ 结束 UID 必须大于或等于开始 UID，请重新输入！')
                args.start, args.end = None, None
                continue
            if not args.suffix:
                args.suffix = input('⌨️ 请输入【尾号后缀】(直接回车=仅靓号模式): ').strip()
        except ValueError:
            print('❌ 输入格式错误，UID 必须为纯数字！')
            args.start, args.end = None, None

    if args.suffix and not args.suffix.isdigit():
        p.error('尾号后缀必须是纯数字')
    if args.start > args.end:
        p.error('结束 UID 必须大于或等于开始 UID')
    if not 3 <= args.min_run <= 7:
        p.error('--min-run 需在 3~7 之间（太小会产生海量目标）')
    if not 1 <= args.threads <= 16:
        p.error('--threads 需在 1~16 之间')
    args.wanted_types = [t.strip() for t in args.types.replace('，', ',').split(',')
                         if t.strip()]
    bad = [t for t in args.wanted_types if t not in PRETTY_TYPES]
    if bad:
        p.error(f'未知靓号类型: {bad}（可选: {list(PRETTY_TYPES)}）')
    if args.min_delay > args.max_delay:
        args.min_delay, args.max_delay = args.max_delay, args.min_delay
    if args.max_retries < 1:
        args.max_retries = 1
    return args


def fmt_duration(seconds):
    h, m = int(seconds // 3600), int(seconds % 3600 // 60)
    return f'{h}小时{m:02d}分钟' if h else f'{m}分钟'


def run_recheck(args):
    """复查模式：重新查询结果文件中的所有账号，更新字段并输出变化清单。"""
    src = args.recheck_file
    if not os.path.exists(src):
        print(f'❌ 文件不存在: {src}')
        return
    _init_log_file(os.path.join(
        os.path.dirname(os.path.abspath(src)) or '.',
        f'runlog_recheck_{time.strftime("%Y%m%d_%H%M%S")}.log'))
    with open(src, encoding='utf-8-sig', newline='') as f:
        first = f.readline()
        delim = '\t' if '\t' in first else ','
        f.seek(0)
        raw = [[c.strip() for c in line]
               for line in csv.reader(f, delimiter=delim) if line]
    if len(raw) < 2:
        print('❌ 文件为空或无数据行')
        return
    header = raw[0]
    for extra in ('注册时间', '获赞', '投稿数'):
        if extra not in header:
            header.append(extra)
    data = [dict(zip(header, r + [''] * (len(header) - len(r))))
            for r in raw[1:] if r and r[0].strip().isdigit()]
    by_uid = {r['UID']: r for r in data}
    uids = [int(u) for u in by_uid]
    est = len(uids) * (args.min_delay + args.max_delay) / 2 / args.threads * 1.1
    print(f'📋 复查 {os.path.basename(src)}: {len(uids):,} 个账号 | '
          f'{args.threads} 线程 | 预计 {fmt_duration(est)}')

    session_warmup()

    rate = RateCtl(args.min_delay, args.max_delay)
    stop_event = threading.Event()
    q = queue.Queue()
    for u in uids:
        q.put(u)
    changes, miss, gone, done_cnt, lock = [], [], [0], [0], threading.Lock()

    def w():
        while not stop_event.is_set():
            try:
                uid = q.get(timeout=2)
            except queue.Empty:
                return
            status, card = check_uid(uid, args, rate, stop_event)
            with lock:
                done_cnt[0] += 1
                row = by_uid[str(uid)]
                if status == 'empty':
                    gone[0] += 1
                    changes.append((uid, ['⚠️ 账号已无资料(可能注销)']))
                    continue
                if status != 'ok':
                    miss.append(uid)
                    continue
                uname = card.get('name', '')
                level = (card.get('level_info') or {}).get('current_level', 0)
                fans = card.get('fans', 0)
                fol = card.get('attention', 0)
                diffs = []
                if row['昵称'] != uname:
                    diffs.append(f"改名: {row['昵称']} -> {uname}")
                    row['昵称'] = uname
                if row['账号等级'] != str(level):
                    diffs.append(f"等级: Lv.{row['账号等级']} -> Lv.{level}")
                    row['账号等级'] = str(level)
                if row['粉丝数'] != str(fans):
                    diffs.append(f"粉丝: {row['粉丝数']} -> {fans}")
                    row['粉丝数'] = str(fans)
                if row['关注数'] != str(fol):
                    diffs.append(f"关注: {row['关注数']} -> {fol}")
                    row['关注数'] = str(fol)
                reg_str = ''
                try:
                    if int(card.get('regtime', 0)) > 0:
                        reg_str = time.strftime(
                            '%Y-%m-%d', time.localtime(int(card['regtime'])))
                except (TypeError, ValueError):
                    reg_str = ''
                if reg_str and row.get('注册时间', '') != reg_str:
                    diffs.append(f"注册时间: {row.get('注册时间', '空')} -> {reg_str}")
                row['注册时间'] = reg_str or row.get('注册时间', '')
                row['获赞'] = str(card.get('_like_num', '')) or row.get('获赞', '')
                row['投稿数'] = str(card.get('_archive_count', '')) or row.get('投稿数', '')
                is_shen = (level == 0 and fans == 0 and fol == 0
                           and bool(STRICT_NAME_PATTERN.match(uname)))
                new_verdict = classify(is_shen, is_gibberish_name(uname), level)
                if new_verdict != row['判定']:
                    diffs.append(f"判定: {row['判定'] or '空'} -> {new_verdict or '空'}")
                    row['判定'] = new_verdict
                if diffs:
                    changes.append((uid, diffs))
                    log(f'🔄 UID {uid}: ' + ' | '.join(diffs))
                if done_cnt[0] % 500 == 0:
                    log(f'⏳ 复查进度 {done_cnt[0]}/{len(uids)}')

    ts = [threading.Thread(target=w, daemon=True) for _ in range(args.threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    tmp = src + '.tmp'
    with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f, delimiter=delim)
        wr.writerow(header)
        for r in data:
            wr.writerow([r.get(h, '') for h in header])
    os.replace(tmp, src)

    base, _ = os.path.splitext(src)
    chg_path = base + '_变化.txt'
    with open(chg_path, 'w', encoding='utf-8-sig') as f:
        for uid, diffs in changes:
            f.write(f'UID {uid}: ' + ' | '.join(diffs) + '\n')

    print('=' * 65)
    print(f' 🔄 复查完成！检查 {done_cnt[0]:,} | 有变化 {len(changes) - gone[0]:,} | '
          f'已注销 {gone[0]:,} | 查询失败 {len(miss)}')
    print(f' 📁 变化清单: {chg_path}')
    print(f' 📁 数据已更新: {src}')


def main():
    args = parse_args()
    if args.proxy:
        session.proxies.update({'http': args.proxy, 'https': args.proxy})

    if args.recheck_file:
        run_recheck(args)
        return

    pretty_enabled = not args.no_pretty
    wanted = set(args.wanted_types)
    pretty_pairs = collect_pretty(args.start, args.end, args.min_run,
                                  args.tail_rules) if pretty_enabled else []
    if pretty_pairs:
        # 只保留用户选择的类型
        pretty_pairs = [(u, [t for t in tags if t in wanted])
                        for u, tags in pretty_pairs]
        pretty_pairs = [(u, tags) for u, tags in pretty_pairs if tags]

    # ---- 组装目标与标记 ----
    target_set = {uid for uid, _ in pretty_pairs}
    mark_map = {uid: '|'.join(tags) for uid, tags in pretty_pairs}
    if args.suffix:
        sfx_rng, _ = build_targets(args.start, args.end, args.suffix)
        sfx_tag = f'尾号{args.suffix}'
        for uid in sfx_rng:
            target_set.add(uid)
            mark_map[uid] = f'{mark_map[uid]}|{sfx_tag}' if uid in mark_map else sfx_tag

    if target_set:
        targets = order_targets(target_set, mark_map)
        marks_provided = True
    elif not pretty_enabled:
        targets = None  # 全量模式：直接用 range
        marks_provided = False
    else:
        print('❌ 没有任何目标（区间内未找到所选类型的靓号且未指定尾号），程序退出。')
        return
    total = len(targets) if targets is not None else args.end - args.start + 1
    if total == 0:
        print('❌ 当前区间内没有符合条件的目标，程序退出。')
        return
    iter_targets = targets if targets is not None \
        else range(args.start, args.end + 1)

    # 各分类目标数预统计
    tag_stat = {}
    if marks_provided:
        for uid in targets:
            for t in mark_map[uid].split('|'):
                tag_stat.setdefault(t, [0, 0, 0])[0] += 1  # [目标, 存在, 神号]
    all_tags = set()
    if marks_provided:
        for uid in targets:
            all_tags.update(tag_base(t) for t in mark_map[uid].split('|'))
    order_msg = ' → '.join(c for c in SCAN_ORDER if c in all_tags) \
        if marks_provided else 'UID 升序'

    # ---- 文件名 ----
    os.makedirs(args.out_dir, exist_ok=True)
    name = 'bili_scan'
    if args.suffix:
        name += f'_end{args.suffix}'
    if pretty_enabled:
        name += '_pretty'
    name += f'_{args.start}_{args.end}'
    csv_path = os.path.join(args.out_dir, name + '.csv')
    done_path = os.path.join(args.out_dir, name + '.done')
    failed_path = os.path.join(args.out_dir, name + '.failed.txt')

    # ---- 清单模式：不联网 ----
    if args.list_only:
        print('=' * 65)
        print(' 📋 目标清单（--list-only，未联网）')
        print('=' * 65)
        if marks_provided:
            for t in sorted(tag_stat):
                a = tag_stat[t][0]
                print(f'  {t:<12} 目标 {a:>8,} 个')
            print('-' * 65)
            print(f'  合计（去重后）：{total:,} 个')
            print(f'  扫描顺序：{order_msg} | 线程数：{args.threads}')
            for label, chunk in (('前 10 个', targets[:10]), ('后 10 个', targets[-10:])):
                print(f'  {label}：')
                for u in chunk:
                    print(f'    {u}  [{mark_map.get(u, "")}]')
        else:
            print(f'  全量扫描：{total:,} 个')
        est = total * (args.min_delay + args.max_delay) / 2 * 1.1 / args.threads
        print(f'  ⏱️ 预计联网耗时：约 {fmt_duration(est)}（{args.threads} 线程 × 平均 '
              f'{(args.min_delay + args.max_delay) / 2:.1f}s/个）')
        return

    _init_log_file(os.path.join(
        args.out_dir, f'runlog_{name}_{time.strftime("%Y%m%d_%H%M%S")}.log'))

    est = total * (args.min_delay + args.max_delay) / 2 * 1.1 / args.threads
    if est > 24 * 3600 and not args.yes:
        print(f'⚠️ 预计耗时约 {fmt_duration(est)}，确认请追加 --yes 参数。')
        return

    # ---- 断点 ----
    resuming = not args.no_resume and os.path.exists(done_path)
    if not resuming:
        for p_ in (csv_path, done_path, failed_path):
            if os.path.exists(p_):
                os.remove(p_)
    migrate_csv_if_needed(csv_path)  # 兼容 v2 旧格式
    done_log = DoneLog(done_path)
    skipped = sum(1 for u in iter_targets
                  if u in done_log.done and done_log.status.get(u) != 'failed')
    if skipped >= total:
        done_log.close()
        print(f'✅ 断点显示本任务已全部扫描完成（{total}/{total}）。'
              f'如需重扫请加 --no-resume。')
        return

    suffix_msg = f'尾号【{args.suffix}】' if args.suffix else ''
    mode_msg = f"靓号({'/'.join(args.wanted_types)})" if pretty_enabled else '全量'
    print('=' * 65)
    print('   Bilibili 靓号/神号/注册机号 探测器 Pro（多线程版）')
    print('=' * 65)
    print(f'📢 目标：{args.start} ~ {args.end} | 模式：{mode_msg} {suffix_msg}')
    print(f'📊 待扫描：{total:,} 个 | {args.threads} 线程 × '
          f'{args.min_delay}~{args.max_delay}s | 预计 {fmt_duration(est)}')
    print(f'🔁 扫描顺序：{order_msg}')
    print('🎯 判定体系：神号·乱码 / 神号 / 注册机号 / 乱码名')
    if args.proxy:
        print(f'🌐 代理：{args.proxy}')
    if resuming:
        print(f'♻️ 检测到断点，跳过已完成的 {skipped:,} 个，继续扫描…')
    print(f'📁 结果文件：{csv_path}')
    print('-' * 65)

    session_warmup()

    # ---- 多线程启动 ----
    q = queue.Queue(maxsize=200)
    stop_event = threading.Event()
    stat_lock = threading.Lock()
    rate = RateCtl(args.min_delay, args.max_delay)
    store = ResultStore(csv_path, failed_path)
    hits = []
    shared = {'done': skipped, 'exists': 0, 'empty': 0, 'failed': 0,
              'shen': 0, 'bot': 0, 'gib': 0,
              'total': total, 'skipped': skipped, 't0': time.monotonic()}

    threads = []
    feeder_t = threading.Thread(
        target=feeder, args=(iter_targets, q, stop_event, args.threads),
        daemon=True)
    feeder_t.start()
    for i in range(args.threads):
        t = threading.Thread(
            target=worker,
            args=(i + 1, q, args, rate, store, done_log, mark_map,
                  marks_provided, tag_stat, hits, shared, stat_lock,
                  stop_event),
            daemon=True)
        t.start()
        threads.append(t)

    interrupted = False
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        interrupted = True
        stop_event.set()
        log('⌨️ 手动中断，等待线程退出（已扫描结果均已保存）…')
    finally:
        stop_event.set()
        deadline = time.monotonic() + 10
        for t in threads:
            t.join(timeout=max(0.1, deadline - time.monotonic()))
        store.close()
        done_log.close()
        sys.stdout.write('\n\n')
        sys.stdout.flush()

    # ---- 汇总 ----
    print('=' * 65)
    state_msg = '扫描中断' if interrupted else '扫描结束'
    processed = shared['done'] - skipped
    normal = shared['exists'] - shared['shen'] - shared['bot'] - shared['gib']
    print(f' 🏁 {state_msg}！目标 {total:,} | 本次处理 {processed:,} | '
          f'存在 {shared["exists"]:,} | 无资料 {shared["empty"]:,} | '
          f'失败 {shared["failed"]:,}')
    print(f' 🎯 判定分布：神号类 {shared["shen"]} | 注册机号 {shared["bot"]} | '
          f'乱码名 {shared["gib"]} | 普通 {normal:,}')
    print('=' * 65)
    if marks_provided:
        print(f"{'标记':<12}\t{'目标':>10}\t{'存在':>10}\t{'神号类':>8}")
        print('-' * 65)
        for t in sorted(tag_stat):
            a, b, c = tag_stat[t]
            print(f'{t:<12}\t{a:>10,}\t{b:>10,}\t{c:>8}')
    if hits:
        print('-' * 65)
        print(f"{'UID':<12}\t{'昵称':<15}\t{'等级':<6}\t{'关注':<6}\t{'粉丝':<6}\t判定\t标记")
        for r in sorted(hits, key=lambda x: x['UID']):
            print(f"{r['UID']:<12}\t{r['昵称']:<15}\tLv.{r['账号等级']:<4}"
                  f"\t{r['关注数']:<6}\t{r['粉丝数']:<6}\t{r['判定']}\t{r['标记']}")
    if os.path.exists(failed_path):
        print(f'📄 失败清单（可稍后单独复查）：{failed_path}')
    print(f'📁 结果 CSV（完整数据以文件为准）：{csv_path}')
    if interrupted:
        print('💡 再次运行同一命令即可从断点继续扫描。')


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    main()
