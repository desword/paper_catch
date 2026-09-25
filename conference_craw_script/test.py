import os
import shutil
from git import Repo, RemoteProgress, GitCommandError

# 定义进度回调类，用于打印克隆过程的进度信息
class CloneProgress(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        percent = (cur_count / max_count * 100) if max_count else 0
        if message:
            print(f"{cur_count}/{max_count} ({percent:.2f}%) - {message}")
        else:
            print(f"{cur_count}/{max_count} ({percent:.2f}%)")

def clone_or_resume_repo(repo_url, target_dir="repo_temp"):
    """
    尝试克隆仓库，如果已存在部分克隆数据，则尝试通过 fetch 补充数据实现断点续传。
    """
    # 如果目标目录已存在，说明可能存在部分克隆内容
    if os.path.exists(target_dir):
        try:
            repo = Repo(target_dir)
            print(f"检测到已有部分克隆数据于：{target_dir}")
            # 尝试执行 fetch 来补充缺失的对象
            repo.remote().fetch(progress=CloneProgress())
            # 重置工作区到最新远端分支（根据实际仓库主分支名称，可能是 'master' 或 'main'）
            repo.git.reset('--hard', 'origin/master')
            print("断点续传成功，仓库已更新为最新版本。")
            return os.path.abspath(target_dir)
        except GitCommandError as e:
            print(f"在断点续传过程中发生错误: {e}")
            print("将删除已有目录并重新完整克隆。")
            shutil.rmtree(target_dir)
        except Exception as e:
            print(f"遇到其他错误: {e}")
            shutil.rmtree(target_dir)

    # 如果目录不存在或上面的续传失败，则重新克隆
    try:
        print(f"开始克隆仓库: {repo_url}")
        Repo.clone_from(repo_url, target_dir, progress=CloneProgress())
        return os.path.abspath(target_dir)
    except GitCommandError as e:
        print(f"完整克隆过程中出现错误: {e}")
        raise

if __name__ == "__main__":
    # 配置参数
    REPO_URL = "https://github.com/mlresearch/v235.git"
    
    try:
        repo_path = clone_or_resume_repo(REPO_URL)
        print(f"仓库路径：{repo_path}")
        # 后续可以在此处添加其他处理逻辑，如处理 PDF 文件等
    except Exception as e:
        print(f"最终执行出错: {str(e)}")