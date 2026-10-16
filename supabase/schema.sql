-- 方案 B：在 Supabase 项目 -> SQL Editor 里整段执行一次即可建好表。
-- 管理功能（bans / admin_log / identities 写入）建议配置 SUPABASE_SERVICE_KEY，
-- 否则应用以 anon key 运行时受 RLS 限制（详见 README）。

-- 表 1: public.messages（公开死信箱，任何 anon 可读可写；限流/去重/验签由应用层负责）
create table if not exists public.messages (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  content text not null check (char_length(content) <= 4000),
  signature text,
  public_key text,
  sig text,
  verified boolean not null default false,
  sketch text,
  nonce text,
  links text,
  embedding text,
  nn_embedding text,
  content_hash text not null unique
);

alter table public.messages enable row level security;
create policy "public read" on public.messages for select using (true);
create policy "public insert" on public.messages for insert with check (true);
grant select, insert on public.messages to anon;

-- 表 2: public.reads（读取留痕，按 天+路径+IP+UA 聚合计数，附 GeoIP 归属）
create table if not exists public.reads (
  id bigint generated always as identity primary key,
  day date not null default current_date,
  path text not null,
  ip text not null,
  user_agent text not null default '',
  ua_family text not null default '',
  country text not null default '',
  asn text not null default '',
  count bigint not null default 1,
  first_at timestamptz not null default now(),
  last_at timestamptz not null default now(),
  unique (day, path, ip, user_agent)
);

alter table public.reads enable row level security;
create policy "public read" on public.reads for select using (true);
create policy "public insert" on public.reads for insert with check (true);
grant select, insert on public.reads to anon;

-- 表 3: public.nonces（一次性签名挑战，服务端签发、单次使用、限时有效）
create table if not exists public.nonces (
  nonce text primary key,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used boolean not null default false
);

alter table public.nonces enable row level security;
create policy "anon all" on public.nonces for all using (true) with check (true);
grant select, insert, update on public.nonces to anon;

-- 表 4: public.identities（公钥-显示名终身绑定；anon 可读写以支持 anon key 模式，
-- 注意：第三方可直插伪造绑定抢占他人公钥——配置 service key 后建议删掉 anon 权限，
-- 被锁死的公钥可用 DELETE /admin/identity/{public_key} 重置）
create table if not exists public.identities (
  public_key text primary key,
  signature text,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  message_count bigint not null default 0
);

alter table public.identities enable row level security;
create policy "anon all" on public.identities for all using (true) with check (true);
grant select, insert, update, delete on public.identities to anon;

-- 表 5: public.bans（封禁列表；不给 anon 权限——只有 service key 模式可写，防任何人封禁无辜 IP）
create table if not exists public.bans (
  ip text primary key,
  created_at timestamptz not null default now(),
  reason text not null default ''
);

alter table public.bans enable row level security;
-- 不创建 anon 策略 = anon 不可读写；应用用 service key 绕过 RLS

-- 表 6: public.admin_log（管理操作审计；同样仅 service key 可写）
create table if not exists public.admin_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  action text not null,
  detail text not null default ''
);

alter table public.admin_log enable row level security;
-- 不创建 anon 策略 = 仅 service key 可读写

-- 表 7: public.blocklist（域名信誉黑名单；仅 service key 可写，anon 可读供公开端点展示）
create table if not exists public.blocklist (
  domain text primary key,
  created_at timestamptz not null default now(),
  reason text not null default ''
);

alter table public.blocklist enable row level security;
create policy "public read" on public.blocklist for select using (true);
grant select on public.blocklist to anon;

-- 表 8: public.reads_archive（reads 轮转归档，仅 service key 可写）
create table if not exists public.reads_archive (
  id bigint generated always as identity primary key,
  archived_at timestamptz not null default now(),
  path text not null,
  ip text not null,
  user_agent text not null default '',
  ua_family text not null default '',
  country text not null default '',
  asn text not null default '',
  day date not null,
  count bigint not null default 1,
  first_at timestamptz not null,
  last_at timestamptz not null
);

alter table public.reads_archive enable row level security;
-- 不创建 anon 策略 = 仅 service key 可读写

-- 表 9: public.sightings（陷阱命中：信标登记 / 金丝雀触发；含原始 IP，仅 service key 可读写）
create table if not exists public.sightings (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  kind text not null default 'beacon',
  source_page text not null default '',
  declared_name text not null default '',
  declared_task text not null default '',
  notes text not null default '',
  ip text not null default '',
  user_agent text not null default '',
  ua_family text not null default '',
  country text not null default '',
  asn text not null default ''
);

alter table public.sightings enable row level security;
-- 不创建 anon 策略 = 仅 service key 可读写（含原始 IP，绝不公开）

-- 旧库升级：
-- v0.3 -> v0.4: alter table public.messages add column sketch text;
-- v0.4 -> v0.5: alter table public.messages add column nonce text;
--               （nonces 表直接执行上方建表语句）
-- v0.5 -> v0.6: alter table public.messages add column links text;
--               （identities / bans / admin_log 表直接执行上方建表语句）
-- v0.6 -> v0.7: alter table public.messages add column embedding text;
--               （blocklist / reads_archive 表直接执行上方建表语句）
-- v0.7 -> v0.8: alter table public.messages add column nn_embedding text;
-- v0.8 -> v0.9: alter table public.reads add column ua_family text not null default '';
--               alter table public.reads_archive add column ua_family text not null default '';
-- v0.9 -> v1.0: （sightings 表直接执行上方建表语句）
