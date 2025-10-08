import requests
from bs4 import BeautifulSoup
import re
import os
import time
from collections import defaultdict
import io
import csv

# ---------- 输入（支持多国，兼容非交互环境） ----------
try:
    target_input = input("请输入要筛选的国家代码（如 SG,JP,KR，可用逗号分隔，回车默认为 SG）：").strip().lower()
except EOFError:
    # 非交互环境时回退到环境变量或默认 sg
    target_input = os.environ.get("TARGET_COUNTRIES", "sg").strip().lower()

if not target_input:
    target_input = "sg"

# 支持逗号或空格分隔
target_countries = [c.strip() for c in re.split(r'[,\s]+', target_input) if c.strip()]
if not target_countries:
    target_countries = ["sg"]

# 映射（用于在 CSV 行说明中匹配全称）
country_map = {
    "sg": "singapore",
    "jp": "japan",
    "kr": "korea",
    "hk": "hong kong",
    "tw": "taiwan",
    "us": "united states",
    "de": "germany",
}

# ---------- 目标URL列表 ----------
urls = [
    'https://api.uouin.com/cloudflare.html',
    'https://ip.164746.xyz',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://cf.090227.xyz',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://addressesapi.090227.xyz/ip.164746.xyz',
    'https://api.cloudflare.com/local-ip-ranges.csv',  # Cloudflare 官方 CSV
]

# 匹配 IPv4（以及可能跟随的 /CIDR），我们只取基地址
ip_cidr_pattern = r'(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?'

session = requests.Session()
session.headers.update({"User-Agent": "cf-ip-collector/1.0"})

# ---------- 读取已有缓存（更稳健地解析含多 # 的行） ----------
cache = {}
if os.path.exists("ip.txt"):
    with open("ip.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "#" in line:
                parts = line.split("#")
                ip = parts[0]
                if len(parts) >= 3:
                    location = parts[1]
                    isp = "#".join(parts[2:])  # 合并剩余部分为 ISP（以防 ISP 内含 #）
                elif len(parts) == 2:
                    location = parts[1]
                    isp = "未知ISP"
                else:
                    continue
                if "-" in location:
                    location = location.split("-")[0]
                cache[ip] = f"{location}#{isp}"

# ---------- 抓取 IP 集合 ----------
ip_set = set()
cf_counts = defaultdict(set)  # 记录从 csv 中每个国家匹配到的 ip（便于统计）

for url in urls:
    try:
        print(f"正在抓取：{url}")
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        content_type = (resp.headers.get('Content-Type') or "").lower()

        # 特殊处理 Cloudflare CSV
        if "cloudflare.com/local-ip-ranges.csv" in url:
            csv_text = resp.text
            reader = csv.DictReader(io.StringIO(csv_text))
            for row in reader:
                # 把所有值转成字符串，避免 None 导致 join 报错
                vals = ["" if v is None else str(v) for v in row.values()]
                row_str = " ".join(vals).lower()

                # 判断是否匹配任一目标国家
                matched = []
                for tc in target_countries:
                    if tc in row_str or country_map.get(tc, "") in row_str:
                        matched.append(tc)

                if matched:
                    # 从每个字段里提取 IPv4（含 CIDR）
                    for v in vals:
                        for base_ip in re.findall(ip_cidr_pattern, v):
                            ip_set.add(base_ip)
                            for tc in matched:
                                cf_counts[tc].add(base_ip)
            continue  # 处理完 CSV 后跳下一 URL

        # 其他站点
        if 'html' in content_type:
            soup = BeautifulSoup(resp.text, 'html.parser')
            if 'cloudflare.html' in url or 'ip.164746.xyz' in url:
                elements = soup.find_all('tr')
            else:
                elements = soup.find_all(['li', 'p', 'div'])
            for el in elements:
                text = el.get_text()
                for base_ip in re.findall(ip_cidr_pattern, text):
                    ip_set.add(base_ip)
        else:
            # 纯文本或 JSON：直接提取所有 IPv4（含 CIDR）
            for base_ip in re.findall(ip_cidr_pattern, resp.text):
                ip_set.add(base_ip)

    except Exception as e:
        print(f"❌ 请求失败：{url} - {e}")

print(f"\n共提取到 {len(ip_set)} 个唯一 IP，开始查询地理信息...\n")

# 打印 Cloudflare CSV 的统计信息（如果有）
if cf_counts:
    print("从 Cloudflare CSV 按国家统计到的 IP 数量：")
    for tc in sorted(cf_counts.keys()):
        print(f"  {tc.upper()}: {len(cf_counts[tc])} 个 IP")

# ---------- IP 查询函数 ----------
def get_ip_info(ip):
    try:
        r = session.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
        data = r.json()
        if data.get("status") == "success":
            country = data.get("country", "")
            region = data.get("regionName", "")
            isp = data.get("isp", "未知ISP")
            location = f"{country} {region}".strip()
            return f"{location}#{isp}"
        else:
            return "未知地区#未知ISP"
    except Exception:
        return "查询失败#未知ISP"

# ---------- 查询并组合结果 ----------
results = {}
for ip in sorted(ip_set):
    if ip in cache:
        info = cache[ip]
    else:
        info = get_ip_info(ip)
        time.sleep(0.5)
    results[ip] = info

# ---------- 分组并写入文件 ----------
grouped = defaultdict(list)
for ip, info in results.items():
    if "#" in info:
        region, isp = info.split("#", 1)
    else:
        region, isp = info, "未知ISP"
    grouped[region].append((ip, isp))

out_tag = "_".join(sorted(set(c.upper() for c in target_countries)))
output_file = f"ip_{out_tag}.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        for idx, (ip, isp) in enumerate(sorted(grouped[region]), 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"✅ 共保存 {len(results)} 个唯一 IP，已写入 {output_file}。")
