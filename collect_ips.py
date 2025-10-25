import requests
import re
import os
import time
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
zip_count_per_region = 30

# ✅ 改进的 IP+端口匹配
ip_pattern = r'\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?'

# ============================================
# GitHub 多源配置
# ============================================
github_sources = [
    "https://raw.githubusercontent.com/JiangXi9527/CNJX/refs/heads/main/test-ip.txt",
    "https://raw.githubusercontent.com/chris202010/yxip/refs/heads/main/city.txt",
]
github_targets = {
    "SG": 30,
    "JP": 20,
    "KR": 20,
    "HK": 20,
    "TW": 20,
}

# ============================================
# 全局 requests Session（带重试）
# ============================================
session = requests.Session()
retries = Retry(
    total=3,  # 重试次数
    backoff_factor=2,  # 每次重试延迟递增
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)

def safe_get(url, timeout=(5, 30)):
    """带容错与重试的请求函数"""
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.exceptions.Timeout:
        print(f"⏰ 请求超时: {url}")
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {url} | 原因: {e}")
    return None

# ============================================
# 从 zip.cm.edu.kg 获取地区数据
# ============================================
def fetch_zip_region_ips(url, regions, n_each=30):
    print(f"正在从 {url} 获取指定地区数据...")
    resp = safe_get(url, timeout=(5, 40))
    if not resp:
        print(f"⚠️ 无法访问 {url}，跳过该数据源。")
        return {r: [] for r in regions}

    lines = resp.text.splitlines()

    region_keys = {
        "JP": ["JP", "Japan", "日本"],
        "KR": ["KR", "Korea", "韩国"],
    }

    results = {r: [] for r in regions}

    def belongs_region(line, keys):
        return any(k.lower() in line.lower() for k in keys)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        for region, keys in region_keys.items():
            if region in regions and belongs_region(stripped, keys):
                m = re.search(ip_pattern, stripped)
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
# 从多个 GitHub 源提取各地区 IP
# ============================================
def fetch_github_region_ips(sources, targets):
    print(f"正在从 GitHub 源获取多地区 IP（含端口）...")
    results = {r: [] for r in targets.keys()}
    region_keys = {
        "JP": ["JP", "Japan", "日本"],
        "SG": ["SG", "Singapore", "新加坡"],
        "KR": ["KR", "Korea", "韩国"],
        "HK": ["HK", "Hong Kong", "香港"],
        "TW": ["TW", "Tai Wang", "台湾","台北","TYP","TP"]
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
        print(f"✅ {r}: 共获取 {len(ips)} 个 IP（含端口）")
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
    resp = safe_get(url)
    if not resp:
        continue
    html_text = resp.text
    ip_matches = re.findall(ip_pattern, html_text)
    ip_set.update(ip_matches)
    print(f"✅ 从 {url} 抓取到 {len(ip_matches)} 个 IP（含端口）")

# ============================================
# 添加 zip.cm.edu.kg 数据
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
# 查询 IP 信息（跳过 zip/github 源）
# ============================================
def get_ip_info(ip):
    try:
        ip_no_port = ip.split(":")[0]
        r = safe_get(f"http://ip-api.com/json/{ip_no_port}?lang=zh-CN", timeout=(3, 8))
        if not r:
            return "查询失败#未知ISP"
        data = r.json()
        if data.get("status") == "success":
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
        if prefer_port:
            sorted_ips = sorted(grouped[region], key=lambda x: (":" not in x[0], x[0]))
        else:
            sorted_ips = sorted(grouped[region], key=lambda x: x[0])

        for idx, (ip, isp) in enumerate(sorted_ips, 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"\n🎯 共保存 {len(results)} 个唯一 IP 地址（{'带端口优先' if prefer_port else '普通排序'}，含 zip.cm.edu.kg 与 GitHub 多源数据）。")
