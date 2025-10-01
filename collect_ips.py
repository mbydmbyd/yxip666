import requests
import re
import os
import time

# 目标URL列表
urls = [
    'https://api.uouin.com/cloudflare.html',
    'https://ip.164746.xyz'
]

# IPv4正则
ip_pattern = r'(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])' \
             r'(?:\.(?:\d{1,2}|1\d{2}|2[0-4]\d|25[0-5])){3}'

# 已有缓存字典 {ip: "国家 省份#ISP"}
cache = {}

# 如果 ip.txt 已存在，读取缓存
if os.path.exists("ip.txt"):
    with open("ip.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "#" in line:
                parts = line.split("#")
                if len(parts) == 3:
                    ip, location, isp = parts
                    cache[ip] = f"{location}#{isp}"
                elif len(parts) == 2:
                    ip, location = parts
                    cache[ip] = f"{location}#未知ISP"

# 用集合去重
ip_set = set()

# 抓取网页并提取IP
for url in urls:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        html_text = response.text
        ip_matches = re.findall(ip_pattern, html_text)
        ip_set.update(ip_matches)
    except Exception as e:
        print(f"请求 {url} 失败: {e}")

# 查询 IP 所属国家/地区/ISP
def get_ip_info(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        data = r.json()
        if data["status"] == "success":
            location = f"{data.get('country', '')} {data.get('regionName', '')}".strip()
            isp = data.get("isp", "未知ISP")
            return f"{location}#{isp}"
        else:
            return "未知地区#未知ISP"
    except:
        return "查询失败#未知ISP"

# 最终结果字典
results = {}

for ip in sorted(ip_set):
    if ip in cache:
        info = cache[ip]  # 用缓存
    else:
        info = get_ip_info(ip)
        time.sleep(0.5)  # 防止API调用过快
    results[ip] = info

# 写入文件（覆盖写入）
with open("ip.txt", "w", encoding="utf-8") as f:
    for ip, info in sorted(results.items()):
        f.write(f"{ip}#{info}\n")

print(f"共保存 {len(results)} 个唯一IP地址、归属地和ISP到 ip.txt 文件中（含缓存）。")
