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
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/bestcf.txt'
]

zip_data_url = "https://zip.cm.edu.kg/all.txt"  # 🇯🇵🇸🇬🇰🇷🇭🇰 数据源
zip_target_regions = ["JP", "SG", "KR", "HK"]
zip_count_per_region = 30  # 每个地区取 30 条

ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'

# ============================================
# GitHub 多源设置（可自定义）
# ============================================
github_sources = [
    "https://raw.githubusercontent.com/JiangXi9527/CNJX/refs/heads/main/test-ip.txt",
    # "https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/bestcf.txt",
    # 可以再添加更多源
]

# 每个地区要取多少条（仅 GitHub 源使用）
github_targets = {
    "SG": 30,  # 新加坡
    "JP": 20,  # 日本
    "KR": 20,  # 韩国
    "HK": 20,  # 香港
}

# ============================================
# 从 zip.cm.edu.kg/all.txt 获取地区数据
# ============================================
def fetch_zip_region_ips(url, regions, n_each=30):
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
    cidr_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?'

    def belongs_region(line, keys):
        line_lower = line.lower()
        return any(k.lower() in line_lower for k in keys)

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
# 从多个 GitHub 源中提取各地区 IP（不查 ISP）
# ============================================
def fetch_github_region_ips(sources, targets):
    print(f"正在从 GitHub 源获取多地区 IP...")
    results = {r: [] for r in targets.keys()}
    region_keys = {
        "JP": ["JP", "Japan", "日本"],
        "SG": ["SG", "Singapore", "新加坡"],
        "KR": ["KR", "Korea", "韩国"],
        "HK": ["HK", "Hong Kong", "香港"]
    }

    for src in sources:
        print(f"🔹 检索源: {src}")
        try:
            resp = requests.get(src, timeout=10)
            resp.raise_for_status()
            lines = resp.text.splitlines()
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                for region, keys in region_keys.items():
                    if region not in targets:
                        continue
                    if any(k.lower() in stripped.lower() for k in keys):
                        m = re.search(ip_pattern, stripped)
                        if m and len(results[region]) < targets[region]:
                            results[region].append(m.group(0))
                            break
            time.sleep(0.3)
        except Exception as e:
            print(f"❌ 请求 {src} 失败: {e}")

    for r, ips in results.items():
        print(f"✅ {r}: 共获取 {len(ips)} 个 IP")
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
        ip_set.add(ip)
        cache[ip] = f"{region}#zip.cm.edu.kg"

# ============================================
# 添加 GitHub 多源数据
# ============================================
github_region_ips = fetch_github_region_ips(github_sources, github_targets)
for region, ips in github_region_ips.items():
    for ip in ips:
        ip_set.add(ip)
        cache[ip] = f"{region}#github"

# ============================================
# 查询 IP 所属国家/地区/ISP（对非 zip/github 源）
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

print(f"\n🎯 共保存 {len(results)} 个唯一 IP 地址（含 zip.cm.edu.kg 各区与 GitHub 多源数据）。")
