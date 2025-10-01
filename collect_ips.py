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

# 查询 IP 所属国家/地区
def get_ip_info(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        data = r.json()
        if data["status"] == "success":
            return f"{data.get('country', '')} {data.get('regionName', '')}"
        else:
            return "未知地区"
    except:
        return "查询失败"

# 写入文件
with open('ip.txt', 'w', encoding='utf-8') as file:
    for ip in sorted(ip_set):
        location = get_ip_info(ip)
        file.write(f"{ip}  {location}\n")
        time.sleep(0.5)  # 给API留点间隔，避免封禁

print(f'共保存 {len(ip_set)} 个唯一IP地址及归属地到 ip.txt 文件中。')
