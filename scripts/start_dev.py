import sys
import subprocess


def main():
    print("=== Project B: 初始化 demo 数据库 ===")
    subprocess.check_call([sys.executable, "scripts/init_demo_db.py"])

    print("\n=== Project B: 启动开发服务器 ===")
    print("访问 http://localhost:8000/health 检查服务状态")
    print("按 Ctrl+C 停止服务\n")
    subprocess.check_call([
        sys.executable, "-m", "uvicorn",
        "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000",
    ])


if __name__ == "__main__":
    main()
