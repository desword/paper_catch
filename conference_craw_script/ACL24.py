## main entry: https://aclanthology.org/
## https://aclanthology.org/events/acl-2024/#2024findings-acl
## this conference, can directly download the full proceedings papers as a single pdf. Then, we may be able to split them into multiple pdfs.
# according to the paper introduction section  content.

import os
import re
import requests
from pdfminer.high_level import extract_text
from PyPDF2 import PdfReader, PdfWriter

def download_pdf(url, output_path):
    """
    下载 PDF 文件，并保存到指定路径
    :param url: PDF 文件下载链接
    :param output_path: 本地保存路径
    :return: 下载后文件的路径
    """
    print(f"开始下载 PDF 文件: {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()  # 如果请求出错则抛出异常
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"下载完成，文件保存为: {output_path}")
    return output_path

def detect_paper_boundaries(input_pdf_path):
    """
    自动识别每篇论文的起始页。
    如果每篇论文的第一页包含特定关键词（例如 "Abstract" 或 "Introduction"），
    则认为该页为论文的起始页。

    :param input_pdf_path: 原始大 PDF 文件路径
    :return: boundaries - 每篇论文的起始页列表（页码从1开始），
             total_pages - PDF 的总页数
    """
    boundaries = []
    # 采用 PyPDF2 获取 PDF 文件总页数
    with open(input_pdf_path, "rb") as f:
        reader = PdfReader(f)
        total_pages = len(reader.pages)
    print(f"该 PDF 文件共有 {total_pages} 页")

    # 遍历每一页，使用 pdfminer 提取文本判断是否包含论文关键字
    for page_num in range(1, total_pages + 1):
        text = extract_text(input_pdf_path, page_numbers=[page_num - 1])
        if re.search(r"Abstract", text) or re.search(r"Introduction", text):
            boundaries.append(page_num)
    
    print(f"检测到论文起始页: {boundaries}")
    return boundaries, total_pages

# def split_pdf(input_pdf_path, boundaries, total_pages):
#     """
#     根据论文起始页边界拆分 PDF 文件为多个较小的 PDF 文件

#     :param input_pdf_path: 原始大 PDF 文件路径
#     :param boundaries: 每篇论文的起始页列表（页码从1开始）
#     :param total_pages: PDF 总页数
#     """
#     with open(input_pdf_path, "rb") as f:
#         reader = PdfReader(f)
#         if not boundaries:
#             print("未检测到论文分界，无法拆分！")
#             return

#         num_papers = len(boundaries)
#         for i, start_page in enumerate(boundaries):
#             if i < num_papers - 1:
#                 end_page = boundaries[i + 1] - 1
#             else:
#                 end_page = total_pages

#             writer = PdfWriter()
#             # 注意：PyPDF2 的页码是从 0 开始计数的
#             for p in range(start_page - 1, end_page):
#                 writer.add_page(reader.pages[p])
            
#             output_filename = f"paper_{i+1}.pdf"
#             with open(output_filename, "wb") as out_file:
#                 writer.write(out_file)
#             print(f"生成文件：{output_filename}，页码范围：{start_page} - {end_page}")

def split_pdf(input_pdf_path, boundaries, total_pages, output_dir='output'):
    """
    根据论文起始页边界拆分 PDF 文件为多个较小的 PDF 文件

    :param input_pdf_path: 原始大 PDF 文件路径
    :param boundaries: 每篇论文的起始页列表（页码从1开始）
    :param total_pages: PDF 总页数
    :param output_dir: 输出目录路径（默认为当前目录下的output文件夹）
    """
    # 确保输出目录存在[1,2,5](@ref)
    os.makedirs(output_dir, exist_ok=True)

    with open(input_pdf_path, "rb") as f:
        reader = PdfReader(f)
        if not boundaries:
            print("未检测到论文分界，无法拆分！")
            return

        num_papers = len(boundaries)
        for i, start_page in enumerate(boundaries):
            if i < num_papers - 1:
                end_page = boundaries[i + 1] - 1
            else:
                end_page = total_pages

            writer = PdfWriter()
            # 注意：PyPDF2 的页码是从 0 开始计数的
            for p in range(start_page - 1, end_page):
                writer.add_page(reader.pages[p])
            
            # 拼接输出路径[6,7,8](@ref)
            output_filename = f"paper_{i+1}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, "wb") as out_file:
                writer.write(out_file)
            print(f"生成文件：{output_path}，页码范围：{start_page} - {end_page}")

def main():
    # 配置参数：指定 PDF 下载链接和本地保存文件名
    # pdf_url = "http://example.com/path/to/your/huge_proceedings.pdf"  # 请替换为实际链接
    # downloaded_pdf = "downloaded_proceedings.pdf"
    downloaded_pdf = "D:\\微云同步文件夹\\办公文件夹\\PaperChat\\conference_pdf\\acl24\\2024.acl-long.pdf"

    # 下载 PDF 文件
    # download_pdf(pdf_url, downloaded_pdf)
    
    # 检测论文起始边界
    boundaries, total_pages = detect_paper_boundaries(downloaded_pdf)
    
    # 根据检测到的边界拆分 PDF 文件
    split_pdf(downloaded_pdf, boundaries, total_pages)

if __name__ == "__main__":
    main()


