# config.py
# 项目配置文件

# Chrome 调试端口（必须与启动 Chrome 时的端口一致）
CHROME_PORT = 9222

# 用户数据目录（重要！改成你自己的）
CHROME_USER_DATA_DIR = r"C:\Users\dell\AppData\Local\Google\Chrome\User Data"

# 各平台网址
KIMI_URL = "https://www.kimi.com/"

# 响应检测配置
STABLE_WAIT_TIME = 2.0      # 文本稳定多少秒后认为生成完成
CHECK_INTERVAL = 0.5         # 检测间隔（秒）
MAX_WAIT_TIME = 120          # 最长等待时间（秒）