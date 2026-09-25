import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import OrderedDict

# 基础配置
conf_name = "osdi21"
BASE_URL = f"https://www.usenix.org/conference/{conf_name}/technical-sessions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

ROOT_DIR = "../conference_pdf/"
SAVE_DIR = conf_name + "_papers"
DST_DIR = ROOT_DIR+SAVE_DIR
os.makedirs(DST_DIR, exist_ok=True)

def get_pdf_links():
    """获取所有论文PDF链接"""
    session = requests.Session()
    response = session.get(BASE_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    paper_links = []
    # 查找所有论文详情页链接（根据官网结构调整选择器）

    for link in soup.select(f'a[href*="/conference/{conf_name}/presentation/"]'):
        paper_url = urljoin(BASE_URL, link['href'])
        paper_id = paper_url.split('/')[-1]
        if "-" in paper_id:
            paper_id = paper_id.replace("-", "_")

        # 构造PDF下载链接（基于USENIX常规格式）
        pdf_url = f"https://www.usenix.org/system/files/{conf_name}-{paper_id}.pdf"

        paper_links.append(pdf_url)
        print("[+] find", pdf_url)
        time.sleep(0.2)  # 礼貌性延迟
    
    return list(set(paper_links)) # 去重

    # combined = OrderedDict()
    # for pl, pc in zip(paper_links, paper_links_candidate):
    #     if pl not in combined:
    #         combined[pl] = pc
    
    # return list(combined.keys()), list(combined.values())

def download_pdf(url):
    """下载单个PDF文件"""
    try:
        filename = url.split('/')[-1]
        save_path = os.path.join(DST_DIR, filename)
        
        # 跳过已下载文件
        if os.path.exists(save_path):
            print(f"已存在: {filename}")
            return True
            
        response = requests.get(url, headers=HEADERS, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"成功下载: {filename}")
            return True
        print(f"下载失败[{response.status_code}]: {url}")
    except Exception as e:
        print(f"异常中断: {str(e)}")
    return False


def download_candidate_pdf(url):
    """下载单个PDF文件"""
    try:
        url = url.split("_")[0] + ".pdf"

        filename = url.split('/')[-1]
        save_path = os.path.join(DST_DIR, filename)
        
        # 跳过已下载文件
        if os.path.exists(save_path):
            print(f"已存在: {filename}")
            return True
            
        response = requests.get(url, headers=HEADERS, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"成功下载: {filename}")
            return True
        print(f"下载失败[{response.status_code}]: {url}")
    except Exception as e:
        print(f"异常中断: {str(e)}")
    return False


def download_candidate_pdf_2(url):
    """下载单个PDF文件"""
    try:
        url = url.replace("_", "-")
        # url = url.split("_")[0] + ".pdf"

        filename = url.split('/')[-1]
        save_path = os.path.join(DST_DIR, filename)
        
        # 跳过已下载文件
        if os.path.exists(save_path):
            print(f"已存在: {filename}")
            return True
            
        response = requests.get(url, headers=HEADERS, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"成功下载: {filename}")
            return True
        print(f"下载失败[{response.status_code}]: {url}")
    except Exception as e:
        print(f"异常中断: {str(e)}")
    return False

if __name__ == "__main__":
    print("开始获取论文列表...")
    pdf_links = get_pdf_links()
    print(f"找到{len(pdf_links)}篇论文")
    
    success = 0
    failed_list = []
    for idx, url in enumerate(pdf_links, 1):
        print(f"正在下载({idx}/{len(pdf_links)})...")
        if download_pdf(url):
            success +=1
        elif download_candidate_pdf(url):
            success +=1
        elif download_candidate_pdf_2(url):
            success +=1
        else:
            failed_list.append(url)
        time.sleep(2)  # 降低请求频率
    
    print(f"下载完成，成功{success}篇，失败{len(pdf_links)-success}篇")
    if len(pdf_links)-success > 0:
        print("Failed pdf link list")
        print(failed_list)