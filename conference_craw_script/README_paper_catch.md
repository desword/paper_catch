# paper_catch.py：一个脚本搞定各会议论文下载

原来每个会议、每一年各有一个脚本（`nsdi25.py`、`sosp25.py`、`infocom24.py` ……）。
这些脚本的差别只在「**怎么拿到 PDF 链接**」，下载部分几乎一样。
所以可以合并成一个脚本，按两个阶段来做：

| 阶段 | 做什么 | 在哪跑 |
|---|---|---|
| `collect` | 拿到每篇论文的 PDF 链接，存为 `links/<conf>.json`（外加一个纯 URL 的 `.txt`） | 任何能上网的机器，不需要下载权限 |
| `download` | 读取 json，下载 PDF | 开放获取的会议任何机器都行；ACM / IEEE 放到有机构权限的电脑上跑 |

`json` 里每篇论文都有 `method` 字段，`requests` 表示可以直接下载，`browser` 表示要用浏览器下载（有权限或者有 Cloudflare 验证）。
`download` 默认 `--mode auto`，会根据这个字段自动选择下载方式。

## 旧脚本的三类情况，现在怎么处理

| 旧脚本 | 以前的做法 | 现在 |
|---|---|---|
| USENIX：nsdi / osdi / atc / fast | 解析 technical-sessions，按规律**猜** PDF 文件名，猜不中再换两种写法 | 打开每篇的 presentation 页面，读出**真实**的 PDF 链接（加 `--fast` 则沿用猜文件名的做法） |
| ACM：sigcomm / sosp / eurosys / mobicom / asplos / www | 手动把 ACM DL 目录页另存为 HTML，再用正则提取链接 | **默认走 DBLP API 拿 DOI**，不需要保存网页，也不需要权限；原来保存 HTML 的做法仍可用 `--page` |
| IEEE：infocom | 分页保存 3 个 HTML，提取 arnumber | 默认也走 DBLP（DOI 结尾就是 arnumber），一次拿全；保存的 HTML 同样可以用 `--page` |
| CVPR / NeurIPS / IJCAI / ICML 等 | 各写一个正则 | 内置 `cvf` / `neurips` / `ijcai` 解析器；其他站点用 `--pattern` 自定义正则 |

## 安装

```bash
pip install -r requirements.txt   # requests, beautifulsoup4, selenium
```

浏览器下载需要本机装有 Chrome。Selenium ≥ 4.6 会自动下载匹配版本的 chromedriver。

## 用法

```bash
cd conference_craw_script
python paper_catch.py list                     # 查看内置的会议

# ---------- 1. 收集链接 ----------
python paper_catch.py collect nsdi25           # USENIX
python paper_catch.py collect osdi2025
python paper_catch.py collect sigcomm24        # ACM，走 DBLP
python paper_catch.py collect asplos24         # 同年多卷（asplos2024-1/-2/-3）会自动合并
python paper_catch.py collect infocom24        # IEEE，走 DBLP
python paper_catch.py collect mobicom24 --min-pages 0   # 不过滤短文（poster/demo）

# 手动保存的网页 / 会议 program 页面（和以前的做法一样）
python paper_catch.py collect eurosys25 --page ./eurosys25_html/
python paper_catch.py collect infocom24 --page infocom24_html_1 infocom24_html_2 infocom24_html_3
python paper_catch.py collect asplos25  --page https://www.asplos-conference.org/asplos2025/program.html
python paper_catch.py collect icml25    --page ./icml25_html/ --pattern 'openreview\.net/pdf\?id='

# 表里没有的会议
python paper_catch.py collect nsdi26 --usenix nsdi
python paper_catch.py collect ancs24 --dblp conf/ancs
python paper_catch.py collect xxx24 --dblp-toc db/conf/xxx/xxx2024.bht

# ---------- 2. 下载 ----------
# 开放获取：直接下载
python paper_catch.py download links/nsdi25.json

# ACM / IEEE：拷 links/xxx.json 到有权限的电脑，然后
python paper_catch.py download links/sigcomm24.json --profile-dir ./chrome_profile --login
#   --profile-dir  Chrome 用户目录，登录状态会保存下来，下次不用再登录
#   --login        先打开浏览器，你手动登录机构账号或过 Cloudflare 验证，回车后开始批量下载
#   --name title   用论文标题命名 PDF（默认用 DOI 后缀 / arnumber / USENIX 文件名）
#   --only 'LLM|RDMA'  只下载标题匹配的论文
#   --limit 3      先试 3 篇

# 一步完成
python paper_catch.py run osdi25
```

下载目录默认是 `../conference_pdf/<conf>_papers/`（与旧的 USENIX 脚本相同），可以用 `--out` 修改。例如：

```bash
python paper_catch.py download links/sosp25.json --out "D:\微云同步文件夹\办公文件夹\PaperChat\conference_pdf\sosp25_papers"
```

下载目录里还会生成：
- `index.csv`：文件名、标题、DOI 的对应表
- `failed.json`：失败列表，可以直接 `python paper_catch.py download .../failed.json` 重试

已经下载好、校验为 PDF 的文件会自动跳过，中断后重跑即可续传。
旧格式的 `acm_links_xxx.txt`（每行一个带引号的 URL）也能直接交给 `download`。

## 内置会议（`python paper_catch.py list`）

- **USENIX**：nsdi, osdi, atc, fast, uss（USENIX Security）
- **ACM（DBLP）**：sigcomm, mobicom, mobisys, sensys, imc, hotnets, conext, sosp, eurosys, asplos, socc, middleware, ppopp, hpdc, isca, micro, sc, www, ccs
- **IEEE（DBLP）**：infocom, icnp, icdcs, iwqos, secon, hpca, dsn, ipdps, sp
- **开放获取列表页**：cvpr, iccv, neurips, ijcai

要加新会议，在 `paper_catch.py` 的 `CONFERENCES` 里加一行就行。

## 注意事项

- DBLP 通常在会议结束后几天到几周内收录。刚开完的会议如果 DBLP 还没有，就先用 `--page` 解析 ACM 目录页或会议 program 页。
- DBLP 来源默认过滤掉页数少于 5 的条目（poster / demo / front matter），用 `--min-pages 0` 可以关掉。
- CoNEXT 从 2023 年起发表在期刊 PACMNET，不在 `conf/conext` 下。这种情况用 `--page` 或 `--dblp-toc` 指定。
- ACM DL 自 2026 年起已全面开放获取，但 dl.acm.org 有 Cloudflare 验证，所以仍默认用浏览器下载。
- 浏览器下载的临时文件放在 `<out>/.browser_tmp/`，下载成功后会校验 `%PDF` 文件头，再重命名移到目标目录。
