importScripts("defaults.js");

async function getCfg() {
  return chrome.storage.sync.get(DEFAULTS);
}

function buildMessage(info) {
  const subject = `✅ Claude 已完成回复：${info.title}`;
  const lines = [
    `对话：${info.title}`,
    `链接：${info.url}`,
    `耗时：约 ${info.durationSec} 秒`,
    `时间：${new Date().toLocaleString()}`
  ];
  if (info.reply) lines.push("", "回复开头：", info.reply);
  return { subject, text: lines.join("\n") };
}

async function sendResend(cfg, subject, text) {
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${cfg.resendApiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ from: cfg.resendFrom, to: [cfg.toEmail], subject, text })
  });
  if (!r.ok) throw new Error(`Resend ${r.status}: ${await r.text()}`);
}

async function sendEmailJS(cfg, subject, text, info) {
  const body = {
    service_id: cfg.emailjsServiceId,
    template_id: cfg.emailjsTemplateId,
    user_id: cfg.emailjsPublicKey,
    template_params: {
      to_email: cfg.toEmail, subject, message: text,
      title: info.title, url: info.url
    }
  };
  if (cfg.emailjsPrivateKey) body.accessToken = cfg.emailjsPrivateKey;
  const r = await fetch("https://api.emailjs.com/api/v1.0/email/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!r.ok) throw new Error(`EmailJS ${r.status}: ${await r.text()}`);
}

async function sendWebhook(cfg, subject, text, info) {
  const r = await fetch(cfg.webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to: cfg.toEmail, subject, text, ...info })
  });
  if (!r.ok) throw new Error(`Webhook ${r.status}: ${await r.text()}`);
}

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon.png",
    title, message, priority: 2
  });
}

async function handleDone(info) {
  const cfg = await getCfg();
  const { subject, text } = buildMessage(info);
  if (cfg.desktopNotify) notify(subject, info.url);
  switch (cfg.provider) {
    case "resend": return sendResend(cfg, subject, text);
    case "emailjs": return sendEmailJS(cfg, subject, text, info);
    case "webhook": return sendWebhook(cfg, subject, text, info);
    default: return;
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== "claude-done") return;
  handleDone(msg)
    .then(() => sendResponse({ ok: true }))
    .catch((e) => {
      console.error(e);
      notify("Claude Done Notifier：邮件发送失败", String(e.message || e).slice(0, 200));
      sendResponse({ ok: false, error: String(e.message || e) });
    });
  return true; // 异步 sendResponse
});

chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());
