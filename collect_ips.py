import requests
from bs4 import BeautifulSoup
import re
import os
import time
from collections import defaultdict

# 目标URL列表
urls = [
    'https://api.uouin.com/cloudflare.html',
    'https://ip.164746.xyz',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://cf.090227.xyz',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://addressesapi.090227.xyz/ip.164746.xyz',
]

# IPv4 正则表达式
ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'

# 已有缓存 {ip: "地区#ISP"}
cache = {}
if os.path.exists("ip.txt"):
    with open("ip.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "#" in line:
                parts = line.split("#")
                if len(parts) == 3:
                    ip, location, isp = parts
                    # 清理掉旧编号（防止多次运行出现 -1-1-1）
                    if "-" in location:
                        location = location.split("-")[0]
                    cache[ip] = f"{location}#{isp}"
                elif len(parts) == 2:
                    ip, location = parts
                    if "-" in location:
                        location = location.split("-")[0]
                    cache[ip] = f"{location}#未知ISP"

# 抓取IP集合
ip_set = set()

for url in urls:
    try:
        print(f"正在抓取：{url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')

        # 如果是 HTML 页面，用 BeautifulSoup 提取
        if 'html' in content_type:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 不同网站结构不同
            if 'cloudflare.html' in url or 'ip.164746.xyz' in url:
                elements = soup.find_all('tr')
            else:
                elements = soup.find_all(['li', 'p', 'div'])
            for el in elements:
                text = el.get_text()
                ip_matches = re.findall(ip_pattern, text)
                ip_set.update(ip_matches)
        else:
            # 对于 JSON 或纯文本接口，直接正则匹配
            ip_matches = re.findall(ip_pattern, response.text)
            ip_set.update(ip_matches)

    except Exception as e:
        print(f"❌ 请求失败：{url} - {e}")

print(f"\n共提取到 {len(ip_set)} 个唯一 IP，开始查询地理信息...\n")

# IP 查询函数
def get_ip_info(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        data = r.json()
        if data["status"] == "success":
            country = data.get("country", "")
            region = data.get("regionName", "")
            isp = data.get("isp", "未知ISP")
            location = f"{country} {region}".strip()
            return f"{location}#{isp}"
        else:
            return "未知地区#未知ISP"
    except Exception:
        return "查询失败#未知ISP"

# 查询并组合结果
results = {}
for ip in sorted(ip_set):
    if ip in cache:
        info = cache[ip]
    else:
        info = get_ip_info(ip)
        time.sleep(0.5)
    results[ip] = info

# 分组 {地区: [(ip, isp), ...]}
grouped = defaultdict(list)
for ip, info in results.items():
    region, isp = info.split("#")
    grouped[region].append((ip, isp))

# 输出文件
with open("ip.txt", "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        for idx, (ip, isp) in enumerate(sorted(grouped[region]), 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"✅ 共保存 {len(results)} 个唯一 IP，已写入 ip.txt。")
