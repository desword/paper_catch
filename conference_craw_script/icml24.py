# 1. enter this site: https://github.com/mlresearch
# 2. search ICML. then we will find the github pages, and then git clone them. https://github.com/mlresearch/v235/tree/main
# 3. move single paper from each single folder, and merge them into a single folder. [This script doing this thing.]

import os
import shutil

# 输入源文件夹路径和目标文件夹路径
# dest_folder = "D:\\微云同步文件夹\\办公文件夹\\PaperChat\\conference_pdf\\icml24"

conf_name = "icml24_papers"
Root_folder = "../conference_pdf/"
dest_folder = Root_folder + conf_name
src_folder = Root_folder + "v235-main\\v235-main"


def move_pdfs(src_folder, dest_folder):
    """
    移动 src_folder 及其子文件夹下所有的 PDF 文件到 dest_folder 中。
    如果目标文件夹中存在同名文件，则在文件名后添加序号。
    """
    # 遍历 src_folder 中所有子目录和文件
    for root, dirs, files in os.walk(src_folder):
        for file in files:
            if file.lower().endswith('.pdf'):
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_folder, file)
                
                # 检查目标文件夹中是否已有同名文件
                if os.path.exists(dest_file_path):
                    base, ext = os.path.splitext(file)
                    counter = 1
                    new_file = f"{base}_{counter}{ext}"
                    dest_file_path = os.path.join(dest_folder, new_file)
                    
                    # 如果新文件名仍然存在则继续加序号
                    while os.path.exists(dest_file_path):
                        counter += 1
                        new_file = f"{base}_{counter}{ext}"
                        dest_file_path = os.path.join(dest_folder, new_file)
                
                # 移动文件
                shutil.move(src_file_path, dest_file_path)
                print(f"移动文件: {src_file_path} -> {dest_file_path}")

if __name__ == "__main__":
    # # 输入源文件夹路径和目标文件夹路径
    # src_folder = input("请输入源文件夹路径: ").strip()
    # dest_folder = input("请输入目标文件夹路径: ").strip()
    
    # 如果目标文件夹不存在，则创建一个
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
    
    move_pdfs(src_folder, dest_folder)
    
    print("所有 PDF 文件已成功移动。")
