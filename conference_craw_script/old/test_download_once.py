from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# 设置下载路径
# download_dir = "./sigcomm24"
download_dir = "D:\\微云同步文件夹\\办公文件夹\\PaperChat\\conference_craw_script\\sigcomm24_papers"


# 浏览器配置
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "plugins.always_open_pdf_externally": True  # 强制浏览器直接下载PDF
})

from selenium.webdriver.chrome.service import Service

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def batch_download_pdf(url_list):
    # 自动管理驱动版本
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    for url in url_list:
        try:
            driver.get(url)
            
            # 显式等待下载按钮加载（网页6的关键点）
            download_btn = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@class,'download-button')]"))
            )
            
            # 执行点击操作（网页4的交互方法）
            driver.execute_script("arguments[0].scrollIntoView();", download_btn)
            download_btn.click()
            
            # 等待下载完成（网页6的容错机制）
            time.sleep(5 if 'preview' in url else 3)  # 根据链接类型调整等待时间
            
        except Exception as e:
            print(f"下载失败 {url}: {str(e)}")
            continue
    
    driver.quit()

# 调用示例（包含用户提供的54个链接）
pdf_urls = [
    "https://dl.acm.org/doi/pdf/10.1145/3651890.3672259",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672249",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672243",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672248",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672252",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672267",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672272",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672231",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672221",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672242",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672238",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672220",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672236",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672226",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672263",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672264",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672218",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672265",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672235",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672268",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672244",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672239",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672222",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672245",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672223",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672270",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672214",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672269",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672230",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672255",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672250",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672232",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672215",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672217",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672260",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672266",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672227",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672254",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672258",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672257",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672274",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672237",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672241",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672234",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672271",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672273",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672247",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672261",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672225",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672262",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672228",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672233",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672216",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672240",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672246",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672224",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672256",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672213",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672229",
# "https://dl.acm.org/doi/pdf/10.1145/3651890.3672219",
"https://dl.acm.org/doi/pdf/10.1145/3651890.3672253",
"https://dl.acm.org/doi/pdf/10.1145/3651890.3672251"
]
batch_download_pdf(pdf_urls)