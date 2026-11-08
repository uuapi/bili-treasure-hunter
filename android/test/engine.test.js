/* 号海捞珍 — JS 引擎单元测试（与 Python tests/test_hunter.py 对齐） */
'use strict';
const assert = require('assert');
const engine = require('../app/assets/engine.js');

const { classify, is_gibberish, pattern_reason, is_block_rep,
        build_targets, pretty_tags, order_targets, cat_index,
        parse_resp, STRICT_NAME } = engine;

let fails = 0;
function check(desc, cond) {
  console.log((cond ? '✅ ' : '❌ ') + desc);
  if (!cond) fails++;
}

/* ---- classify 判定体系 ---- */
check('极品神号', classify(true, true, 0) === '极品神号');
check('神号', classify(true, false, 0) === '神号');
check('注册机号', classify(false, true, 0) === '注册机号');
check('乱码名', classify(false, true, 3) === '乱码名');
check('普通', classify(false, false, 5) === '');
check('规范名正则', STRICT_NAME.test('shinfanalyst') === true);

/* ---- is_gibberish 乱码名 ---- */
check('乱码名 xk7f2m', is_gibberish('xk7f2m') === true);
check('拼音名 wang2019 非乱码', is_gibberish('wang2019') === false);
check('无数字不算乱码', is_gibberish('achouchou') === false);
check('三连数字不算乱码', is_gibberish('qq123456') === false);
check('超长不算乱码', is_gibberish('ab1' + 'c'.repeat(20)) === false);

/* ---- pattern_reason 规律名 ---- */
check('纯数字', pattern_reason('13101726186') === '纯数字');
check('同字符连3+', pattern_reason('Fuuuck') === '同字符连3+');
check('键盘序列', pattern_reason('qwerdf14') === '键盘序列');
check('字母表连续4段', pattern_reason('zyxwde625') === '字母表连续4段');
check('整体重复块', pattern_reason('abcabc') === '整体重复块');
check('去数字后字母重复块', pattern_reason('as5d4as56d456') === '去数字后字母重复块');
check('无元音回文', pattern_reason('FDSFSDF') === '无元音回文');
check('正常名放行', pattern_reason('josiesenior') === null);
check('大写名放行', pattern_reason('Golf') === null);
check('含中文跳过', pattern_reason('小明123') === null);
check('is_block_rep abcabc', is_block_rep('abcabc') === true);

/* ---- build_targets 尾号取模 ---- */
const bt = build_targets(1000000, 2000000, '0901');
check('尾号0901 首个', bt.first === 1000901);
check('尾号0901 末个', bt.last === 1990901);
let cnt = 0;
for (let u = bt.first; u <= bt.last; u += bt.step) cnt++;
check('尾号0901 共 100 个', cnt === 100);
const bt6 = build_targets(100000, 999999, '0901');
check('六位尾号首个', bt6.first === 100901);
check('六位尾号步进', bt6.step === 10000);
check('start>end 返回 null', build_targets(5, 3, '') === null);

/* ---- pretty_tags 靓号标签 ---- */
check('1234567 → 顺子', pretty_tags(1234567, 5, false).includes('顺子'));
check('1111111 → 豹子', pretty_tags(1111111, 5, false).includes('豹子'));
check('1234321 → 回文', pretty_tags(1234321, 5, false).includes('回文'));
check('1212121 → 交替', pretty_tags(1212121, 5, false).includes('交替'));
check('5888888 → 豹子+尾4', (() => {
  const t = pretty_tags(5888888, 5, true);
  return t.includes('豹子') && t.includes('尾4');
})());
check('普通号无标签', pretty_tags(2468135, 5, false).length === 0);

/* ---- cat_index / order_targets 扫描顺序 ---- */
check('cat_index 尾号0901', cat_index('尾号0901') === 1);
check('cat_index 顺子', cat_index('顺子') === 0);
const ordered = order_targets([300, 200, 100], {100: '顺子', 200: '尾号0901', 300: '豹子'});
check('排序 顺子→尾号→豹子',
  JSON.stringify(ordered) === JSON.stringify([100, 200, 300]));

/* ---- parse_resp 响应解析 ---- */
const okResp = parse_resp('HTTP:200\n{"code":0,"data":{"card":{"name":"heycc","level_info":{"current_level":0},"fans":0,"attention":0},"like_num":12,"archive_count":3}}');
check('ok 解析 + 获赞回填', okResp.status === 'ok' && okResp.card._like_num === '12');
check('风控 -352 → blocked',
  parse_resp('HTTP:200\n{"code":-352,"message":"-352"}').status === 'blocked');
check('风控 -412 → blocked',
  parse_resp('HTTP:200\n{"code":-412}').status === 'blocked');
check('不存在 → empty',
  parse_resp('HTTP:200\n{"code":0,"data":{"card":{}}}').status === 'empty');
check('ERR 前缀 → error',
  parse_resp('ERR:超时').status === 'error');
check('HTTP 412 状态码 → blocked',
  parse_resp('HTTP:412\nblocked').status === 'blocked');

console.log('=' . repeat(40));
if (fails) {
  console.log('❌ ' + fails + ' 项失败');
  process.exit(1);
}
console.log('✅ JS 引擎单元测试全部通过');
