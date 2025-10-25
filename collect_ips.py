import requests
import re
import os
import time
import csv
from io import StringIO
from collections import defaultdict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================
# 基础配置
# ============================================
prefer_port = True  # ✅ 是否优先显示带端口的 IP（True=带端口排前）
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

zip_data_url = "https://zip.cm.edu.kg/all.txt"
zip_target_regions = ["JP", "SG", "KR", "HK"]
zip_count_per_region = 3

ip_pattern = r'\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?'

# ============================================
# GitHub 多源配置
# ============================================
github_sources = [
    "https://raw.githubusercontent.com/JiangXi9527/CNJX/refs/heads/main/test-ip.txt",
]
github_targets = {
    "SG": 30,
    "JP": 20,
    "KR": 20,
    "HK": 20,
}

# ============================================
# Session 带重试
# ============================================
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)

def safe_get(url, timeout=(5, 30)):
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"❌ 请求失败 {url}：{e}")
        return None

# ============================================
# 从 zip.cm.edu.kg 获取地区数据
# ============================================
def fetch_zip_region_ips(url, regions, n_each=30):
    print(f"正在从 {url} 获取指定地区数据...")
    resp = safe_get(url)
    if not resp:
        return {r: [] for r in regions}

    lines = resp.text.splitlines()
    region_keys = {
        "JP": ["JP", "Japan", "日本"],
        "KR": ["KR", "Korea", "韩国"],
    }
    results = {r: [] for r in regions}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for region, keys in region_keys.items():
            if region in regions and any(k.lower() in line.lower() for k in keys):
                m = re.search(ip_pattern, line)
                if m and len(results[region]) < n_each:
                    results[region].append(m.group(0))
                break
        if all(len(results[r]) >= n_each for r in regions):
            break
    for r in regions:
        print(f"  ✅ {r}: {len(results[r])} 条")
    return results

# ============================================
# 从 GitHub 源提取 IP
# ============================================
def fetch_github_region_ips(sources, targets):
    print(f"正在从 GitHub 源获取多地区 IP（含端口）...")
    results = {r: [] for r in targets.keys()}
    region_keys = {
        "JP": ["JP", "Japan", "日本"],
        "SG": ["SG", "Singapore", "新加坡"],
        "KR": ["KR", "Korea", "韩国"],
        "HK": ["HK", "Hong Kong", "香港"]
    }
    for src in sources:
        print(f"🔹 检索源: {src}")
        resp = safe_get(src)
        if not resp:
            continue
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
    for r, ips in results.items():
        print(f"✅ {r}: 共 {len(ips)} 个")
    return results

# ============================================
# 缓存系统
# ============================================
cache = {}
if os.path.exists("ip.txt"):
    with open("ip.txt", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("#")
            if len(parts) >= 2:
                ip, region = parts[:2]
                cache[ip] = f"{region}#缓存"

# ============================================
# 普通网页源抓取
# ============================================
ip_set = set()
for url in urls:
    resp = safe_get(url)
    if not resp:
        continue
    ips = re.findall(ip_pattern, resp.text)
    ip_set.update(ips)
    print(f"✅ 从 {url} 抓取 {len(ips)} 个 IP")

# ============================================
# 新增源：temp.csv（仅取香港/日本/新加坡 各10条）
# ============================================
extra_source = "https://raw.githubusercontent.com/chris202010/yxip/refs/heads/main/temp.csv"
print(f"🔹 从新源提取数据: {extra_source}")

region_map = {
    "JP": ["JP", "Japan", "日本"],
    "SG": ["SG", "Singapore", "新加坡"],
    "HK": ["HK", "Hong Kong", "香港"]
}
region_results = {r: [] for r in region_map.keys()}

resp = safe_get(extra_source)
if resp:
    csv_text = resp.text.strip()
    reader = csv.reader(StringIO(csv_text))
    headers = next(reader, None)
    if headers:
        lower_headers = [h.lower() for h in headers]
        has_ip = "ip" in lower_headers
        has_port = "port" in lower_headers
        has_city = any(x in lower_headers for x in ["city", "region", "country"])
        for row in reader:
            try:
                if has_ip:
                    ip = row[lower_headers.index("ip")].strip()
                else:
                    continue
                port = row[lower_headers.index("port")].strip() if has_port else ""
                city_info = ""
                for col in ["city", "region", "country"]:
                    if col in lower_headers:
                        city_info = row[lower_headers.index(col)].strip()
                        break
                ip_full = f"{ip}:{port}" if port else ip
                for region, keys in region_map.items():
                    if any(k.lower() in city_info.lower() for k in keys):
                        if len(region_results[region]) < 10:
                            region_results[region].append(ip_full)
                            cache[ip_full] = f"{region}#temp.csv"
                        break
                if all(len(region_results[r]) >= 10 for r in region_results):
                    break
            except Exception:
                continue
    total = sum(len(v) for v in region_results.values())
    print(f"✅ 从 temp.csv 提取到 {total} 个 IP（每地区最多10个）")
else:
    print(f"⚠️ 无法访问 temp.csv")

for r, ips in region_results.items():
    for ip in ips:
        ip_set.add(ip)

# ============================================
# 添加 zip 与 GitHub 数据
# ============================================
zip_ips = fetch_zip_region_ips(zip_data_url, zip_target_regions, zip_count_per_region)
for r, ips in zip_ips.items():
    for ip in ips:
        ip_set.add(ip)
        cache[ip] = f"{r}#zip.cm.edu.kg"

github_ips = fetch_github_region_ips(github_sources, github_targets)
for r, ips in github_ips.items():
    for ip in ips:
        ip_set.add(ip)
        cache[ip] = f"{r}#github"

# ============================================
# 输出结果
# ============================================
grouped = defaultdict(list)
for ip in sorted(ip_set):
    info = cache.get(ip, "未知地区#未知ISP")
    region, isp = info.split("#", 1)
    grouped[region].append((ip, isp))

with open("ip.txt", "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        f.write(f"# ===== 地区: {region} =====\n")
        sorted_ips = sorted(grouped[region], key=lambda x: (":" not in x[0], x[0])) if prefer_port else sorted(grouped[region], key=lambda x: x[0])
        for idx, (ip, isp) in enumerate(sorted_ips, 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"\n🎯 共保存 {len(ip_set)} 个唯一 IP（含 zip.cm.edu.kg、GitHub、temp.csv 三类数据）。")
