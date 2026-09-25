# paper_catch

会议论文 PDF 批量下载脚本。

使用统一脚本 [`conference_craw_script/paper_catch.py`](conference_craw_script/paper_catch.py)，说明见 [`README_paper_catch.md`](conference_craw_script/README_paper_catch.md)。

```bash
cd conference_craw_script
python paper_catch.py collect sigcomm24          # 收集链接（无需权限）
python paper_catch.py download links/sigcomm24.json --profile-dir ./chrome_profile --login   # 在有权限的电脑上下载
```
