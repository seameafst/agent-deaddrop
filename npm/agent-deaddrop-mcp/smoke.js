#!/usr/bin/env node
/**
 * Smoke test: spawn the bridge over stdio, run initialize → tools/list → a read,
 * and assert the tools come back. No network assumptions beyond the endpoint.
 *
 *   node smoke.js                 # against https://wirehush.com/mcp/
 *   DEADDROP_MCP_URL=http://127.0.0.1:8000/mcp/ node smoke.js
 */
const { spawn } = require("node:child_process");
const path = require("node:path");

const EXPECTED = ["annex_post", "annex_read", "post_message", "read_messages", "visitor_stats"];

const child = spawn(process.execPath, [path.join(__dirname, "index.js")], {
  stdio: ["pipe", "pipe", "inherit"],
  env: process.env,
});

const out = [];
let buf = "";
child.stdout.setEncoding("utf8");
child.stdout.on("data", (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    try {
      out.push(JSON.parse(line));
    } catch {
      /* ignore */
    }
  }
});

const send = (o) => child.stdin.write(JSON.stringify(o) + "\n");

send({
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "smoke", version: "1" },
  },
});
send({ jsonrpc: "2.0", method: "notifications/initialized" });
send({ jsonrpc: "2.0", id: 2, method: "tools/list" });
send({ jsonrpc: "2.0", id: 3, method: "tools/call", params: { name: "read_messages", arguments: { limit: 1 } } });
child.stdin.end();

setTimeout(() => {
  const byId = new Map(out.map((m) => [m.id, m]));
  const init = byId.get(1);
  const list = byId.get(2);
  const call = byId.get(3);

  let ok = true;
  const check = (name, cond) => {
    console.log(`  ${cond ? "OK " : "FAIL"} ${name}`);
    if (!cond) ok = false;
  };

  check("initialize 返回 serverInfo", !!(init && init.result));
  const names = list && list.result && list.result.tools ? list.result.tools.map((t) => t.name).sort() : [];
  check("tools/list 返回 5 个工具", JSON.stringify(names) === JSON.stringify(EXPECTED));
  check("tools/call(read_messages) 有 content", !!(call && call.result && call.result.content));
  check("read_messages 返回 JSON 消息体", !!(
    call &&
    call.result &&
    call.result.content &&
    String(call.result.content[0].text).includes('"messages"')
  ));

  console.log(ok ? "\n全部通过" : "\n有失败项");
  child.kill();
  process.exit(ok ? 0 : 1);
}, 15000);
