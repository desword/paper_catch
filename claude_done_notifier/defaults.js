// 默认配置，background / options 共用
const DEFAULTS = {
  enabled: true,
  provider: "resend",          // resend | emailjs | webhook | none
  toEmail: "",
  // Resend
  resendApiKey: "",
  resendFrom: "Claude Notifier <onboarding@resend.dev>",
  // EmailJS
  emailjsServiceId: "",
  emailjsTemplateId: "",
  emailjsPublicKey: "",
  emailjsPrivateKey: "",
  // 通用 Webhook
  webhookUrl: "",
  // 行为
  desktopNotify: true,
  onlyWhenAway: true,          // 仅在标签页不可见 / 窗口未聚焦时提醒
  minDurationSec: 10,          // 回复耗时少于该秒数则不提醒
  settleSec: 3,                // “停止”信号持续多少秒才判定完成
  includeReply: false,         // 邮件中附带回复开头片段
  extraBusySelectors: ""       // 额外“生成中”CSS 选择器，每行一个
};
