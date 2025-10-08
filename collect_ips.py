import requests
from bs4 import BeautifulSoup
import re
import os
import time
from collections import defaultdict
import io
import csv

# 🌏 让用户选择目标地区
target_country = input("请输入要筛选的国家代码（如 SG、JP、KR）：").strip().lower()

# 目标URL列表
urls = [
    'https://api.uouin.com/cloudflare.html',
    'https://ip.164746.xyz',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://cf.090227.xyz',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://addressesapi.090227.xyz/ip.164746.xyz',
    'https://api.cloudflare.com/local-ip-ranges.csv',  # ✅ 新增 Cloudflare 官方 IP 段接口
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

        # ✅ 特殊处理 Cloudflare CSV 接口
        if "cloudflare.com/local-ip-ranges.csv" in url:
            csv_text = response.text
            reader = csv.DictReader(io.StringIO(csv_text))
            for row in reader:
                # 转为小写统一匹配
                row_str = " ".join(row.values()).lower()
                # 匹配目标国家（如 sg / singapore）
                if target_country in row_str or {
                    "sg": "singapore",
                    "jp": "japan",
                    "kr": "korea"
                }.get(target_country, "") in row_str:
                    # 提取 IPv4 地址
                    for value in row.values():
                        ips = re.findall(ip_pattern, value)
                        ip_set.update(ips)
            continue  # ✅ 跳过后续HTML逻辑，进入下一个URL

        # 其他网站抓取逻辑
        if 'html' in content_type:
            soup = BeautifulSoup(response.text, 'html.parser')
            if 'cloudflare.html' in url or 'ip.164746.xyz' in url:
                elements = soup.find_all('tr')
            else:
                elements = soup.find_all(['li', 'p', 'div'])
            for el in elements:
                text = el.get_text()
                ip_matches = re.findall(ip_pattern, text)
                ip_set.update(ip_matches)
        else:
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
output_file = f"ip_{target_country.upper()}.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        for idx, (ip, isp) in enumerate(sorted(grouped[region]), 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"✅ 共保存 {len(results)} 个唯一 IP，已写入 {output_file}。")
