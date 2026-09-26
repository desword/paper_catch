// 监视 claude.ai 页面：检测到“生成中”→“结束”的转变后通知 background。
(() => {
  const BUILTIN_BUSY_SELECTORS = [
    'button[aria-label="Stop response"]',
    'button[aria-label="Stop"]',
    'button[aria-label*="Stop" i][aria-label*="respon" i]',
    'button[aria-label*="interrupt" i]',
    'button[aria-label*="停止"]',
    '[data-is-streaming="true"]'
  ];

  let cfg = { ...DEFAULTS };
  let busySince = 0;       // 本轮开始生成的时间
  let idleSince = 0;       // 本轮停止信号出现的时间
  let lastReplySnippet = "";

  function loadCfg() {
    chrome.storage.sync.get(DEFAULTS, (v) => { cfg = v; });
  }
  loadCfg();
  chrome.storage.onChanged.addListener(loadCfg);

  function busySelectors() {
    const extra = (cfg.extraBusySelectors || "")
      .split("\n").map((s) => s.trim()).filter(Boolean);
    return BUILTIN_BUSY_SELECTORS.concat(extra);
  }

  function isBusy() {
    for (const sel of busySelectors()) {
      try {
        const el = document.querySelector(sel);
        if (el && (el.offsetParent !== null || el.getClientRects().length)) return true;
      } catch (_) { /* 用户填的选择器非法，忽略 */ }
    }
    return false;
  }

  function lastReply() {
    const nodes = document.querySelectorAll(
      '[data-is-streaming], .font-claude-message, .font-claude-response'
    );
    const el = nodes[nodes.length - 1];
    return el ? el.innerText.trim() : "";
  }

  function isAway() {
    return document.hidden || !document.hasFocus();
  }

  function tick() {
    if (!cfg.enabled) return;
    const now = Date.now();
    if (isBusy()) {
      if (!busySince) busySince = now;
      idleSince = 0;
      lastReplySnippet = lastReply() || lastReplySnippet;
      return;
    }
    if (!busySince) return;
    if (!idleSince) { idleSince = now; return; }
    if (now - idleSince < cfg.settleSec * 1000) return;

    // 判定为完成
    const durationSec = Math.round((idleSince - busySince) / 1000);
    busySince = 0;
    idleSince = 0;
    if (durationSec < cfg.minDurationSec) return;
    if (cfg.onlyWhenAway && !isAway()) return;

    const reply = lastReply() || lastReplySnippet;
    lastReplySnippet = "";
    try {
      chrome.runtime.sendMessage({
        type: "claude-done",
        title: document.title.replace(/\s*[-|]\s*Claude\s*$/i, "") || "Claude",
        url: location.href,
        durationSec,
        reply: cfg.includeReply ? reply.slice(0, 800) : ""
      });
    } catch (_) { /* 插件被重新加载后旧页面上下文失效，忽略 */ }
  }

  setInterval(tick, 1000);
})();
