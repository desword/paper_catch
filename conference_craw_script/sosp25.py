from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
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
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

#====================== 1. Extrac download link phase============================================

# ------------------ 配置参数 -------------------
conf_name = "sosp25"
TARGET_PATTERN = re.compile(r'https://dl\.acm\.org/doi/pdf/\d+\.\d+/\d+')  # 精确匹配DOI链接格式[4](@ref)
# BASE_URL = "https://dl.acm.org/doi/proceedings/10.1145/3627703?id=31"       # 示例搜索页（需替换实际目标URL）
# OUTPUT_FILE = "acm_links_{timestamp}.txt".format(timestamp=int(time.time()))
file_path = f"./{conf_name}_html/Proceedings of the ACM SIGOPS 31st Symposium on Operating Systems Principles _ ACM Conferences.html"

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
def get_links_local(file_path):
    """解析本地HTML文件获取符合规则的链接"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()
            
        soup = BeautifulSoup(html, 'html.parser')
        all_links = [a['href'] for a in soup.find_all('a', href=True)]
        
        # 保持原有过滤逻辑（参考原代码正则表达式）
        valid_links = list(filter(TARGET_PATTERN.match, all_links))
        all_links_valid = list(set(valid_links))
        return ["https://dl.acm.org/doi/pdf/" + link.split("/")[-2] + "/" + link.split("/")[-1] 
                for link in all_links_valid]

    except (FileNotFoundError, PermissionError) as e:
        print(f"文件操作失败: {str(e)}")
        return []
    except Exception as e:
        print(f"解析异常: {str(e)}")
        return []


#====================== 2. download files phase ============================================
# 设置下载路径
download_dir = f"D:\\微云同步文件夹\\办公文件夹\\PaperChat\\conference_pdf\\{conf_name}_papers"


# 浏览器配置
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "plugins.always_open_pdf_externally": True  # 强制浏览器直接下载PDF
})


def check_file_existence(filename):
    return os.path.exists(os.path.join(download_dir, filename))

def batch_download_pdf(url_list):
    # 自动管理驱动版本
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    count = 1
    for url in url_list:
        try:
            print(f"[+] Downloading, {count}/{len(url_list)}.")
            count += 1
            filename = f"{url.split("/")[-1]}.pdf"
            if os.path.exists(os.path.join(download_dir,filename) ):
                print(f"[++] {filename} exists, pass.")
                continue; 

#========================= old way.
            # print("[-]CGL start driver.get(url)")    
            driver.get(url)
            # print("[-]CGL after driver.get(url)")
            # 显式等待下载按钮加载（网页6的关键点）
            # download_btn = WebDriverWait(driver, 15).until(
            #     EC.presence_of_element_located((By.XPATH, "//a[contains(@class,'download-button')]"))
            # )
            download_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@class,'download-button')]"))
            )
            if download_btn.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView();", download_btn)
                download_btn.click()
            # print("[-]CGL after download_btn")
            # 执行点击操作（网页4的交互方法）
            # driver.execute_script("arguments[0].scrollIntoView();", download_btn)
            # # print("[-]CGL after execute_script")
            # download_btn.click()
            # # print("[-]CGL after download_btn.click")
            # # 等待下载完成（网页6的容错机制）
            # time.sleep(5 if 'preview' in url else 3)  # 根据链接类型调整等待时间
            # print("[-]CGL after sleep")

        # except Exception as e:
        except (StaleElementReferenceException, TimeoutException):
            if check_file_existence:
                print(f"下载成功 {url}")
            else:
                print(f"下载失败 {url}: {str(StaleElementReferenceException)}")
            continue
#========================= old way.

    driver.quit()

# 调用示例（包含用户提供的54个链接）
# pdf_urls = [
#     "https://dl.acm.org/doi/pdf/10.1145/3651890.3672259",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672253",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672251"
# ]

# ------------------ 执行流程 -------------------
if __name__ == "__main__":
    ua = UserAgent()
    headers = {'User-Agent': ua.random}

    print(f"Processing ...")
    # current_url = f"{BASE_URL}"  # 假设分页参数为page
    # page_links = get_links(current_url, headers)

    page_links = get_links_local(file_path)
    print(f"Obtain {len(page_links)} page links ...")
    # test_links = [
    #     "https://dl.acm.org/doi/pdf/10.1145/3651890.3672219",
    #     "https://dl.acm.org/doi/pdf/10.1145/3651890.3672235",
    #     "https://dl.acm.org/doi/pdf/10.1145/3651890.3672251"
    # ]
    batch_download_pdf(page_links)