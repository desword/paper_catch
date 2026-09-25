import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# 全局配置
CONFERENCE_URL = "https://conferences.sigcomm.org/sigcomm/2024/program/"
ACM_DOI_PREFIX = "https://dl.acm.org/doi/"
PDF_SUFFIX = "pdf/"
OUTPUT_DIR = "sigcomm24_papers"
# HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
#     "Referer": CONFERENCE_URL
# }
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://dl.acm.org/",  # 设置来源页
    "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REQUEST_DELAY = 5  # 延长请求间隔
RETRY_TIMES = 3    # 增加重试次数


import time
import random
from selenium.webdriver import ChromeOptions, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc  # 反检测浏览器驱动

from webdriver_manager.chrome import ChromeDriverManager


def bypass_cloudflare(url):
    # 配置浏览器参数
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    # 启用Stealth插件配置
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    
    # 初始化反检测浏览器
    driver = uc.Chrome(
        options=options,
        headless=True,  # 调试阶段显示浏览器    
        driver_executable_path=ChromeDriverManager().install()
    )
    
    try:
        # 访问目标URL
        driver.get(url)
        
        # 等待可能出现的人机验证框架
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # 检查是否存在Cloudflare验证
        if "challenge.cloudflare.com" in driver.current_url:
            print("⚠️ 检测到Cloudflare验证，开始处理...")
            
            # 定位验证iframe框架
            iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title='Widget containing a Cloudflare security challenge']"))
            )
            
            # 切换至验证iframe
            driver.switch_to.frame(iframe)
            
            # 模拟人类点击行为
            checkbox = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#cf-stage > div.mark > label > input"))
            )
            
            # 生成随机点击轨迹
            actions = ActionChains(driver)
            actions.move_to_element_with_offset(checkbox, random.randint(2,5), random.randint(2,5))
            actions.pause(random.uniform(0.5, 1.2))
            actions.click()
            actions.perform()
            
            print("✅ 已模拟人工点击验证")
            
            # 等待验证通过
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "#cf-stage"))
            )
            print("🎉 Cloudflare验证已通过")
            
        return driver
    except Exception as e:
        print(f"❌ 验证失败: {str(e)}")
        driver.save_screenshot('cloudflare_error.png')
        return None

def setup_environment():
    """初始化下载环境"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"📁 下载目录已创建：{os.path.abspath(OUTPUT_DIR)}")

def extract_doi_links():
    """从会议网站提取所有DOI链接"""
    print("🔍 开始解析会议网站论文列表...")
    
    try:
        response = requests.get(CONFERENCE_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 智能定位DOI链接（根据最新网页结构调整）
        doi_links = []
        for link in soup.select('a[href^="https://dl.acm.org/doi/"]'):
            href = link.get('href')
            if href and href.startswith(ACM_DOI_PREFIX):
                doi_links.append(href)
        
        print(f"✅ 发现 {len(doi_links)} 篇论文的DOI链接")
        return list(set(doi_links))  # 去重
    
    except Exception as e:
        print(f"❌ 解析失败：{str(e)}")
        return []

def generate_pdf_url(doi_url):
    """将DOI链接转换为PDF下载链接"""
    parsed = urlparse(doi_url)
    if parsed.path.startswith('/doi/'):
        return urljoin(doi_url, parsed.path.replace('/doi/', '/doi/pdf/'))
    return None

def download_pdf(pdf_url, retries=2):
    """下载PDF文件（含重试机制）"""
    filename = pdf_url.split('/')[-2] + '.pdf'  # 从DOI生成文件名
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # 跳过已下载文件
    if os.path.exists(filepath):
        print(f"⏩ 已存在：{filename}")
        return True
    
    for attempt in range(retries + 1):
        try:
            response = requests.get(pdf_url, headers=HEADERS, stream=True, timeout=30)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024 * 1024):  # 1MB chunks
                        if chunk:
                            f.write(chunk)
                print(f"✅ 下载成功：{filename}")
                return True
            elif response.status_code == 404:
                print(f"❌ 文件未找到：{filename}")
                return False
        except Exception as e:
            if attempt < retries:
                print(f"⚠️ 下载失败（第{attempt+1}次重试）：{filename}")
                time.sleep(5)
            else:
                print(f"❌ 最终失败：{filename} - {str(e)}")
    return False


def download_with_retry(pdf_url, max_retries=RETRY_TIMES):
    """增强版下载函数（带错误诊断）"""
    filename = pdf_url.split('/')[-1] + '.pdf'
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    if os.path.exists(filepath):
        print(f"⏩ 已存在：{filename}")
        return True

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(pdf_url, headers=HEADERS, stream=True, timeout=30)
            print(f"🔧 调试信息：[{response.status_code}] {pdf_url}")

            # 处理重定向（需登录的情况）
            if response.history:
                print(f"⚠️ 需要登录验证：{response.url}")
                return False

            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024 * 1024):
                        f.write(chunk)
                print(f"✅ 下载成功：{filename}")
                return True
            elif response.status_code == 403:
                print(f"⛔ 权限不足，请确认：")
                print("1. 是否通过机构网络访问？")
                print("2. 是否拥有ACM Digital Library访问权限？")
                return False
            else:
                print(f"❌ HTTP错误 [{response.status_code}]：{filename}")
                
        except Exception as e:
            print(f"⚠️ 网络异常：{str(e)}")
            if attempt < max_retries:
                wait_time = 10 * (attempt + 1)
                print(f"⏳ 等待{wait_time}秒后重试...")
                time.sleep(wait_time)
    
    return False

def main():
    setup_environment()
    
    # 步骤1：获取所有DOI链接
    doi_links = extract_doi_links()
    if not doi_links:
        return
    
    # 步骤2：生成PDF下载链接
    pdf_urls = [generate_pdf_url(url) for url in doi_links]
    pdf_urls = [url for url in pdf_urls if url]  # 过滤无效链接
    
    # 步骤3：批量下载
    total = len(pdf_urls)
    success = 0
    for idx, url in enumerate(pdf_urls, 1):
        print(f"\n📄 正在处理 ({idx}/{total}): {url}")
        driver = bypass_cloudflare(url)
        if driver:
            print("[+] bypass cloudflare.")

            if download_with_retry(url):
                success += 1
        else:
            print("[+] failed. ..")
        time.sleep(REQUEST_DELAY)
    
    print(f"\n🎉 下载完成！成功 {success}/{total} 篇")
    if success < total:
        print("💡 解决方案建议：")
        print("1. 通过学校/公司网络访问")
        print("2. 使用机构提供的VPN服务")
        print("3. 访问本地图书馆的电子资源")

if __name__ == "__main__":
    main()