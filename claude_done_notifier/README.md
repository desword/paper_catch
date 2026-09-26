# Claude Done Notifier（Chrome 插件）

在 claude.ai 上（包括普通对话和 claude.ai/code 会话），Claude 回复完成后发邮件提醒你，也可以同时弹出桌面通知。

## 安装

1. 打开 `chrome://extensions`，右上角打开「开发者模式」。
2. 点「加载已解压的扩展程序」，选择本目录 `claude_done_notifier/`。
3. 点击工具栏里的插件图标，打开设置页，填写收件邮箱和发送方式，点「发送测试邮件」确认能收到。
4. 刷新已经打开的 claude.ai 标签页（插件只对加载后打开或刷新的页面生效）。

## 发送方式

| 方式 | 配置 | 说明 |
| --- | --- | --- |
| **Resend**（推荐） | 在 [resend.com](https://resend.com) 注册，创建 API Key | 免费额度足够个人使用。未验证域名时，发件人用 `onboarding@resend.dev`，并且只能发给注册 Resend 的邮箱，发给自己正好够用 |
| EmailJS | Service ID、Template ID、Public Key | 需要在 EmailJS 后台 Account → Security 勾选允许非浏览器调用。模板变量：`{{to_email}} {{subject}} {{message}} {{title}} {{url}}` |
| Webhook | 任意 URL | 发送 POST JSON `{to, subject, text, title, url, durationSec, reply}`，可以接自己的服务器、n8n、Make、Zapier 等 |
| 仅桌面通知 | 无需配置 | 不发邮件 |

## 检测原理

内容脚本每秒检查一次页面上是否有表示“正在生成”的元素：

- `button[aria-label="Stop response"]` 等停止按钮
- `[data-is-streaming="true"]` 的消息节点

从“生成中”变成“结束”，并且持续 `settleSec` 秒（默认 3 秒）后，就判定为回复完成。如果本轮回复耗时不少于 `minDurationSec`（默认 10 秒），就发出提醒。

默认只在你**不在该标签页**的时候提醒（标签页被切走或浏览器窗口没有聚焦）。想每次都提醒，可以在设置里关掉这一项。

如果 claude.ai 改版导致检测不到，可以在设置页的「额外生成中 CSS 选择器」里补充选择器。做法是在开发者工具里找到生成过程中才出现的停止按钮，复制它的选择器填进去。

## 隐私

- API Key 保存在 `chrome.storage.sync` 中，只在本地使用。
- 默认邮件里只有对话标题、链接和耗时。勾选「附带回复开头」后，回复的前 800 个字才会经过第三方邮件服务。
