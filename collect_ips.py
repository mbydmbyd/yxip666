import requests
import re
import os
import time
from collections import defaultdict

# ============================================
# 基础配置
# ============================================
urls = [
    'https://api.uouin.com/cloudflare.html',
    'https://ip.164746.xyz',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://cf.090227.xyz',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://addressesapi.090227.xyz/ip.164746.xyz',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true'
]

zip_data_url = "https://zip.cm.edu.kg/all.txt"  # 🇯🇵🇸🇬🇰🇷🇭🇰 数据源
zip_target_regions = ["JP", "SG", "KR", "HK"]
zip_count_per_region = 20  # 每个地区取 20 条

ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'

# ============================================
# 从 zip.cm.edu.kg/all.txt 获取 JP/SG/KR/HK 数据
# ============================================
def fetch_zip_region_ips(url, regions, n_each=20):
    """从 zip.cm.edu.kg/all.txt 抓取各地区各 n 个 IP"""
    print(f"正在从 {url} 获取指定地区数据...")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    lines = resp.text.splitlines()

    region_keys = {
        "JP": ["JP", "Japan", "日本"],
        "SG": ["SG", "Singapore", "新加坡"],
        "KR": ["KR", "Korea", "韩国"],
        "HK": ["HK", "Hong Kong", "香港"]
    }

    results = {r: [] for r in regions}

    def belongs_region(line, keys):
        line_lower = line.lower()
        for k in keys:
            if k.lower() in line_lower:
                return True
        return False

    cidr_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?'

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        for region, keys in region_keys.items():
            if region in regions and belongs_region(stripped, keys):
                m = re.search(cidr_pattern, stripped)
                if m and len(results[region]) < n_each:
                    results[region].append(m.group(0))
                break
        if all(len(results[r]) >= n_each for r in regions):
            break

    print("✅ 获取完毕：")
    for r in regions:
        print(f"  {r}: {len(results[r])} 条")
    return results

# ============================================
# 缓存系统
# ============================================
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

# ============================================
# 普通网页源抓取
# ============================================
ip_set = set()
for url in urls:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        html_text = response.text
        ip_matches = re.findall(ip_pattern, html_text)
        ip_set.update(ip_matches)
        print(f"✅ 从 {url} 抓取到 {len(ip_matches)} 个 IP")
    except Exception as e:
        print(f"❌ 请求 {url} 失败: {e}")

# ============================================
# 添加 zip.cm.edu.kg 的数据
# ============================================
zip_region_ips = fetch_zip_region_ips(zip_data_url, zip_target_regions, zip_count_per_region)
for region, ips in zip_region_ips.items():
    for ip in ips:
        ip_set.add(ip)  # 加入总集合
        cache[ip] = f"{region}#zip.cm.edu.kg"  # 不查ISP，直接标记来源

# ============================================
# 查询 IP 所属国家/地区/ISP（对非 zip 源）
# ============================================
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

results = {}
for ip in sorted(ip_set):
    if ip in cache:
        info = cache[ip]
    else:
        info = get_ip_info(ip)
        time.sleep(0.5)
    results[ip] = info

# ============================================
# 按地区分组 + 编号输出
# ============================================
grouped = defaultdict(list)
for ip, info in results.items():
    region, isp = info.split("#")
    grouped[region].append((ip, isp))

with open("ip.txt", "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        for idx, (ip, isp) in enumerate(sorted(grouped[region]), 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"\n🎯 共保存 {len(results)} 个唯一 IP 地址，含 zip.cm.edu.kg 各区 20 条数据。")
