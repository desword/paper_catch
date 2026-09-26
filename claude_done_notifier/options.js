const $ = (id) => document.getElementById(id);
const status = (s) => { $("status").textContent = s; };

function showBoxes() {
  const p = $("provider").value;
  document.querySelectorAll(".box").forEach((b) => {
    b.style.display = b.dataset.for === p ? "" : "none";
  });
}

function load() {
  chrome.storage.sync.get(DEFAULTS, (cfg) => {
    for (const [k, v] of Object.entries(cfg)) {
      const el = $(k);
      if (!el) continue;
      if (el.type === "checkbox") el.checked = v; else el.value = v;
    }
    showBoxes();
  });
}

function collect() {
  const cfg = {};
  for (const [k, def] of Object.entries(DEFAULTS)) {
    const el = $(k);
    if (!el) continue;
    if (el.type === "checkbox") cfg[k] = el.checked;
    else if (typeof def === "number") cfg[k] = Number(el.value) || 0;
    else cfg[k] = el.value.trim();
  }
  return cfg;
}

async function save() {
  const cfg = collect();
  // Webhook 需要额外的主机权限（必须在用户点击中请求）
  if (cfg.provider === "webhook" && cfg.webhookUrl) {
    try {
      const origin = new URL(cfg.webhookUrl).origin + "/*";
      const ok = await chrome.permissions.request({ origins: [origin] });
      if (!ok) { status("未授予 Webhook 域名权限"); return false; }
    } catch (_) { status("Webhook URL 无效"); return false; }
  }
  await chrome.storage.sync.set(cfg);
  status("已保存 ✔");
  return true;
}

$("provider").addEventListener("change", showBoxes);
$("save").addEventListener("click", save);
$("test").addEventListener("click", async () => {
  if (!(await save())) return;
  status("发送中…");
  const r = await chrome.runtime.sendMessage({
    type: "claude-done",
    title: "测试对话",
    url: "https://claude.ai/",
    durationSec: 42,
    reply: "这是一封测试邮件。"
  });
  status(r?.ok ? "测试已发送 ✔ 请查收邮箱" : `失败：${r?.error}`);
});

load();
