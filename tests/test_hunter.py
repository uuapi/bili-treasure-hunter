#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_hunter_pro 核心纯函数测试（无 pytest 依赖，直接 python 运行）。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bili_hunter_pro import (DoneLog, build_targets, classify, is_block_repeat,
                             is_gibberish_name, order_targets, pattern_reason,
                             STRICT_NAME_PATTERN, tag_base)

FAILS = []


def check(desc, actual, expected):
    ok = actual == expected
    if not ok:
        FAILS.append(f'{desc}: 期望 {expected!r} 实际 {actual!r}')
    print(('✅' if ok else '❌') + f' {desc}')


# ---- build_targets：尾号取模定位 ----
rng, n = build_targets(1000000, 2000000, '0901')
check('尾号0901 目标数', n, 100)
check('尾号0901 首个', rng[0], 1000901)
check('尾号0901 末个', rng[-1], 1990901)
rng, n = build_targets(100000, 999999, '0901')
check('六位尾号目标数', n, 90)
check('六位尾号首个', rng[0], 100901)
check('start>end', build_targets(5, 3, '')[1], 0)

# ---- tag_base / order_targets ----
check('tag_base 尾号', tag_base('尾号0901'), '尾号')
check('tag_base 顺子', tag_base('顺子'), '顺子')
marks = {100: '尾号0901', 200: '顺子', 300: '豹子', 400: ''}
check('扫描顺序 顺子>尾号>豹子>无标记',
      order_targets([300, 200, 100, 400], marks), [200, 100, 300, 400])

# ---- pattern_reason：规律名判定 ----
check('纯数字', pattern_reason('13101726186'), '纯数字')
check('同字符连3+', pattern_reason('Fuuuck'), '同字符连3+')
check('键盘序列', pattern_reason('qwerdf14'), '键盘序列')
check('字母表连续4段', pattern_reason('zyxwde625'), '字母表连续4段')
check('整体重复块', pattern_reason('abcabc'), '整体重复块')
check('去数字后字母重复块', pattern_reason('as5d4as56d456'), '去数字后字母重复块')
check('无元音回文', pattern_reason('FDSFSDF'), '无元音回文')
check('正常名放行', pattern_reason('josiesenior'), None)
check('大写名放行', pattern_reason('Golf'), None)
check('含中文跳过', pattern_reason('小明123'), None)

# ---- is_gibberish_name：乱码名判定 ----
check('乱码名', is_gibberish_name('xk7f2m'), True)
check('拼音名', is_gibberish_name('wang2019'), False)
check('无数字不算乱码', is_gibberish_name('achouchou'), False)
check('三连数字不算乱码', is_gibberish_name('qq123456'), False)
check('超长不算乱码', is_gibberish_name('ab1' + 'c' * 20), False)

# ---- classify：判定体系 ----
check('极品神号', classify(True, True, 0), '极品神号')
check('神号', classify(True, False, 0), '神号')
check('注册机号', classify(False, True, 0), '注册机号')
check('乱码名', classify(False, True, 3), '乱码名')
check('普通', classify(False, False, 5), '')
check('规范名正则', bool(STRICT_NAME_PATTERN.match('shinfanalyst')), True)

# ---- is_block_repeat ----
check('abcabc 是重复块', is_block_repeat('abcabc'), True)
check('abcd 非重复块', is_block_repeat('abcd'), False)

# ---- DoneLog：状态断点 ----
tmp = os.path.join(tempfile.gettempdir(), 'hunter_done_test.txt')
with open(tmp, 'w', encoding='utf-8') as f:
    f.write('100\n200\tfailed\n300\tok\n')
dl = DoneLog(tmp)
check('旧格式行视为 ok', dl.status[100], 'ok')
check('failed 状态', dl.status[200], 'failed')
check('ok 状态', dl.status[300], 'ok')
check('done 包含全部', all(u in dl.done for u in (100, 200, 300)), True)
dl.add(200, 'ok')
check('失败后重扫覆盖为 ok', dl.status[200], 'ok')
dl.close()
os.remove(tmp)

print('-' * 50)
if FAILS:
    print(f'❌ {len(FAILS)} 个测试失败：')
    for f_ in FAILS:
        print('  ' + f_)
    sys.exit(1)
print('✅ 全部测试通过')
