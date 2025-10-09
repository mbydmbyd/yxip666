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
    'https://zip.cm.edu.kg/all.txt'  # 🌏 新增数据源
]

# IPv4 正则表达式
ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
cidr_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?'  # 支持 /24 等

# 国家关键字（只保留这些）
country_keywords = ['JP', 'Japan', 'SG', 'Singapore', 'KR', 'Korea', 'HK', 'Hong Kong']

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
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')

        # ✅ 特殊处理 zip.cm.edu.kg/all.txt
        if 'zip.cm.edu.kg/all.txt' in url:
            for line in response.text.splitlines():
                # 保留含 JP/SG/KR/HK 的行（不区分大小写）
                if any(k.lower() in line.lower() for k in country_keywords):
                    # 提取 IP 或 CIDR
                    match = re.search(cidr_pattern, line)
                    if match:
                        ip = match.group(0)
                        remark = line.split('#')[-1].strip() if '#' in line else ''
                        ip_set.add((ip, remark))  # 带备注保存
            continue  # 跳过通用提取逻辑

        # 对 HTML 页面使用 BeautifulSoup
        if 'html' in content_type:
            soup = BeautifulSoup(response.text, 'html.parser')
            if 'cloudflare.html' in url or 'ip.164746.xyz' in url:
                elements = soup.find_all('tr')
            else:
                elements = soup.find_all(['li', 'p', 'div'])
            for el in elements:
                text = el.get_text()
                ip_matches = re.findall(ip_pattern, text)
                for ip in ip_matches:
                    ip_set.add((ip, ''))  # 无备注
        else:
            # 文本接口直接正则匹配
            ip_matches = re.findall(ip_pattern, response.text)
            for ip in ip_matches:
                ip_set.add((ip, ''))

    except Exception as e:
        print(f"❌ 请求失败：{url} - {e}")

print(f"\n共提取到 {len(ip_set)} 个唯一 IP 或网段，开始查询地理信息...\n")

# IP 查询函数
def get_ip_info(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip.split('/')[0]}?lang=zh-CN", timeout=5)
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
for ip, remark in sorted(ip_set):
    if ip in cache:
        info = cache[ip]
    else:
        info = get_ip_info(ip)
        time.sleep(0.5)
    results[ip] = (info, remark)

# 分组 {地区: [(ip, isp, remark), ...]}
grouped = defaultdict(list)
for ip, (info, remark) in results.items():
    region, isp = info.split("#")
    grouped[region].append((ip, isp, remark))

# 输出文件
with open("ip.txt", "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        for idx, (ip, isp, remark) in enumerate(sorted(grouped[region]), 1):
            # 保留备注（如果有）
            if remark:
                f.write(f"{ip}#{region}-{idx}#{isp}#备注: {remark}\n")
            else:
                f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"✅ 共保存 {len(results)} 个唯一 IP，已写入 ip.txt。仅包含 JP / SG / KR / HK 区域。")
