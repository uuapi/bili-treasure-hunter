/* 号海捞珍 — 判定与目标生成引擎（纯函数，浏览器 / Node 双端通用） */
'use strict';

const STRICT_NAME = /^[a-z][a-z0-9]{2,17}$/;
const VOWELS = new Set('aeiou');
const COMMON_SUBSTRINGS = ['the','ing','tion','ment','able','ness','ful','less','game','love','cool','star','fire','dark','blue','king','play','hero','wolf','fox','cat','dog','sky','moon','sun','ice','war','pro','max','boy','girl','man','fan','god','ace','top','big','red','hot','old','new','one','two','day','way','eye','her','his','you','not','all','can','out','use','how','its','may','did','get','has','him','see','now','come','than','like','just','over','know','back','only','good','some','time','very','when','with','make','hand','high','keep','last','long','much','own','say','she','too','any','same','tell','each','bilibili','bili','video','anime','music','live','chen','wang','zhang','yang','huang','zhao','zhou','chun','xiao','ming','hong','feng','jing','ying','qing','long','ping','ling','dong','song','tang'];
const KB = ['qwerty','qwer','rewq','asdf','fdsa','zxcv','xcvb','vcxz','hjkl','qaz','wsx','edc','1qaz','2wsx'];
const ASC4 = Array.from({length:7}, (_,i)=>String.fromCharCode(97+i)+String.fromCharCode(98+i)+String.fromCharCode(99+i)+String.fromCharCode(100+i));
const DSC4 = Array.from({length:7}, (_,i)=>String.fromCharCode(122-i)+String.fromCharCode(121-i)+String.fromCharCode(120-i)+String.fromCharCode(119-i));

function is_gibberish(name) {
  if (!/^[a-z0-9]+$/.test(name)) return false;
  if (!(/[a-z]/.test(name) && /\d/.test(name))) return false;
  if (/\d{3}/.test(name)) return false;
  if (name.length < 6 || name.length > 12) return false;
  let cons = 0;
  for (const ch of name) if (!VOWELS.has(ch)) cons++;
  if (cons / name.length <= 0.60) return false;
  for (const s of COMMON_SUBSTRINGS) if (name.includes(s)) return false;
  return true;
}
function classify(isShen, isGib, level) {
  if (isShen && isGib) return '极品神号';
  if (isShen) return '神号';
  if (isGib && level === 0) return '注册机号';
  if (isGib) return '乱码名';
  return '';
}
function pattern_reason(name) {
  const n = name.toLowerCase();
  if (/^\d+$/.test(n)) return '纯数字';
  if (!/^[a-z0-9]+$/.test(n)) return null;
  if (/(.)\1{2,}/.test(n)) return '同字符连3+';
  for (const w of ASC4.concat(DSC4)) if (n.includes(w)) return '字母表连续4段';
  for (const k of KB) if (n.includes(k)) return '键盘序列';
  const L = n.length;
  for (let bl = 1; bl <= L/2; bl++) {
    if (L % bl === 0 && n === n.slice(0, bl).repeat(L/bl)) return '整体重复块';
  }
  const letters = n.replace(/[^a-z]/g, '');
  if (letters.length >= 4 && is_block_rep(letters)) return '去数字后字母重复块';
  if (n.length >= 6 && n === n.split('').reverse().join('') && !/[aeiou]/.test(n)) return '无元音回文';
  return null;
}
function is_block_rep(s) {
  const L = s.length;
  for (let bl = 1; bl <= L/2; bl++) {
    if (L % bl === 0 && s === s.slice(0, bl).repeat(L/bl)) return true;
  }
  return false;
}
function build_targets(start, end, suffix) {
  if (start > end) return null;
  if (!suffix) return {first:start, last:end, step:1};
  const step = Math.pow(10, suffix.length);
  const mod = parseInt(suffix, 10);
  const first = start + ((mod - start) % step + step) % step;
  if (first > end) return null;
  const last = end - ((end - mod) % step);
  return {first, last, step};
}
function digit_windows(n) {
  const asc = [], dsc = [];
  for (let d = 0; d + n <= 10; d++) asc.push(Array.from({length:n},(_,j)=>String(d+j)).join(''));
  for (let d = 9; d - n + 1 >= 0; d--) dsc.push(Array.from({length:n},(_,j)=>String(d-j)).join(''));
  return asc.concat(dsc);
}
const WIN4 = digit_windows(4), REP4 = Array.from({length:10},(_,d)=>String(d).repeat(4));
const WIN5 = digit_windows(5), REP5 = Array.from({length:10},(_,d)=>String(d).repeat(5));
const ASC3 = digit_windows(3), REP3 = Array.from({length:10},(_,d)=>String(d).repeat(3));
const SCAN_ORDER = ['顺子','尾号','豹子','交替','回文','尾4','尾3'];

function pretty_tags(uid, minRun, tail) {
  const s = String(uid), tags = [];
  const win = digit_windows(minRun);
  if (win.some(w => s.includes(w))) tags.push('顺子');
  if ((Array.from({length:10},(_,d)=>String(d).repeat(minRun))).some(w => s.includes(w))) tags.push('豹子');
  if (s.length >= 5 && s === s.split('').reverse().join('')) tags.push('回文');
  if (s.length >= 6 && s[0] !== s[1] && s === (s.slice(0,2).repeat(Math.ceil(s.length/2))).slice(0, s.length)) tags.push('交替');
  if (tail && s.length >= 4) {
    const t4 = s.slice(-4);
    if (WIN4.includes(t4) || REP4.includes(t4)
        || (t4[0] === t4[1] && t4[1] !== t4[2] && t4[2] === t4[3])
        || (t4[0] === t4[2] && t4[2] !== t4[1] && t4[1] === t4[3])) tags.push('尾4');
    const t3 = s.slice(-3);
    if (REP3.includes(t3) || ASC3.includes(t3) || digit_windows(3).includes(t3)) tags.push('尾3');
  }
  return tags;
}
function order_targets(list, markMap) {
  return list.slice().sort((a, b) => {
    const ka = cat_index(markMap[a] || ''), kb = cat_index(markMap[b] || '');
    return ka - kb || a - b;
  });
}
function cat_index(mark) {
  let idx = SCAN_ORDER.length;
  for (const t of mark.split('|')) {
    const base = t.startsWith('尾号') ? '尾号' : t;
    const i = SCAN_ORDER.indexOf(base);
    if (i >= 0) idx = Math.min(idx, i);
  }
  return idx;
}
function parse_resp(res) {
  if (res.startsWith('ERR:')) return {status:'error', reason:res.slice(4)};
  const nl = res.indexOf('\n');
  const head = nl < 0 ? res : res.slice(0, nl);
  const body = nl < 0 ? '' : res.slice(nl + 1);
  if (!head.startsWith('HTTP:')) return {status:'error', reason:'未知响应'};
  const code = parseInt(head.slice(5), 10);
  if (code === 412 || code === 429) return {status:'blocked', reason:'HTTP '+code};
  let j;
  try { j = JSON.parse(body); } catch (e) {
    return code >= 500 ? {status:'error', reason:'HTTP '+code+' 非JSON'}
                       : {status:'blocked', reason:'HTTP '+code+' 非JSON'};
  }
  const c = j.code;
  if (c === 0) {
    const p = j.data || {}, card = p.card || null;
    if (!card || Object.keys(card).length === 0) return {status:'empty'};
    card._like_num = p.like_num != null ? String(p.like_num) : '';
    card._archive_count = p.archive_count != null ? String(p.archive_count) : '';
    return {status:'ok', card};
  }
  if (c === -412 || c === -799 || c === -352) return {status:'blocked', reason:'风控拦截('+c+')'};
  if (c === -400 || c === -402 || c === -404) return {status:'empty'};
  return {status:'error', reason:'未知业务码 '+c};
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const rand = (a, b) => a + Math.random() * (b - a);

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { classify, is_gibberish, pattern_reason, is_block_rep,
    build_targets, digit_windows, pretty_tags, order_targets, cat_index,
    parse_resp, SCAN_ORDER, STRICT_NAME, is_block_rep_underscore: is_block_rep };
}
