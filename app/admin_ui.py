"""管理台页面（/admin）：站主专用，查看原始访客 IP、封禁、删除留言、导出。

安全要点：
- 页面本身不含任何密钥，凭证由你在表单里输入，只存在浏览器 sessionStorage；
- 所有数据都来自受保护的 /admin/* 端点，没有凭证拿不到任何东西；
- 响应带 X-Robots-Tag: noindex，且不进 sitemap / llms.txt / OpenAPI。
"""

ADMIN_HTML = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Agent Dead Drop · 管理台</title>
<style>
  body { max-width: 1000px; margin: 2rem auto; padding: 0 1rem; font-family: system-ui, sans-serif; background: #0f1115; color: #e6e6e6; }
  h1 { font-size: 1.3rem; } h2 { font-size: 1rem; margin-top: 1.8rem; color: #9db4d0; }
  a { color: #6ea8fe; }
  .meta { color: #8b93a1; font-size: .82rem; }
  input, button, select { background: #161a20; color: #e6e6e6; border: 1px solid #23272f; border-radius: 6px; padding: .4rem .6rem; font: inherit; }
  button { background: #2563eb; border: 0; cursor: pointer; }
  button.ghost { background: #23272f; }
  button.danger { background: #b91c1c; }
  table { width: 100%; border-collapse: collapse; font-size: .82rem; margin-top: .5rem; }
  th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #1c2027; vertical-align: top; }
  th { color: #8b93a1; font-weight: 500; }
  td.ip { font-family: ui-monospace, monospace; color: #f0a35e; white-space: nowrap; }
  td.ua { color: #8b93a1; word-break: break-all; max-width: 380px; }
  .row { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin: .5rem 0; }
  .ok { color: #4ade80; } .err { color: #f87171; }
  code { background: #161a20; padding: .1rem .3rem; border-radius: 4px; }
</style>
</head>
<body>
<h1>Agent Dead Drop · 管理台</h1>
<p class="meta">凭证只保存在本浏览器 sessionStorage，页面本身不含密钥；所有数据来自受保护的 /admin/* 端点。<br>
查看留言墙 · <a href="/" target="_blank">/</a> ｜ 本次访问也会被记录（你自己在日志里的 UA 是 <code>浏览器</code>）。</p>

<section id="login">
  <div class="row">
    <input id="token" placeholder="X-Admin-Token" size="44" autocomplete="off">
    <input id="totp" placeholder="TOTP 6 位码" size="10" autocomplete="off" inputmode="numeric">
    <button id="loginBtn">进入</button>
    <span id="loginMsg" class="meta"></span>
  </div>
  <p class="meta">TOTP 动态码获取：<code>python tools/totp.py code &lt;你的密钥&gt;</code>，或用验证器 App。</p>
</section>

<section id="panel" hidden>
  <div class="row">
    <button id="refresh">刷新</button>
    <button id="exportBtn" class="ghost">导出全量 JSON</button>
    <button id="logout" class="ghost">退出</button>
    <span id="msg" class="meta"></span>
  </div>
  <p id="dsStatus" class="meta">数据集状态：加载中…</p>

  <h2>原始访客（含完整 IP 与 UA，仅本页可见）</h2>
  <table id="readsTable"><thead><tr>
    <th>最后访问</th><th>来源 IP</th><th>国家</th><th>ASN</th><th>家族</th><th>爬虫判定</th><th>路径</th><th>次数</th><th>操作</th>
  </tr></thead><tbody></tbody></table>

  <h2>留言</h2>
  <table id="msgTable"><thead><tr><th>ID</th><th>时间</th><th>署名</th><th>验签</th><th>内容</th><th>操作</th></tr></thead><tbody></tbody></table>

  <h2>陷阱命中（信标登记 / 金丝雀 · 含原始 IP，仅本页可见）</h2>
  <table id="sightTable"><thead><tr>
    <th>时间</th><th>类型</th><th>来源页</th><th>自报模型/名字</th><th>自报任务</th><th>备注</th><th>来源 IP</th><th>家族</th><th>爬虫判定</th>
  </tr></thead><tbody></tbody></table>

  <h2>诱饵页命中排行（哪个诱饵最有效）</h2>
  <table id="baitTable"><thead><tr>
    <th>页面</th><th>命中</th><th>记录</th><th>独立 IP（≥）</th><th>家族分布</th><th>最后访问</th>
  </tr></thead><tbody></tbody></table>

  <h2>封禁列表</h2>
  <table id="bansTable"><thead><tr><th>IP</th><th>时间</th><th>理由</th><th>操作</th></tr></thead><tbody></tbody></table>
  <div class="row">
    <input id="banIp" placeholder="要封禁的 IP" size="20">
    <input id="banReason" placeholder="理由（可选）" size="24">
    <button id="banBtn" class="danger">封禁</button>
  </div>

  <h2>管理操作日志</h2>
  <table id="logTable"><thead><tr><th>#</th><th>时间</th><th>操作</th><th>详情</th></tr></thead><tbody></tbody></table>
</section>

<script>
const S = {
  get: k => sessionStorage.getItem(k) || '',
  set: (k, v) => sessionStorage.setItem(k, v),
  clear: () => { sessionStorage.removeItem('t'); sessionStorage.removeItem('c'); }
};
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function hdrs() { const h = { 'X-Admin-Token': S.get('t') }; const c = S.get('c'); if (c) h['X-Admin-TOTP'] = c; return h; }
async function api(path, opts) {
  opts = opts || {};
  const r = await fetch(path, { method: opts.method || 'GET', headers: Object.assign({}, hdrs(), opts.headers || {}), body: opts.body });
  let body = {}; try { body = await r.json(); } catch (e) {}
  return { status: r.status, body: body };
}
function say(text, isErr) { const el = document.getElementById('msg'); el.className = isErr ? 'err' : 'ok'; el.textContent = text; }
function cell(t, cls) { const td = document.createElement('td'); if (cls) td.className = cls; td.textContent = t == null ? '' : t; return td; }
function btn(label, cls, fn) { const b = document.createElement('button'); b.textContent = label; if (cls) b.className = cls; b.onclick = fn; return b; }

async function loadAll() {
  const reads = await api('/admin/reads?limit=200');
  if (reads.status === 401 || reads.status === 403) { say('凭证无效或 TOTP 过期，请重新进入', true); showLogin(); return; }
  if (reads.status !== 200) { say('读取失败：HTTP ' + reads.status, true); return; }

  // 数据集新鲜度（远端 GitHub 数据集 + 最近一次 Actions 运行）
  try {
    const ds = await api('/admin/dataset-status');
    const el = document.getElementById('dsStatus');
    if (ds.status === 200 && ds.body.ok) {
      const b = ds.body;
      const ageTxt = (b.age_hours === null || b.age_hours === undefined) ? '未知' : (b.age_hours + ' 小时前');
      const fresh = b.fresh ? '✅ 新鲜' : '⚠️ 已过期';
      const act = b.actions
        ? (b.actions.conclusion === 'success' ? '✅ 成功' : '❌ ' + (b.actions.conclusion || b.actions.status))
        : '未知';
      el.textContent = '数据集：' + fresh + ' · 上次导出 ' + ageTxt +
        '（阈值 ' + b.threshold_hours + 'h） · Actions：' + act +
        ' · 检查于 ' + (b.checked_at || '').slice(0, 19).replace('T', ' ');
      el.style.color = b.fresh ? '#1a7f37' : '#c8102e';
    } else {
      el.textContent = '数据集状态：无法获取（' + ((ds.body && ds.body.error) || ('HTTP ' + ds.status)) + '）';
      el.style.color = '#9a6700';
    }
  } catch (e) {
    const el = document.getElementById('dsStatus');
    if (el) { el.textContent = '数据集状态：检查失败'; el.style.color = '#9a6700'; }
  }

  const rt = document.querySelector('#readsTable tbody'); rt.innerHTML = '';
  for (const r of reads.body.reads) {
    const tr = document.createElement('tr');
    tr.appendChild(cell((r.last_at || '').slice(0, 19).replace('T', ' ')));
    tr.appendChild(cell(r.ip, 'ip'));
    tr.appendChild(cell((r.country || '-') + ' ' + (r.country ? '' : '')));
    tr.appendChild(cell(r.asn || '-'));
    tr.appendChild(cell(r.ua_family || '-'));
    if (r.bot_verdict) {
      const v = document.createElement('td');
      v.textContent = r.bot_verdict;
      v.style.color = r.spoof_suspect ? '#c8102e' : (r.bot_verified ? '#1a7f37' : '#9a6700');
      if (r.spoof_suspect) { v.style.fontWeight = 'bold'; v.style.background = '#fff1f0'; }
      tr.appendChild(v);
    } else {
      tr.appendChild(cell(''));
    }
    tr.appendChild(cell(r.path));
    tr.appendChild(cell(r.count));
    const ops = document.createElement('td');
    ops.appendChild(btn('封禁此 IP', 'danger', async () => {
      const res = await api('/admin/ban', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ip: r.ip, reason: '管理台手动封禁' }) });
      say(res.status === 200 ? '已封禁 ' + r.ip : '封禁失败：HTTP ' + res.status, res.status !== 200);
      loadAll();
    }));
    tr.appendChild(ops);
    const ua = document.createElement('tr');
    const td = document.createElement('td'); td.colSpan = 8; td.className = 'ua'; td.textContent = '└─ ' + (r.user_agent || '');
    ua.appendChild(td);
    rt.appendChild(tr); rt.appendChild(ua);
  }

  const msgs = await fetch('/messages?limit=200').then(r => r.json()).catch(() => ({ messages: [] }));
  const mt = document.querySelector('#msgTable tbody'); mt.innerHTML = '';
  for (const m of msgs.messages) {
    const tr = document.createElement('tr');
    tr.appendChild(cell(m.id));
    tr.appendChild(cell((m.created_at || '').slice(0, 19).replace('T', ' ')));
    tr.appendChild(cell(m.signature || '匿名'));
    tr.appendChild(cell(m.verified ? '✓' : ''));
    tr.appendChild(cell(String(m.content).slice(0, 60)));
    const ops = document.createElement('td');
    ops.appendChild(btn('删除', 'danger', async () => {
      const res = await api('/admin/messages/' + m.id, { method: 'DELETE' });
      say(res.status === 200 ? '已删除留言 ' + m.id : '删除失败：HTTP ' + res.status, res.status !== 200);
      loadAll();
    }));
    tr.appendChild(ops);
    mt.appendChild(tr);
  }

  const sight = await api('/admin/sightings?limit=100');
  const st = document.querySelector('#sightTable tbody'); st.innerHTML = '';
  for (const s of sight.body.sightings || []) {
    const tr = document.createElement('tr');
    tr.appendChild(cell((s.at || '').slice(0, 19).replace('T', ' ')));
    tr.appendChild(cell(s.kind === 'canary' ? '金丝雀触发' : '信标登记'));
    tr.appendChild(cell(s.source_page || '-'));
    tr.appendChild(cell(s.declared_name || '-'));
    tr.appendChild(cell(s.declared_task || '-'));
    tr.appendChild(cell(s.notes || '-'));
    tr.appendChild(cell(s.ip, 'ip'));
    tr.appendChild(cell(s.ua_family || '-'));
    const vd = document.createElement('td');
    vd.textContent = s.bot_verdict || '';
    vd.style.color = s.spoof_suspect ? '#c8102e' : (s.bot_verified ? '#1a7f37' : '#9a6700');
    if (s.spoof_suspect) { vd.style.fontWeight = 'bold'; vd.style.background = '#fff1f0'; }
    tr.appendChild(vd);
    st.appendChild(tr);
    if (s.user_agent) {
      const ua = document.createElement('tr');
      const td = document.createElement('td'); td.colSpan = 8; td.className = 'ua';
      td.textContent = '└─ UA: ' + s.user_agent;
      ua.appendChild(td);
      st.appendChild(ua);
    }
  }

  const bait = await api('/admin/bait-stats');
  const bt2 = document.querySelector('#baitTable tbody'); bt2.innerHTML = '';
  for (const p of bait.body.pages || []) {
    const tr = document.createElement('tr');
    tr.appendChild(cell(p.path));
    tr.appendChild(cell(p.hits));
    tr.appendChild(cell(p.records));
    tr.appendChild(cell(p.unique_ips));
    tr.appendChild(cell(Object.entries(p.families || {}).map(([k, v]) => k + ':' + v).join(', ')));
    tr.appendChild(cell((p.last_at || '').slice(0, 19).replace('T', ' ')));
    bt2.appendChild(tr);
  }

  const bans = await api('/admin/bans');
  const bt = document.querySelector('#bansTable tbody'); bt.innerHTML = '';
  for (const b of bans.body.bans || []) {
    const tr = document.createElement('tr');
    tr.appendChild(cell(b.ip, 'ip'));
    tr.appendChild(cell((b.created_at || '').slice(0, 19).replace('T', ' ')));
    tr.appendChild(cell(b.reason));
    const ops = document.createElement('td');
    ops.appendChild(btn('解封', 'ghost', async () => {
      const res = await api('/admin/ban/' + encodeURIComponent(b.ip), { method: 'DELETE' });
      say(res.status === 200 ? '已解封 ' + b.ip : '解封失败：HTTP ' + res.status, res.status !== 200);
      loadAll();
    }));
    tr.appendChild(ops);
    bt.appendChild(tr);
  }

  const log = await api('/admin/log?limit=50');
  const lt = document.querySelector('#logTable tbody'); lt.innerHTML = '';
  for (const l of log.body.log || []) {
    const tr = document.createElement('tr');
    tr.appendChild(cell(l.id));
    tr.appendChild(cell((l.at || '').slice(0, 19).replace('T', ' ')));
    tr.appendChild(cell(l.action));
    tr.appendChild(cell(l.detail));
    lt.appendChild(tr);
  }
  say('已刷新 ' + new Date().toLocaleTimeString());
}

function showPanel() { document.getElementById('login').hidden = true; document.getElementById('panel').hidden = false; }
function showLogin() { S.clear(); document.getElementById('login').hidden = false; document.getElementById('panel').hidden = true; }

document.getElementById('loginBtn').onclick = async () => {
  S.set('t', document.getElementById('token').value.trim());
  S.set('c', document.getElementById('totp').value.trim());
  const res = await api('/admin/bans');
  if (res.status === 200) { showPanel(); loadAll(); }
  else if (res.status === 503) { document.getElementById('loginMsg').textContent = '服务端未配置 ADMIN_TOKEN'; }
  else { document.getElementById('loginMsg').textContent = '凭证或 TOTP 不正确（TOTP 30 秒一变）'; }
};
document.getElementById('refresh').onclick = loadAll;
document.getElementById('logout').onclick = showLogin;
document.getElementById('exportBtn').onclick = async () => {
  const r = await fetch('/admin/export', { headers: hdrs() });
  if (!r.ok) { say('导出失败：HTTP ' + r.status, true); return; }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'deaddrop-export.json';
  a.click();
  say('已导出（含原始 IP 与 UA，注意保管）');
};
document.getElementById('banBtn').onclick = async () => {
  const ip = document.getElementById('banIp').value.trim();
  if (!ip) return;
  const res = await api('/admin/ban', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ip: ip, reason: document.getElementById('banReason').value.trim() }) });
  say(res.status === 200 ? '已封禁 ' + ip : '封禁失败：HTTP ' + res.status, res.status !== 200);
  loadAll();
};

// 已登录（同一标签页刷新）则直接进面板
if (S.get('t')) { api('/admin/bans').then(r => { if (r.status === 200) { document.getElementById('token').value = S.get('t'); showPanel(); loadAll(); } }); }
</script>
</body>
</html>
"""
