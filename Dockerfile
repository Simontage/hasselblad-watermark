# 使用 slim 镜像自动适配 ARM64/AMD64
FROM python:3.9-slim

WORKDIR /app

# 安装必要的系统库以支持 Pillow (特别是 JPEG/ZLIB)
# 这一步对于 ARM 架构 (M1/M2) 尤为重要
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建静态文件夹
RUN mkdir -p static

# 暴露端口 (5001)
EXPOSE 5001

# 使用 ENTRYPOINT 确保容器作为可执行程序运行
# JSON 数组格式 ["executable", "param1", "param2"] 确保应用成为 PID 1
ENTRYPOINT ["python", "app.py"]