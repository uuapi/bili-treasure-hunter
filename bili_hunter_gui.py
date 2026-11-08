#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B站靓号猎手 BiliHunter — 桌面版（PySide6 GUI，复用 bili_hunter_pro 引擎）"""
import os
import re
import sys
import csv
import time
import queue
import tempfile
import threading
from types import SimpleNamespace
from collections import deque

# ---- windowed 模式下 sys.stdout 可能为 None，必须先重定向再 import 引擎 ----
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
    else os.path.dirname(os.path.abspath(__file__))
os.makedirs(APP_DIR, exist_ok=True)
try:
    _out = open(os.path.join(APP_DIR, 'gui_stdout.log'), 'a', encoding='utf-8')
except OSError:
    import tempfile
    _out = open(os.path.join(tempfile.gettempdir(), 'bilihunter_stdout.log'),
                'a', encoding='utf-8')
sys.stdout = _out
sys.stderr = _out

import bili_hunter_pro as eng
from PySide6.QtCore import Qt, QThread, Signal, QPointF
from PySide6.QtGui import (QFont, QPainter, QColor, QPixmap, QIcon, QBrush,
                           QPen)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QGroupBox, QFrame, QListWidget, QStackedWidget, QMessageBox,
    QHeaderView, QScrollArea)

FIELDS = eng.CSV_FIELDS
APP_TITLE = '号海捞珍'


def asset(name):
    """定位资源文件：兼容 PyInstaller 解包目录(含 assets 子目录)与源码目录。"""
    meipass = getattr(sys, '_MEIPASS', '')
    bases = []
    for b in (meipass, APP_DIR):
        if b:
            bases += [b, os.path.join(b, 'assets')]
    bases.append(os.path.join(APP_DIR, '2233'))
    for b in bases:
        p = os.path.join(b, name)
        if os.path.exists(p):
            return p
    return os.path.join(APP_DIR, name)


def _ui_cache_dir():
    """可写的界面缓存目录（勾选框图标等），exe 目录只读时退回 temp。"""
    d = os.path.join(APP_DIR, '.ui_assets')
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, '.w')
        with open(probe, 'w') as f:
            f.write('1')
        os.remove(probe)
        return d
    except OSError:
        d = os.path.join(tempfile.gettempdir(), 'bilihunter_ui')
        os.makedirs(d, exist_ok=True)
        return d


def _gen_check_images(d):
    """程序绘制勾选框图标：未选=玻璃方框 / 悬停=粉框 / 选中=粉底白勾。"""
    specs = {
        'off':   (QColor(255, 255, 255, 205), QColor(31, 36, 48, 90), None),
        'hover': (QColor(255, 255, 255, 235), QColor(251, 114, 153, 235), None),
        'on':    (QColor(251, 114, 153, 255), QColor(224, 95, 136, 235),
                  QColor(255, 255, 255)),
    }
    paths = {}
    for key, (fill, border, tick) in specs.items():
        pm = QPixmap(40, 40)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(border, 3))
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(4, 4, 32, 32, 11, 11)
        if tick is not None:
            p.setPen(QPen(tick, 4.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPolyline([QPointF(13, 21), QPointF(18.5, 26.5),
                            QPointF(28, 13.5)])
        p.end()
        path = os.path.join(d, f'cb_{key}.png')
        pm.save(path)
        paths[key] = path.replace('\\', '/')
    for key, direction in (('up', -1), ('down', 1)):
        pm = QPixmap(40, 40)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(31, 36, 48, 175), 5, Qt.SolidLine,
                      Qt.RoundCap, Qt.RoundJoin))
        cy = 20 + direction * 3
        p.drawPolyline([QPointF(13, cy - direction * 7),
                        QPointF(20, cy), QPointF(27, cy - direction * 7)])
        p.end()
        path = os.path.join(d, f'arrow_{key}.png')
        pm.save(path)
        paths[f'arrow_{key}'] = path.replace('\\', '/')
    return paths


def build_qss():
    """构建玻璃拟态样式表。必须在 QApplication 创建之后调用
    （勾选框图标需要 QPixmap/QPainter）。"""
    ind = _gen_check_images(_ui_cache_dir())
    return """
QWidget { background: transparent; color:#1f2430; font-size:13px; }
QScrollArea { background:transparent; border:none; }
QScrollArea > QWidget > QWidget { background:transparent; }
QFrame#panel { background: rgba(255,255,255,215); border:1px solid rgba(255,255,255,240);
    border-radius:14px; }
QWidget#sidebar { background: rgba(255,255,255,225); border:1px solid rgba(255,255,255,240);
    border-radius:14px; }
QFrame#subcard { background: rgba(255,255,255,200); border:1px solid rgba(255,255,255,215);
    border-radius:10px; }
QFrame#card { background: rgba(255,255,255,205); border:1px solid rgba(255,255,255,220);
    border-radius:10px; }
QLabel#statuspill { background: rgba(255,255,255,232); border:1px solid rgba(255,255,255,245);
    border-radius:16px; padding:7px 16px; color:#1f2430; }
QLabel#cardtitle { color:#e05f88; font-weight:700; background:transparent; }
QLabel#title { font-size:21px; font-weight:700; color:#e05f88; background:transparent; }
QLabel#subtitle { color:#5a6470; font-size:11px; background:transparent; }
QListWidget { background:transparent; border:none; outline:0; }
QListWidget::item { color:#2a313c; padding:13px 14px; border-radius:9px; margin:3px 4px; }
QListWidget::item:hover { background:rgba(255,255,255,120); }
QListWidget::item:selected { background:rgba(251,114,153,235); color:#fff; font-weight:600; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background:rgba(255,255,255,238); color:#1f2430; border:1px solid rgba(31,36,48,55);
    border-radius:6px; padding:4px 7px; selection-background-color:#00AEEC;
    selection-color:#fff; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color:#FB7299; }
QSpinBox, QDoubleSpinBox { padding-right:22px; }
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin:border; subcontrol-position:top right; width:18px;
    border-left:1px solid rgba(31,36,48,45); background:rgba(255,255,255,170); }
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin:border; subcontrol-position:bottom right; width:18px;
    border-left:1px solid rgba(31,36,48,45); background:rgba(255,255,255,170); }
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background:rgba(251,114,153,130); }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(@ARROW_UP); width:9px; height:9px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(@ARROW_DOWN); width:9px; height:9px; }
QComboBox QAbstractItemView { background:rgba(255,255,255,246); color:#1f2430;
    selection-background-color:#FB7299; selection-color:#fff;
    border:1px solid rgba(255,255,255,160); }
QPushButton { background:#FB7299; color:#fff; border:none; border-radius:6px;
    padding:7px 16px; font-weight:600; }
QPushButton:hover { background:#fc86a8; }
QPushButton:pressed { background:#e05f88; }
QPushButton:disabled { background:rgba(210,215,222,160); color:#8a9098; }
QPushButton#blue { background:#00AEEC; } QPushButton#blue:hover { background:#33bdff; }
QPushButton#gray { background:rgba(120,130,145,190); color:#fff; }
QPushButton#gray:hover { background:rgba(140,150,165,215); }
QProgressBar { background:rgba(255,255,255,120); border:1px solid rgba(255,255,255,160);
    border-radius:7px; text-align:center; min-height:18px; color:#1f2430; }
QProgressBar::chunk { background:#00AEEC; border-radius:6px; }
QTableWidget { background:rgba(255,255,255,190); color:#1f2430;
    gridline-color:rgba(31,36,48,45); border-radius:8px; }
QTableWidget::item { padding:3px; }
QTableWidget::item:selected { background:#FB7299; color:#fff; }
QHeaderView::section { background:rgba(255,255,255,235); color:#e05f88; padding:5px;
    border:none; border-bottom:2px solid #FB7299; font-weight:600; }
QGroupBox { border:1px solid rgba(31,36,48,45); border-radius:10px;
    margin-top:22px; padding-top:10px; background:rgba(255,255,255,195);
    color:#1f2430; font-weight:600; }
QGroupBox::title { color:#e05f88; subcontrol-origin:margin; left:14px;
    top:2px; padding:0 6px; }
QCheckBox { spacing:7px; color:#1f2430; }
QCheckBox::indicator { width:18px; height:18px; }
QCheckBox::indicator:unchecked { image: url(@IND_OFF); }
QCheckBox::indicator:hover { image: url(@IND_HOVER); }
QCheckBox::indicator:checked { image: url(@IND_ON); }
QCheckBox::indicator:checked:hover { image: url(@IND_ON); }
QTextEdit { font-family:'Consolas'; background:rgba(255,255,255,218);
    border:1px solid rgba(31,36,48,45); }
QScrollBar:vertical { background:rgba(31,36,48,35); width:10px; border-radius:5px; }
QScrollBar::handle:vertical { background:rgba(31,36,48,110); border-radius:5px;
    min-height:30px; }
QScrollBar::handle:vertical:hover { background:#FB7299; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }
""".replace('@IND_OFF', ind['off']).replace('@IND_HOVER', ind['hover']) \
   .replace('@IND_ON', ind['on']) \
   .replace('@ARROW_UP', ind['arrow_up']).replace('@ARROW_DOWN', ind['arrow_down'])


def read_table(path):
    """读取 csv / txt(制表符) 结果文件，返回 (表头, 行字典列表)。"""
    with open(path, encoding='utf-8-sig', newline='') as f:
        first = f.readline()
        delim = '\t' if '\t' in first else ','
        f.seek(0)
        raw = [[c.strip() for c in line]
               for line in csv.reader(f, delimiter=delim) if line]
    if not raw:
        return [], []
    header = raw[0]
    data = [dict(zip(header, r + [''] * (len(header) - len(r))))
            for r in raw[1:] if any(x for x in r)]
    for r in data:  # 兼容旧数据：神号·乱码 → 极品神号
        if r.get('判定') == '神号·乱码':
            r['判定'] = '极品神号'
    return header, data


class WallpaperWidget(QWidget):
    """清晰壁纸主容器：壁纸原样铺满（等比裁切），不做模糊，透明面板直接浮在其上。"""

    def __init__(self):
        super().__init__()
        self._pix = QPixmap(asset('1920x1080.jpg'))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect()
        if not self._pix.isNull():
            scaled = self._pix.scaled(rect.size(),
                                      Qt.KeepAspectRatioByExpanding,
                                      Qt.SmoothTransformation)
            p.drawPixmap((rect.width() - scaled.width()) // 2,
                         (rect.height() - scaled.height()) // 2, scaled)
        else:
            p.fillRect(rect, QColor(238, 241, 246))
        p.fillRect(rect, QColor(255, 255, 255, 66))  # 白纱提亮，缓解壁纸花哨


class ScanWorker(QThread):
    progress = Signal(int, int, int, float, str)   # done, total, exists, rate, uid
    hit = Signal(dict)
    event = Signal(str)
    finished2 = Signal(dict)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        c = self.cfg
        stop = self._stop
        try:
            pairs = eng.collect_pretty(c.start, c.end, c.min_run, c.tail_rules) \
                if c.pretty else []
            if pairs:
                wanted = set(c.types)
                pairs = [(u, [t for t in tg if t in wanted]) for u, tg in pairs]
                pairs = [(u, tg) for u, tg in pairs if tg]
            tset = {u for u, _ in pairs}
            mark_map = {u: '|'.join(tg) for u, tg in pairs}
            if c.suffix:
                rng, _ = eng.build_targets(c.start, c.end, c.suffix)
                tag = f'尾号{c.suffix}'
                for u in rng:
                    tset.add(u)
                    mark_map[u] = f'{mark_map[u]}|{tag}' if u in mark_map else tag
            if tset:
                targets = eng.order_targets(tset, mark_map)
                marks_provided = True
            else:
                targets, marks_provided = None, False
            exc = ''.join(sorted(set(c.exclude_digits or '')))
            must = ''.join(sorted(set(c.must_digits or '')))
            if exc or must:
                def digit_ok(u):
                    s = str(u)
                    if any(x in s for x in exc):
                        return False
                    return all(x in s for x in must)
                if targets is not None:
                    targets = [u for u in targets if digit_ok(u)]
                else:
                    targets = [u for u in range(c.start, c.end + 1)
                               if digit_ok(u)]
                mark_map = {u: m for u, m in mark_map.items()
                            if u in set(targets)}
            total = len(targets) if targets is not None else c.end - c.start + 1
            iter_targets = targets if targets is not None \
                else range(c.start, c.end + 1)
            if total == 0:
                self.finished2.emit({'msg': '没有符合条件的目标，请调整参数',
                                     'interrupted': False})
                return

            name = 'bili_scan' + (f'_end{c.suffix}' if c.suffix else '') \
                + ('_pretty' if c.pretty else '') + f'_{c.start}_{c.end}'
            out = c.out_dir
            os.makedirs(out, exist_ok=True)
            csv_path = os.path.join(out, name + '.csv')
            done_path = os.path.join(out, name + '.done')
            failed_path = os.path.join(out, name + '.failed.txt')
            resuming = not c.no_resume and os.path.exists(done_path)
            if not resuming:
                for p in (csv_path, done_path, failed_path):
                    if os.path.exists(p):
                        os.remove(p)
            done_log = eng.DoneLog(done_path)
            skipped = sum(1 for u in iter_targets if u in done_log.done
                          and done_log.status.get(u) != 'failed')
            if skipped >= total:
                self.finished2.emit({'msg': f'断点显示已全部完成（{total}）。'
                                     f'如需重扫请勾选"忽略断点"',
                                     'interrupted': False})
                return
            self.event.emit(f'♻️ 跳过已完成 {skipped:,} 个，待扫 '
                            f'{total - skipped:,} 个 | 结果: {csv_path}')
            store = eng.ResultStore(csv_path, failed_path)
            rate = eng.RateCtl(c.min_delay, c.max_delay)
            q = queue.Queue(maxsize=200)
            exists = {'n': 0}
            done_n = {'n': skipped}
            t0 = time.monotonic()
            stat = {'shen': 0, 'bot': 0, 'gib': 0, 'emp': 0, 'fail': 0}
            lock = threading.Lock()

            def w():
                while not stop.is_set():
                    try:
                        uid = q.get(timeout=2)
                    except queue.Empty:
                        continue
                    if uid is None:
                        return
                    if uid in done_log.done and done_log.status.get(uid) != 'failed':
                        continue
                    mark = mark_map.get(uid, '') if marks_provided else ''
                    status, card = eng.check_uid(uid, c, rate, stop)
                    if status == 'stopped':
                        continue
                    with lock:
                        if status == 'ok':
                            exists['n'] += 1
                            uname = card.get('name', '')
                            level = (card.get('level_info') or {}) \
                                .get('current_level', 0)
                            fans = card.get('fans', 0)
                            fol = card.get('attention', 0)
                            reg_str = ''
                            try:
                                if int(card.get('regtime', 0)) > 0:
                                    reg_str = time.strftime(
                                        '%Y-%m-%d',
                                        time.localtime(int(card['regtime'])))
                            except (TypeError, ValueError):
                                reg_str = ''
                            is_shen = (level == 0 and fans == 0 and fol == 0
                                       and bool(eng.STRICT_NAME_PATTERN
                                                .match(uname)))
                            verdict = eng.classify(is_shen,
                                                   eng.is_gibberish_name(uname),
                                                   level)
                            row = {'UID': uid, '昵称': uname, '关注数': fol,
                                   '粉丝数': fans, '账号等级': level,
                                   '标记': mark, '判定': verdict,
                                   '注册时间': reg_str,
                                   '获赞': card.get('_like_num', ''),
                                   '投稿数': card.get('_archive_count', '')}
                            store.append_row(row)
                            if verdict.endswith('神号'):
                                stat['shen'] += 1
                            elif verdict == '注册机号':
                                stat['bot'] += 1
                            elif verdict == '乱码名':
                                stat['gib'] += 1
                            if verdict:
                                self.hit.emit(row)
                        elif status == 'empty':
                            stat['emp'] += 1
                        else:
                            stat['fail'] += 1
                            store.append_failed(uid)
                            self.event.emit(f'❌ UID {uid} 重试耗尽，记入失败清单')
                        done_log.add(uid, status)
                        done_n['n'] += 1
                        r = (time.monotonic() - t0) \
                            / max(done_n['n'] - skipped, 1)
                        self.progress.emit(done_n['n'], total, exists['n'],
                                           r, str(uid))

            def feeder():
                try:
                    for u in iter_targets:
                        if stop.is_set():
                            break
                        q.put(u)
                finally:
                    for _ in range(c.threads):
                        try:
                            q.put(None, timeout=5)
                        except queue.Full:
                            pass

            ft = threading.Thread(target=feeder, daemon=True)
            ft.start()
            ths = [threading.Thread(target=w, daemon=True)
                   for _ in range(c.threads)]
            for t in ths:
                t.start()
            for t in ths:
                t.join()
            interrupted = stop.is_set() and done_n['n'] < total
            stop.set()
            store.close()
            done_log.close()
            self.finished2.emit({
                'msg': (f'{"⏹ 已停止" if interrupted else "🏁 扫描完成"} | '
                        f'处理 {done_n["n"] - skipped:,}/{total:,} | '
                        f'存在 {exists["n"]:,} | 神号类 {stat["shen"]} | '
                        f'注册机号 {stat["bot"]} | 乱码名 {stat["gib"]} | '
                        f'失败 {stat["fail"]}'),
                'interrupted': interrupted, 'csv': csv_path})
        except Exception as e:  # noqa
            self.finished2.emit({'msg': f'❌ 异常: {e}', 'interrupted': False})


class RecheckWorker(QThread):
    progress = Signal(int, int)
    event = Signal(str)
    finished2 = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        c = self.cfg
        stop = self._stop
        try:
            src = c.file
            header, data = read_table(src)
            if not data:
                self.finished2.emit('❌ 文件为空或无数据行')
                return
            for extra in ('注册时间', '获赞', '投稿数'):
                if extra not in header:
                    header.append(extra)
            by_uid = {r['UID']: r for r in data if r['UID'].strip().isdigit()}
            uids = [int(u) for u in by_uid]
            if not uids:
                self.finished2.emit('❌ 文件中没有有效 UID 列')
                return
            self.event.emit(f'📋 开始复查 {len(uids):,} 个账号')
            eng.session_warmup()

            rate = eng.RateCtl(c.min_delay, c.max_delay)
            q = queue.Queue()
            for u in uids:
                q.put(u)
            changes, miss, gone = [], [], [0]
            done_cnt = {'n': 0}
            lock = threading.Lock()

            def w():
                while not stop.is_set():
                    try:
                        uid = q.get(timeout=2)
                    except queue.Empty:
                        return
                    status, card = eng.check_uid(uid, c, rate, stop)
                    with lock:
                        done_cnt['n'] += 1
                        row = by_uid[str(uid)]
                        if status == 'empty':
                            gone[0] += 1
                            changes.append((uid, ['⚠️ 账号已无资料(可能注销)']))
                        elif status == 'ok':
                            uname = card.get('name', '')
                            level = (card.get('level_info') or {}) \
                                .get('current_level', 0)
                            fans = card.get('fans', 0)
                            fol = card.get('attention', 0)
                            diffs = []
                            if row.get('昵称', '') != uname:
                                diffs.append(f"改名: {row.get('昵称', '')} -> {uname}")
                                row['昵称'] = uname
                            if row.get('账号等级', '') != str(level):
                                diffs.append(f"等级: Lv.{row.get('账号等级', '?')} -> Lv.{level}")
                                row['账号等级'] = str(level)
                            if row.get('粉丝数', '') != str(fans):
                                diffs.append(f"粉丝: {row.get('粉丝数', '?')} -> {fans}")
                                row['粉丝数'] = str(fans)
                            if row.get('关注数', '') != str(fol):
                                diffs.append(f"关注: {row.get('关注数', '?')} -> {fol}")
                                row['关注数'] = str(fol)
                            reg_str = ''
                            try:
                                if int(card.get('regtime', 0)) > 0:
                                    reg_str = time.strftime(
                                        '%Y-%m-%d',
                                        time.localtime(int(card['regtime'])))
                            except (TypeError, ValueError):
                                reg_str = ''
                            if reg_str and row.get('注册时间', '') != reg_str:
                                diffs.append(f"注册时间: {row.get('注册时间', '空')} -> {reg_str}")
                            row['注册时间'] = reg_str or row.get('注册时间', '')
                            row['获赞'] = str(card.get('_like_num', '')) \
                                or row.get('获赞', '')
                            row['投稿数'] = str(card.get('_archive_count', '')) \
                                or row.get('投稿数', '')
                            is_shen = (level == 0 and fans == 0 and fol == 0
                                       and bool(eng.STRICT_NAME_PATTERN
                                                .match(uname)))
                            nv = eng.classify(is_shen,
                                              eng.is_gibberish_name(uname),
                                              level)
                            if nv != row.get('判定', ''):
                                diffs.append(f"判定: {row.get('判定', '') or '空'} -> {nv or '空'}")
                                row['判定'] = nv
                            if diffs:
                                changes.append((uid, diffs))
                                self.event.emit(f'🔄 UID {uid}: '
                                                + ' | '.join(diffs))
                        else:
                            miss.append(uid)
                        if done_cnt['n'] % 100 == 0:
                            self.progress.emit(done_cnt['n'], len(uids))

            ths = [threading.Thread(target=w, daemon=True)
                   for _ in range(c.threads)]
            for t in ths:
                t.start()
            for t in ths:
                t.join()

            delim = '\t' if src.lower().endswith('.txt') else ','
            tmp = src + '.tmp'
            with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
                wr = csv.writer(f, delimiter=delim)
                wr.writerow(header)
                for r in data:
                    wr.writerow([r.get(h, '') for h in header])
            os.replace(tmp, src)
            base, _ = os.path.splitext(src)
            chg = base + '_变化.txt'
            with open(chg, 'w', encoding='utf-8-sig') as f:
                for uid, diffs in changes:
                    f.write(f'UID {uid}: ' + ' | '.join(diffs) + '\n')
            self.progress.emit(done_cnt['n'], len(uids))
            self.finished2.emit(
                f'🔄 复查完成！检查 {done_cnt["n"]:,} | 有变化 '
                f'{len(changes) - gone[0]:,} | 已注销 {gone[0]:,} | 失败 {len(miss)}'
                + ('（已停止）' if stop.is_set() else ''))
        except Exception as e:  # noqa
            self.finished2.emit(f'❌ 异常: {e}')


class ScanTab(QWidget):
    def _card(self, title):
        """创建一张带粉色标题的分区卡片，返回 (卡片, 内部布局)。"""
        card = QFrame()
        card.setObjectName('card')
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 12)
        cl.setSpacing(8)
        t = QLabel(title)
        t.setObjectName('cardtitle')
        cl.addWidget(t)
        return card, cl

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        card1, c1 = self._card('📍 扫描区间')
        r1 = QHBoxLayout()
        r1.addWidget(QLabel('从'))
        self.start = QSpinBox(); self.start.setRange(1, 99999999)
        self.start.setValue(1000000)
        r1.addWidget(self.start, 1)
        r1.addWidget(QLabel('到'))
        self.end = QSpinBox(); self.end.setRange(1, 99999999)
        self.end.setValue(2000000)
        r1.addWidget(self.end, 1)
        r1.addSpacing(18)
        r1.addWidget(QLabel('指定尾号'))
        self.suffix = QLineEdit(); self.suffix.setPlaceholderText('如 0901，留空不限')
        self.suffix.setMaximumWidth(180)
        r1.addWidget(self.suffix)
        c1.addLayout(r1)
        outer.addWidget(card1)

        card2, c2 = self._card('💎 靓号规则')
        r2 = QHBoxLayout()
        r2.addWidget(QLabel('类型'))
        self.type_boxes = {}
        for t in ('顺子', '豹子', '回文', '交替', '尾4', '尾3'):
            cb = QCheckBox(t)
            cb.setChecked(t in ('顺子', '豹子'))
            self.type_boxes[t] = cb
            r2.addWidget(cb)
        r2.addSpacing(14)
        r2.addWidget(QLabel('连号位数'))
        self.min_run = QSpinBox(); self.min_run.setRange(3, 7); self.min_run.setValue(5)
        r2.addWidget(self.min_run)
        r2.addSpacing(14)
        self.pretty = QCheckBox('只扫靓号（关闭则全量）')
        self.pretty.setChecked(True)
        r2.addWidget(self.pretty)
        self.tail_rules = QCheckBox('附加尾部规律')
        r2.addWidget(self.tail_rules)
        r2.addStretch(1)
        c2.addLayout(r2)
        r2b = QHBoxLayout()
        dl = QLabel('数字偏好'); dl.setObjectName('cardtitle')
        r2b.addWidget(dl)
        self.no4 = QCheckBox('不带 4')
        self.no7 = QCheckBox('不带 7')
        self.no0 = QCheckBox('不含 0')
        for cb in (self.no4, self.no7, self.no0):
            r2b.addWidget(cb)
        r2b.addSpacing(10)
        r2b.addWidget(QLabel('额外排除'))
        self.exclude_digits = QLineEdit()
        self.exclude_digits.setPlaceholderText('如 3')
        self.exclude_digits.setMaximumWidth(120)
        r2b.addWidget(self.exclude_digits)
        r2b.addWidget(QLabel('必含数字'))
        self.must_digits = QLineEdit(); self.must_digits.setPlaceholderText('如 8 或 68')
        self.must_digits.setMaximumWidth(150)
        r2b.addWidget(self.must_digits)
        r2b.addStretch(1)
        c2.addLayout(r2b)
        outer.addWidget(card2)

        card4, c4 = self._card('⚙️ 引擎与输出')
        r4 = QHBoxLayout()
        r4.addWidget(QLabel('并发线程'))
        self.threads = QSpinBox(); self.threads.setRange(1, 16); self.threads.setValue(4)
        r4.addWidget(self.threads)
        r4.addSpacing(22)
        r4.addWidget(QLabel('请求间隔（秒）'))
        self.dmin = QDoubleSpinBox(); self.dmin.setRange(0.5, 60); self.dmin.setValue(2.0)
        r4.addWidget(self.dmin)
        r4.addWidget(QLabel('~'))
        self.dmax = QDoubleSpinBox(); self.dmax.setRange(0.5, 60); self.dmax.setValue(5.0)
        r4.addWidget(self.dmax)
        r4.addSpacing(22)
        r4.addWidget(QLabel('失败重试'))
        self.retries = QSpinBox(); self.retries.setRange(1, 10); self.retries.setValue(4)
        r4.addWidget(self.retries)
        r4.addStretch(1)
        c4.addLayout(r4)
        r4b = QHBoxLayout()
        self.no_resume = QCheckBox('从头重扫（忽略断点进度）')
        r4b.addWidget(self.no_resume)
        r4b.addSpacing(22)
        r4b.addWidget(QLabel('结果保存至'))
        self.out_dir = QLineEdit(os.path.join(APP_DIR, 'scan_out'))
        r4b.addWidget(self.out_dir, 1)
        b = QPushButton('浏览…'); b.setProperty('class', 'gray')
        b.clicked.connect(self.pick_dir)
        r4b.addWidget(b)
        c4.addLayout(r4b)
        outer.addWidget(card4)

        crow = QHBoxLayout()
        self.start_btn = QPushButton('🚀 开始寻号')
        self.start_btn.clicked.connect(self.start_scan)
        crow.addWidget(self.start_btn)
        self.stop_btn = QPushButton('⏹ 停止')
        self.stop_btn.setProperty('class', 'gray')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scan)
        crow.addWidget(self.stop_btn)
        self.open_btn = QPushButton('📂 结果文件夹')
        self.open_btn.setProperty('class', 'blue')
        self.open_btn.clicked.connect(self.open_out)
        crow.addWidget(self.open_btn)
        crow.addStretch(1)
        outer.addLayout(crow)

        self.bar = QProgressBar()
        outer.addWidget(self.bar)
        self.stat = QLabel('⏳ 静候佳号 | 双击命中行可直达其 B 站主页')
        self.stat.setObjectName('statuspill')
        self.stat.setWordWrap(True)
        outer.addWidget(self.stat)

        card = QFrame(); card.setObjectName('subcard')
        card.setMinimumHeight(190)
        cl = QVBoxLayout(card); cl.setContentsMargins(10, 10, 10, 10)
        hdr = QHBoxLayout()
        ht = QLabel('🎯 实时命中'); ht.setObjectName('cardtitle')
        hdr.addWidget(ht)
        hint = QLabel('双击行 = 打开 B 站主页'); hint.setProperty('subtitle', True)
        hdr.addWidget(hint)
        hdr.addStretch(1)
        cl.addLayout(hdr)
        self.table = QTableWidget(0, len(FIELDS))
        self.table.setHorizontalHeaderLabels(FIELDS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.open_uid)
        cl.addWidget(self.table, 1)
        outer.addWidget(card, 1)

        lcard = QFrame(); lcard.setObjectName('subcard')
        ll = QVBoxLayout(lcard); ll.setContentsMargins(10, 8, 10, 10)
        lt = QLabel('📜 寻号手札'); lt.setObjectName('cardtitle')
        ll.addWidget(lt)
        self.logbox = QTextEdit(); self.logbox.setReadOnly(True)
        self.logbox.setMaximumHeight(130)
        self._buf = deque(maxlen=300)
        ll.addWidget(self.logbox)
        outer.addWidget(lcard)

    def open_uid(self, row, _col=None):
        table = self.sender() if isinstance(self.sender(), QTableWidget) else self.table
        headers = [table.horizontalHeaderItem(i).text()
                   for i in range(table.columnCount())]
        if 'UID' in headers:
            uid = table.item(row, headers.index('UID')).text()
            if uid.strip().isdigit():
                os.startfile(f'https://space.bilibili.com/{uid}')

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, '选择保存位置', self.out_dir.text())
        if d:
            self.out_dir.setText(d)

    def open_out(self):
        d = self.out_dir.text()
        if os.path.isdir(d):
            os.startfile(d)

    def _cfg(self):
        if int(self.start.value()) > int(self.end.value()):
            QMessageBox.warning(self, '参数错误', '结束 UID 必须大于等于起始 UID')
            return None
        if self.dmin.value() > self.dmax.value():
            QMessageBox.warning(self, '参数错误', '最小延迟不能大于最大延迟')
            return None
        types = {t for t, cb in self.type_boxes.items() if cb.isChecked()}
        exclude = set(self.exclude_digits.text().strip())
        if self.no4.isChecked():
            exclude.add('4')
        if self.no7.isChecked():
            exclude.add('7')
        if self.no0.isChecked():
            exclude.add('0')
        return SimpleNamespace(
            start=int(self.start.value()), end=int(self.end.value()),
            suffix=self.suffix.text().strip(), types=types,
            min_run=int(self.min_run.value()), tail_rules=self.tail_rules.isChecked(),
            pretty=self.pretty.isChecked(), threads=int(self.threads.value()),
            min_delay=float(self.dmin.value()), max_delay=float(self.dmax.value()),
            timeout=5.0, max_retries=int(self.retries.value()),
            out_dir=self.out_dir.text().strip() or APP_DIR,
            no_resume=self.no_resume.isChecked(),
            exclude_digits=''.join(sorted(exclude)),
            must_digits=self.must_digits.text().strip())

    def start_scan(self):
        cfg = self._cfg()
        if cfg is None:
            return
        self.worker = ScanWorker(cfg)
        self.worker.progress.connect(self.on_progress)
        self.worker.hit.connect(self.on_hit)
        self.worker.event.connect(self.on_event)
        self.worker.finished2.connect(self.on_finished)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.table.setRowCount(0)
        self._buf.clear()
        self.logbox.clear()
        self.worker.start()

    def stop_scan(self):
        if getattr(self, 'worker', None):
            self.worker.stop()
            self.stat.setText('正在停止…（等待在途请求完成）')

    def on_progress(self, done, total, exists, rate, uid):
        self.bar.setMaximum(total)
        self.bar.setValue(done)
        eta = max(total - done, 0) * rate
        self.stat.setText(f'进度 {done:,}/{total:,} ({done / max(total, 1) * 100:.2f}%) '
                          f'| 记录 {exists:,} | {rate:.1f}s/个 | '
                          f'剩余 ~{int(eta // 3600)}h{int(eta % 3600 // 60):02d}m '
                          f'| 当前 {uid}')

    def on_hit(self, row):
        r = self.table.rowCount()
        if r >= 500:
            self.table.removeRow(0)
            r -= 1
        self.table.insertRow(r)
        for i, f in enumerate(FIELDS):
            it = QTableWidgetItem(str(row.get(f, '')))
            if f == '判定' and row.get('判定', '').endswith('神号'):
                it.setForeground(QBrush(QColor('#17994f')))
            self.table.setItem(r, i, it)

    def on_event(self, msg):
        self._buf.append(f'[{time.strftime("%H:%M:%S")}] {msg}')
        self.logbox.setPlainText('\n'.join(self._buf))
        sb = self.logbox.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_finished(self, info):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stat.setText(info['msg'])
        self._buf.append(f'[{time.strftime("%H:%M:%S")}] {info["msg"]}')
        self.logbox.setPlainText('\n'.join(self._buf))


class ResultsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        self.rows = []
        self.columns = list(FIELDS)
        self.view = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        crow = QHBoxLayout()
        b1 = QPushButton('📂 打开数据文件')
        b1.setProperty('class', 'blue')
        b1.clicked.connect(self.load_file)
        crow.addWidget(b1)
        preset1 = QPushButton('✨ 三无神号')
        preset1.clicked.connect(lambda: self.preset('shen'))
        crow.addWidget(preset1)
        preset2 = QPushButton('🤖 乱码/注册机')
        preset2.setProperty('class', 'gray')
        preset2.clicked.connect(lambda: self.preset('bot'))
        crow.addWidget(preset2)
        crow.addStretch(1)
        self.info = QLabel('支持 csv / txt(制表符) | 双击表格行直达 B 站主页')
        self.info.setProperty('subtitle', True)
        crow.addWidget(self.info)
        lay.addLayout(crow)

        fbox = QGroupBox('筛选条件 · 可自由组合')
        fl = QVBoxLayout(fbox)
        fl.setContentsMargins(14, 12, 14, 12)
        fl.setSpacing(9)

        r0 = QHBoxLayout()
        r0.addWidget(QLabel('判定'))
        self.vboxes = {}
        for v in ('极品神号', '神号', '注册机号', '乱码名', '其他'):
            cb = QCheckBox(v)
            self.vboxes[v] = cb
            r0.addWidget(cb)
        r0.addStretch(1)
        fl.addLayout(r0)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel('标记包含'))
        self.mark_in = QLineEdit()
        self.mark_in.setPlaceholderText('逗号分隔，如: 顺子,尾号0901')
        r1.addWidget(self.mark_in, 1)
        r1.addSpacing(22)
        r1.addWidget(QLabel('账号等级'))
        self.level = QComboBox()
        self.level.addItems(['全部等级'] + [f'Lv.{i}' for i in range(7)])
        self.level.setMinimumWidth(130)
        r1.addWidget(self.level)
        fl.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel('UID 范围'))
        self.uid_lo = QSpinBox(); self.uid_lo.setRange(0, 99999999)
        self.uid_hi = QSpinBox(); self.uid_hi.setRange(0, 99999999)
        self.uid_hi.setValue(99999999)
        r2.addWidget(self.uid_lo, 1)
        r2.addWidget(QLabel('~'))
        r2.addWidget(self.uid_hi, 1)
        r2.addSpacing(22)
        r2.addWidget(QLabel('昵称包含'))
        self.name_in = QLineEdit()
        r2.addWidget(self.name_in, 1)
        fl.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel('昵称排除'))
        self.name_ex = QLineEdit()
        r3.addWidget(self.name_ex, 1)
        r3.addSpacing(22)
        r3.addWidget(QLabel('昵称正则'))
        self.name_re = QLineEdit()
        self.name_re.setPlaceholderText('如 ^[a-z][a-z0-9]{2,17}$')
        r3.addWidget(self.name_re, 1)
        fl.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel('数量'))
        self.f0 = QCheckBox('仅0粉丝')
        self.g0 = QCheckBox('仅0关注')
        self.like0 = QCheckBox('仅获赞0')
        self.arc0 = QCheckBox('仅投稿0')
        self.live = QCheckBox('仅含昵称')
        for cb in (self.f0, self.g0, self.like0, self.arc0, self.live):
            r4.addWidget(cb)
        r4.addSpacing(22)
        r4.addWidget(QLabel('规则'))
        self.no_pattern = QCheckBox('排除规律名')
        self.ascii_only = QCheckBox('仅纯英文数字')
        self.shen_quick = QCheckBox('三无神号快捷(Lv0+双0+规范名)')
        for cb in (self.no_pattern, self.ascii_only, self.shen_quick):
            r4.addWidget(cb)
        r4.addStretch(1)
        fl.addLayout(r4)

        r5 = QHBoxLayout()
        ab = QPushButton('🔍 应用筛选')
        ab.clicked.connect(self.apply)
        r5.addWidget(ab)
        rb = QPushButton('重置')
        rb.setProperty('class', 'gray')
        rb.clicked.connect(self.reset)
        r5.addWidget(rb)
        r5.addStretch(1)
        self.stat = QLabel('')
        r5.addWidget(self.stat, 1)
        fl.addLayout(r5)
        lay.addWidget(fbox)

        self.table = QTableWidget(0, len(FIELDS))
        self.table.setHorizontalHeaderLabels(FIELDS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.open_uid)
        lay.addWidget(self.table, 1)

        erow = QHBoxLayout()
        erow.addWidget(QLabel('导出格式'))
        self.fmt = QComboBox()
        self.fmt.addItems(['CSV 文件', 'TXT (制表符)', 'Excel (xlsx)', '纯UID列表'])
        erow.addWidget(self.fmt)
        self.sel_only = QCheckBox('仅导出筛选结果')
        self.sel_only.setChecked(True)
        erow.addWidget(self.sel_only)
        erow.addStretch(1)
        lay.addLayout(erow)

    def preset(self, kind):
        for cb in self.vboxes.values():
            cb.setChecked(False)
        for cb in (self.f0, self.g0, self.like0, self.arc0, self.live,
                   self.no_pattern, self.ascii_only, self.shen_quick):
            cb.setChecked(False)
        if kind == 'shen':
            self.vboxes['极品神号'].setChecked(True)
            self.vboxes['神号'].setChecked(True)
            self.f0.setChecked(True)
            self.g0.setChecked(True)
            self.ascii_only.setChecked(True)
            self.no_pattern.setChecked(True)
        else:
            self.vboxes['极品神号'].setChecked(True)
            self.vboxes['注册机号'].setChecked(True)
            self.vboxes['乱码名'].setChecked(True)
            self.ascii_only.setChecked(True)
        self.apply()

    def open_uid(self, row, _col=None):
        headers = [self.table.horizontalHeaderItem(i).text()
                   for i in range(self.table.columnCount())]
        if 'UID' in headers:
            uid = self.table.item(row, headers.index('UID')).text()
            if uid.strip().isdigit():
                os.startfile(f'https://space.bilibili.com/{uid}')

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '打开结果文件', os.path.join(APP_DIR, 'scan_out'),
            '结果文件 (*.csv *.txt);;所有文件 (*)')
        if not path:
            return
        try:
            header, data = read_table(path)
        except Exception as e:
            QMessageBox.critical(self, '读取失败', str(e))
            return
        if not data:
            QMessageBox.warning(self, '提示', '文件中没有数据行')
            return
        self.rows = data
        self.columns = header if header else list(FIELDS)
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.info.setText(f'{os.path.basename(path)} | {len(data):,} 行')
        self.apply()

    def _keep(self, r):
        vset = {v for v, cb in self.vboxes.items() if cb.isChecked()}
        if vset:
            verdict = r.get('判定', '') or '其他'
            if verdict not in vset:
                return False
        marks = [m.strip() for m in self.mark_in.text().split(',') if m.strip()]
        if marks and not any(m in r.get('标记', '') for m in marks):
            return False
        uid = int(r['UID']) if r.get('UID', '').strip().isdigit() else 0
        if int(self.uid_lo.value()) and uid < int(self.uid_lo.value()):
            return False
        if int(self.uid_hi.value()) < 99999999 and uid > int(self.uid_hi.value()):
            return False
        lv = self.level.currentText()
        if lv != '全部等级' and r.get('账号等级', '') != lv.replace('Lv.', ''):
            return False
        if self.f0.isChecked() and r.get('粉丝数', '0') not in ('', '0'):
            return False
        if self.g0.isChecked() and r.get('关注数', '0') not in ('', '0'):
            return False
        if self.like0.isChecked() and r.get('获赞', '0') not in ('', '0'):
            return False
        if self.arc0.isChecked() and r.get('投稿数', '0') not in ('', '0'):
            return False
        name = r.get('昵称', '')
        if self.live.isChecked() and not name.strip():
            return False
        ni = self.name_in.text().strip()
        if ni and ni not in name:
            return False
        ne = self.name_ex.text().strip()
        if ne and ne in name:
            return False
        rex = self.name_re.text().strip()
        if rex and not re.search(rex, name):
            return False
        if self.no_pattern.isChecked() and eng.pattern_reason(name):
            return False
        if self.ascii_only.isChecked() and not re.fullmatch(r'[A-Za-z0-9_]*', name):
            return False
        if self.shen_quick.isChecked() and not (
                r.get('账号等级', '') == '0'
                and r.get('粉丝数', '0') in ('', '0')
                and r.get('关注数', '0') in ('', '0')
                and re.fullmatch(r'[A-Za-z0-9_]*', name)):
            return False
        return True

    def apply(self):
        self.view = [r for r in self.rows if self._keep(r)]
        self.table.setRowCount(0)
        shown = 0
        for r in self.view:
            if shown >= 3000:
                break
            i = self.table.rowCount()
            self.table.insertRow(i)
            for j, col in enumerate(self.columns):
                it = QTableWidgetItem(str(r.get(col, '')))
                if col == '判定' and r.get('判定', '').endswith('神号'):
                    it.setForeground(QBrush(QColor('#17994f')))
                self.table.setItem(i, j, it)
            shown += 1
        extra = '（表格最多显示 3,000 行，导出不受限）' if len(self.view) > 3000 else ''
        self.stat.setText(f'共 {len(self.rows):,} 行 | 筛选后 {len(self.view):,} 行{extra}')

    def reset(self):
        for cb in self.vboxes.values():
            cb.setChecked(False)
        for le in (self.mark_in, self.name_in, self.name_ex, self.name_re):
            le.clear()
        self.uid_lo.setValue(0)
        self.uid_hi.setValue(99999999)
        self.level.setCurrentIndex(0)
        for cb in (self.f0, self.g0, self.like0, self.arc0, self.live,
                   self.no_pattern, self.ascii_only, self.shen_quick):
            cb.setChecked(False)
        self.apply()

    def export(self):
        rows = self.view if self.sel_only.isChecked() else self.rows
        if not rows:
            QMessageBox.information(self, '提示', '没有可导出的数据')
            return
        fmt = self.fmt.currentText()
        ext = {'CSV 文件': '.csv', 'TXT (制表符)': '.txt',
               'Excel (xlsx)': '.xlsx', '纯UID列表': '.txt'}[fmt]
        path, _ = QFileDialog.getSaveFileName(
            self, '选择导出路径', os.path.join(APP_DIR, 'scan_out', '导出' + ext),
            f'{fmt} (*{ext})')
        if not path:
            return
        try:
            cols = self.columns
            if fmt == 'CSV 文件':
                with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(cols)
                    for r in rows:
                        w.writerow([r.get(c, '') for c in cols])
            elif fmt == 'TXT (制表符)':
                with open(path, 'w', encoding='utf-8-sig') as f:
                    f.write('\t'.join(cols) + '\n')
                    for r in rows:
                        f.write('\t'.join(str(r.get(c, '')) for c in cols) + '\n')
            elif fmt == 'Excel (xlsx)':
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.title = '结果'
                ws.append(cols)
                for r in rows:
                    ws.append([r.get(c, '') for c in cols])
                wb.save(path)
            else:  # 纯UID列表
                with open(path, 'w', encoding='utf-8') as f:
                    for r in rows:
                        f.write(f"{r.get('UID', '')}\n")
            QMessageBox.information(self, '导出成功',
                                    f'已导出 {len(rows):,} 行到:\n{path}')
            os.startfile(os.path.dirname(path))
        except Exception as e:
            QMessageBox.critical(self, '导出失败', str(e))


class RecheckTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        form = QGridLayout()
        form.addWidget(QLabel('结果文件'), 0, 0)
        self.file = QLineEdit()
        form.addWidget(self.file, 0, 1)
        b = QPushButton('浏览…'); b.setProperty('class', 'gray')
        b.clicked.connect(self.pick)
        form.addWidget(b, 0, 2)
        form.addWidget(QLabel('线程数'), 1, 0)
        self.threads = QSpinBox(); self.threads.setRange(1, 16); self.threads.setValue(4)
        form.addWidget(self.threads, 1, 1)
        form.addWidget(QLabel('延迟(秒)'), 1, 2)
        d = QHBoxLayout()
        self.dmin = QDoubleSpinBox(); self.dmin.setRange(0.5, 60); self.dmin.setValue(2.0)
        self.dmax = QDoubleSpinBox(); self.dmax.setRange(0.5, 60); self.dmax.setValue(5.0)
        d.addWidget(self.dmin); d.addWidget(QLabel('~')); d.addWidget(self.dmax)
        form.addLayout(d, 1, 3)
        lay.addLayout(form)

        crow = QHBoxLayout()
        self.start_btn = QPushButton('🔄 开始复查')
        self.start_btn.clicked.connect(self.start)
        crow.addWidget(self.start_btn)
        self.stop_btn = QPushButton('⏹ 停止')
        self.stop_btn.setProperty('class', 'gray')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self.worker.stop() if self.worker else None)
        crow.addWidget(self.stop_btn)
        crow.addStretch(1)
        lay.addLayout(crow)

        self.bar = QProgressBar(); lay.addWidget(self.bar)
        self.stat = QLabel('⏳ 待命 | 复查会重新查询文件里的每个账号，检测改名/升级/活跃/注销'
                           '并更新数据，同时补齐"注册时间/获赞/投稿数"三列')
        self.stat.setObjectName('statuspill')
        self.stat.setWordWrap(True)
        lay.addWidget(self.stat)

        lcard = QFrame(); lcard.setObjectName('subcard')
        ll = QVBoxLayout(lcard); ll.setContentsMargins(10, 8, 10, 10)
        lt = QLabel('📜 复查日志'); lt.setObjectName('cardtitle')
        ll.addWidget(lt)
        self.logbox = QTextEdit(); self.logbox.setReadOnly(True)
        self._buf = deque(maxlen=300)
        ll.addWidget(self.logbox)
        lay.addWidget(lcard, 1)
        self.worker = None

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(
            self, '选择结果文件', os.path.join(APP_DIR, 'scan_out'),
            '结果文件 (*.csv *.txt);;所有文件 (*)')
        if p:
            self.file.setText(p)

    def start(self):
        f = self.file.text().strip()
        if not os.path.exists(f):
            QMessageBox.warning(self, '提示', '请选择存在的结果文件')
            return
        self.worker = RecheckWorker(SimpleNamespace(
            file=f, threads=int(self.threads.value()),
            min_delay=float(self.dmin.value()), max_delay=float(self.dmax.value()),
            timeout=5.0, max_retries=4))
        self.worker.progress.connect(self.on_progress)
        self.worker.event.connect(self.on_event)
        self.worker.finished2.connect(self.on_finished)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._buf.clear()
        self.logbox.clear()
        self.worker.start()

    def on_progress(self, done, total):
        self.bar.setMaximum(total)
        self.bar.setValue(done)
        self.stat.setText(f'复查进度 {done:,}/{total:,}')

    def on_event(self, msg):
        self._buf.append(f'[{time.strftime("%H:%M:%S")}] {msg}')
        self.logbox.setPlainText('\n'.join(self._buf))
        sb = self.logbox.verticalScrollBar()
        sb.setValue(sb.maximum())

    def on_finished(self, msg):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stat.setText(msg)
        self._buf.append(f'[{time.strftime("%H:%M:%S")}] {msg}')
        self.logbox.setPlainText('\n'.join(self._buf))


class HelpTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('panel')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        t = QTextEdit()
        t.setReadOnly(True)
        t.setHtml("""
        <h2 style="color:#FB7299">号海捞珍 · 使用宝典</h2>
        <p>在号海之中，捞取属于你的珍宝 —— 一款对新手友好的 B 站 UID 寻号、判定与筛选工具</p>

        <h3 style="color:#00AEEC">🌟 新手必读：判定等级是什么？</h3>
        <p>每个账号扫描后会得到一个"判定"等级（结果表中的「判定」列），从高到低排列如下。</p>
        <p>先记住一个词——<b>三无</b>：0 级 + 0 粉丝 + 0 关注，代表这个号<b>注册后从未使用过</b>。
        再认识两种名字——<b>规范名</b>（小写字母开头、3~18 位英文数字，像正常人取的名字）和
        <b>乱码名</b>（字母数字混杂、辅音偏多、不含常见单词或拼音，像机器随机敲出来的，如 xk7f2m）。</p>
        <table cellpadding="7">
        <tr><td><b style="color:#e05f88">🏆 极品神号</b></td>
        <td>三无 + 规范名 + 乱码名。注册后从未用过、名字还像机器生成的——大概率是<b>注册机批量注册后遗弃的号</b>，最难被原主人找回，是最值得收藏的顶级目标。</td></tr>
        <tr><td><b style="color:#e05f88">✨ 神号</b></td>
        <td>三无 + 规范名。同样是"从未使用"的干净号，只是名字更像真人随手取的。</td></tr>
        <tr><td><b style="color:#e05f88">🤖 注册机号</b></td>
        <td>乱码名 + 0 级，但已有少量粉丝或关注——疑似注册机批量生产的"半成品"。</td></tr>
        <tr><td><b>❓ 乱码名</b></td>
        <td>名字像机器生成，但账号已升过级，不再是纯净三无。</td></tr>
        <tr><td><b>─ 普通</b></td>
        <td>不符合以上任何特征的账号。</td></tr>
        </table>

        <h3 style="color:#00AEEC">🚀 扫描任务</h3>
        <ul>
        <li><b>扫描区间</b>：要检查的 UID 范围；<b>指定尾号</b>：只扫特定结尾（如 0901），留空不限</li>
        <li><b>靓号类型</b>：顺子(1234567)、豹子(1111111)、回文(1234321)、交替(1212121)；<b>尾4 / 尾3</b> 是结尾规律，需勾选"附加尾部规律"</li>
        <li><b>连号位数</b>：顺子/豹子的位数门槛——5 = 标准靓号，4 = 小靓号</li>
        <li><b>数字偏好</b>：忌讳与吉利自由组合，如"不带 4 / 不带 7"再配"必含 8"</li>
        <li><b>只扫靓号</b>：取消勾选则扫描区间内全部 UID（配合判定等级捞神号）</li>
        <li><b>断点保护</b>：中途停止后再点"开始寻号"会自动跳过已扫部分；勾选"从头重扫"则推倒重来</li>
        <li><b>风控保护</b>：每线程随机延迟；触发 -412 限流时全体线程同步冷却，请勿盲目调高线程数</li>
        <li><b>小技巧</b>：双击命中行，直达该用户的 B 站主页</li>
        </ul>

        <h3 style="color:#00AEEC">🔎 结果与筛选</h3>
        <ul>
        <li>打开历史 csv/txt 数据文件，所有筛选条件都带勾选框，可自由组合</li>
        <li>一键预设：<b>✨ 三无神号</b>（极品神号 + 神号）/ <b>🤖 乱码与注册机</b>（极品神号 + 注册机号 + 乱码名）</li>
        <li>导出格式：CSV、TXT(制表符)、Excel(xlsx)、纯 UID 列表；保存路径自选</li>
        </ul>

        <h3 style="color:#00AEEC">🔄 数据复查</h3>
        <ul>
        <li>定期重新查询数据文件里的每个账号，检测<b>改名 / 升级 / 涨粉 / 注销</b>等变化并输出变化清单</li>
        <li>复查会为新老文件补齐"注册时间 / 获赞 / 投稿数"三列</li>
        </ul>

        <h3 style="color:#FB7299">⚠️ 免责声明</h3>
        <p>本工具仅供技术研究与数据分析。请遵守 B 站用户协议与相关法律法规，勿用于任何恶意用途；使用产生的一切后果由使用者自行承担。</p>
        """)
        lay.addWidget(t)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 780)
        self.setMinimumSize(980, 640)
        icon_path = asset('icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        root = WallpaperWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(14)

        sidebar = QWidget(); sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(190)
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(14, 18, 14, 14)
        t = QLabel(APP_TITLE); t.setObjectName('title')
        sv.addWidget(t)
        s = QLabel('在号海之中，捞取属于你的珍宝'); s.setObjectName('subtitle')
        sv.addWidget(s)
        sv.addSpacing(10)
        self.nav = QListWidget()
        for label in ('🚀 扫描任务', '🔎 结果筛选', '🔄 数据复查', '❓ 使用说明'):
            self.nav.addItem(label)
        sv.addWidget(self.nav, 1)
        ver = QLabel('v1.1 · 引擎 v3'); ver.setObjectName('subtitle')
        sv.addWidget(ver)
        lay.addWidget(sidebar)

        self.stack = QStackedWidget()

        def scrolled(page):
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.NoFrame)
            sa.setWidget(page)
            return sa

        self.stack.addWidget(scrolled(ScanTab()))
        self.stack.addWidget(scrolled(ResultsTab()))
        self.stack.addWidget(scrolled(RecheckTab()))
        self.stack.addWidget(HelpTab())
        lay.addWidget(self.stack, 1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.setCentralWidget(root)


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont('Microsoft YaHei UI', 10))
    app.setStyleSheet(build_qss())
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
