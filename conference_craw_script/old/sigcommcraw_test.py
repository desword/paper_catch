import re
import time
import random
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# ------------------ 配置参数 -------------------
TARGET_PATTERN = re.compile(r'https://dl\.acm\.org/doi/\d+\.\d+/\d+')  # 精确匹配DOI链接格式[4](@ref)
BASE_URL = "https://conferences.sigcomm.org/sigcomm/2024/program/"       # 示例搜索页（需替换实际目标URL）
OUTPUT_FILE = "acm_links_{timestamp}.txt".format(timestamp=int(time.time()))


# ================== 配置区 ==================
# URLS = [
#     "https://dl.acm.org/doi/pdf/10.1145/3651890.3672259",
#     # 此处粘贴所有其他PDF链接...
# ]  # 共54个链接需填写
SAVE_DIR = "./sigcomm24"
MAX_WORKERS = 5  # 并发线程数
RETRIES = 3  # 失败重试次数
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/pdf"
}
def download_pdf(url, save_path):
    """增强型PDF下载函数"""
    for attempt in range(RETRIES):
        try:
            with requests.get(url, headers=HEADERS, stream=True, timeout=15) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                # 进度条配置
                progress = tqdm(
                    total=total_size, 
                    unit='iB',
                    unit_scale=True,
                    desc=os.path.basename(save_path)[:20],  # 显示前20字符文件名
                    leave=False
                )
                
                # 分块写入文件
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB/块
                        if chunk:
                            f.write(chunk)
                            progress.update(len(chunk))
                progress.close()
                return True
        except Exception as e:
            if attempt == RETRIES - 1:
                print(f"\n[失败] {url} | 错误: {str(e)}")
                return False

def get_filename(url):
    """从URL生成唯一文件名"""
    path = urlparse(url).path
    return path.replace('/doi/pdf/', '').replace('/', '_') + ".pdf"


def download_main_loop(urls):
        # 创建目标目录
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    # 并发下载控制
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for url in urls:
            filename = get_filename(url)
            save_path = os.path.join(SAVE_DIR, filename)
            future = executor.submit(download_pdf, url, save_path)
            futures[future] = url
        
        # 进度监控
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(futures), desc="总进度"):
            url = futures[future]
            if future.result():
                success_count += 1

    # 结果报告
    print(f"\n下载完成: {success_count}/{len(urls)} 成功 | 存储目录: {os.path.abspath(SAVE_DIR)}")

# ------------------ 核心函数 -------------------
def get_links(url, headers):
    """爬取单页中所有符合规则的链接"""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取所有可能的链接元素
        all_links = [a['href'] for a in soup.find_all('a', href=True)]
        
        # 过滤匹配目标格式的链接
        valid_links = list(filter(TARGET_PATTERN.match, all_links))
        all_links_valid = list(set(valid_links))
        all_links_valid_now = []
        for eachlink in all_links_valid:
            all_links_valid_now.append("https://dl.acm.org/doi/pdf/" + eachlink.split("/")[-2] + "/"+ eachlink.split("/")[-1])
        return all_links_valid_now  # 去重
    
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return []

# ------------------ 执行流程 -------------------
if __name__ == "__main__":
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    # all_links = []

    # # 示例：爬取前3页（根据实际分页规则调整）
    # for page in range(1, 4):
    #     print(f"Processing page {page}...")
    #     current_url = f"{BASE_URL}&page={page}"  # 假设分页参数为page
    #     page_links = get_links(current_url, headers)
    #     all_links.extend(page_links)
        
    #     # 随机延迟防止高频请求[3](@ref)
    #     time.sleep(random.uniform(1, 3))  

    print(f"Processing ...")
    current_url = f"{BASE_URL}"  # 假设分页参数为page
    page_links = get_links(current_url, headers)
    # all_links.extend(page_links)

    # 随机延迟防止高频请求[3](@ref)
    # time.sleep(random.uniform(1, 3))  

    # 持久化存储
    # with open(OUTPUT_FILE, 'w') as f:
    #     f.write("\n".join(all_links))
    # print(f"Success! Saved {len(all_links)} links to {OUTPUT_FILE}")

    download_main_loop(page_links)