
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
conf_name = "icml25"

TARGET_PATTERN = re.compile(r'https:\/\/openreview\.net\/pdf\?id=[a-zA-Z0-9]')  # 精确匹配DOI链接格式[4](@ref)
# BASE_URL = "https://dl.acm.org/doi/proceedings/10.1145/3627703?id=31"       # 示例搜索页（需替换实际目标URL）
# OUTPUT_FILE = "acm_links_{timestamp}.txt".format(timestamp=int(time.time()))
file_path = f"./{conf_name}_html/ICML 2025 Accepted Paper List - Paper Copilot.html"
# 设置下载路径
download_dir = f"D:\\微云同步文件夹\\办公文件夹\\PaperChat\\conference_pdf\\{conf_name}_papers"




# ------------------ 核心函数 -------------------

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
        return all_links_valid
        # return ["https://dl.acm.org/doi/pdf/" + link.split("/")[-2] + "/" + link.split("/")[-1] 
        #         for link in all_links_valid]

    except (FileNotFoundError, PermissionError) as e:
        print(f"文件操作失败: {str(e)}")
        return []
    except Exception as e:
        print(f"解析异常: {str(e)}")
        return []


#====================== 2. download files phase ============================================

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

# --- 核心函数 ---

def get_actual_filename_from_url(url, session):
    """
    使用 requests 发送请求，从 Content-Disposition 响应头中获取真实的文件名。
    这是一个轻量级的操作，避免了启动整个浏览器。
    """
    try:
        # 使用 stream=True，这样请求不会立即下载整个文件内容，只获取响应头
        with session.get(url, allow_redirects=True, stream=True, timeout=20) as response:
            # 检查请求是否成功
            response.raise_for_status()
            
            # 检查 'Content-Disposition' 响应头
            content_disposition = response.headers.get('Content-Disposition')
            if content_disposition:
                # 使用正则表达式从头信息中提取文件名
                # 例如: 'inline; filename="5001_Policy_Design_for_Two_sid.pdf"'
                fn_match = re.search('filename="(.+)"', content_disposition)
                if fn_match:
                    filename = fn_match.group(1)
                    # 对文件名进行清理，防止包含不安全字符
                    return re.sub(r'[\\/*?:"<>|]', "", filename)

            # 如果没有 Content-Disposition，尝试从 URL 的最后一部分猜测
            # 对于 openreview 链接，这通常是备用方案
            parsed_url = requests.utils.urlparse(url)
            query_id = requests.utils.parse_qs(parsed_url.query).get('id', [None])[0]
            if query_id:
                return f"{query_id}.pdf"

    except requests.exceptions.RequestException as e:
        print(f"[!] 获取文件名时发生网络错误: {e}")
    except Exception as e:
        print(f"[!] 解析文件名时发生未知错误: {e}")
        
    return None

def wait_for_download_complete(directory, filename, timeout=300):
    """
    等待指定文件下载完成。
    通过检查 .crdownload 临时文件是否存在来判断。
    """
    filepath = os.path.join(directory, filename)
    temp_filepath = filepath + '.crdownload'
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(filepath) and not os.path.exists(temp_filepath):
            # 确保文件大小稳定，防止文件刚创建但内容未写完
            last_size = os.path.getsize(filepath)
            time.sleep(1)
            if last_size > 0 and last_size == os.path.getsize(filepath):
                return True
        time.sleep(1)
    print(f"[!] 下载文件 '{filename}' 超时。")
    return False


def batch_download_pdf(url_list):
    """
    批量下载PDF文件，并在下载前检查文件是否已存在。
    """
    # --- 浏览器配置 ---
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # 可选：无头模式，不在屏幕上显示浏览器窗口
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    })
    
    # 使用 requests.Session 来复用TCP连接，提高效率
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    # --- Selenium WebDriver 初始化 ---
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    total_urls = len(url_list)
    for i, url in enumerate(url_list):
        print("-" * 50)
        print(f"[+] 正在处理第 {i+1}/{total_urls} 个链接: {url}")
        
        # 1. 从 URL 获取真实的文件名
        actual_filename = get_actual_filename_from_url(url, session)
        
        if not actual_filename:
            print(f"[!] 无法确定文件名，跳过此链接。")
            continue
            
        print(f"[*] 解析到的真实文件名为: '{actual_filename}'")
        
        # 2. 检查文件是否已经存在于下载目录
        filepath = os.path.join(download_dir, actual_filename)
        if os.path.exists(filepath):
            print(f"[>>] 文件 '{actual_filename}' 已存在，跳过下载。")
            continue
            
        # 3. 如果文件不存在，则使用 Selenium 进行下载
        try:
            print(f"[-] 文件不存在，开始下载...")
            # 对于 openreview.net 的直链，直接访问即可触发下载
            driver.get(url)
            
            # 4. 等待下载完成
            if wait_for_download_complete(download_dir, actual_filename):
                print(f"[✔] 成功下载: {actual_filename}")
            else:
                print(f"[✘] 下载失败或超时: {actual_filename}")

        except Exception as e:
            print(f"[✘] 使用 Selenium 下载时出错: {e}")

    print("-" * 50)
    print("[*] 所有下载任务处理完毕。")
    driver.quit()
    session.close()
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
