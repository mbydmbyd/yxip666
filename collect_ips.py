#!/usr/bin/env python3
# collect_ips.py
import argparse
import requests
from bs4 import BeautifulSoup
import re
import os
import time
from collections import defaultdict
import io
import csv

# ---------- 参数（支持命令行和环境变量） ----------
parser = argparse.ArgumentParser(description="抓取多个来源并从 Cloudflare CSV 筛选指定国家的 IP（支持多国家，逗号分隔）")
parser.add_argument("-c", "--countries", default=os.getenv("TARGET_COUNTRY", "sg"),
                    help="目标国家代码，逗号分隔，例如: SG 或 SG,JP,KR (默认 SG 或环境变量 TARGET_COUNTRY)")
args = parser.parse_args()

target_input = args.countries.strip().lower()
target_countries = [c.strip() for c in target_input.split(",") if c.strip()]
if not target_countries:
    target_countries = ["sg"]

print(f"🌍 当前筛选国家: {', '.join(c.upper() for c in target_countries)}")

# 映射常见显示名（用于在 CSV 行中匹配国家名）
country_map = {
    "sg": "singapore",
    "jp": "japan",
    "kr": "korea",
    "hk": "hong kong",
    "tw": "taiwan",
    "us": "united states",
    "de": "germany",
}

# ---------- 目标 URL 列表 ----------
urls = [
    'https://api.uouin.com/cloudflare.html',
    'https://ip.164746.xyz',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://cf.090227.xyz',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://addressesapi.090227.xyz/ip.164746.xyz',
    'https://api.cloudflare.com/local-ip-ranges.csv',  # Cloudflare 官方 CSV
]

# ---------- 正则与会话 ----------
# 提取 IPv4（支持 CIDR，如 1.1.1.1/24，取基地址 1.1.1.1）
ip_cidr_pattern = r'(\d{1,3}(?:\.\d{1,3}){3})(?:/\d{1,2})?'

session = requests.Session()
session.headers.update({"User-Agent": "cf-ip-collector/1.0"})

# ---------- 读取已有缓存 ip.txt（若存在） ----------
cache = {}
if os.path.exists("ip.txt"):
    with open("ip.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 只分割成三部分，避免 ISP 名中含 '#' 导致多分割
            parts = line.split("#", 2)
            if len(parts) >= 3:
                ip = parts[0].strip()
                location = parts[1].strip()
                isp = parts[2].strip()
                if "-" in location:
                    location = location.split("-")[0]
                cache[ip] = f"{location}#{isp}"
            elif len(parts) == 2:
                ip = parts[0].strip()
                location = parts[1].strip()
                if "-" in location:
                    location = location.split("-")[0]
                cache[ip] = f"{location}#未知ISP"

# ---------- 抓取并汇总 IP ----------
ip_set = set()
cf_counts = defaultdict(set)  # 记录从 Cloudflare CSV 每个国家匹配到的 IP

for url in urls:
    try:
        print(f"正在抓取：{url}")
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        content_type = (resp.headers.get('Content-Type') or "").lower()

        # 专门处理 Cloudflare CSV
        if "cloudflare.com/local-ip-ranges.csv" in url:
            csv_text = resp.text
            # 使用 DictReader 解析，处理可能的 None
            try:
                reader = csv.DictReader(io.StringIO(csv_text))
            except Exception as e:
                print(f"  ⚠️ CSV 解析失败: {e}")
                continue

            for row in reader:
                # 将 row 中的值都转换为字符串（None -> ""），然后 lowercase
                vals = ["" if v is None else str(v) for v in row.values()]
                row_str = " ".join(vals).lower()

                # 判断是否匹配任意目标国家
                matched = []
                for tc in target_countries:
                    nm = country_map.get(tc, "")
                    if tc in row_str or (nm and nm in row_str):
                        matched.append(tc)

                if matched:
                    # 从每个字段中提取 IPv4（包括 CIDR），加入集合并计数
                    for v in vals:
                        for base_ip in re.findall(ip_cidr_pattern, v):
                            ip_set.add(base_ip)
                            for tc in matched:
                                cf_counts[tc].add(base_ip)
            continue  # CSV 处理完成，继续下一个 URL

        # 其他 URL：根据 content-type 处理
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
            # 纯文本或 JSON：直接提取 IPv4
            for base_ip in re.findall(ip_cidr_pattern, resp.text):
                ip_set.add(base_ip)

    except Exception as e:
        print(f"❌ 请求失败：{url} - {e}")

print(f"\n共提取到 {len(ip_set)} 个唯一 IP，开始查询地理信息...\n")

# 显示 Cloudflare CSV 的统计（如果有）
if cf_counts:
    print("从 Cloudflare CSV 按国家统计到的 IP 数量：")
    for tc in sorted(cf_counts.keys()):
        print(f"  {tc.upper()}: {len(cf_counts[tc])} 个 IP")

# ---------- IP 查询函数（ip-api） ----------
def get_ip_info(ip):
    try:
        r = session.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=6)
        r.raise_for_status()
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

# ---------- 查询并合并结果（使用缓存） ----------
results = {}
for ip in sorted(ip_set):
    if ip in cache:
        info = cache[ip]
    else:
        info = get_ip_info(ip)
        time.sleep(0.5)  # 保持适度间隔，避免速率限制
    results[ip] = info

# ---------- 分组并写入文件 ----------
grouped = defaultdict(list)
for ip, info in results.items():
    if "#" in info:
        region, isp = info.split("#", 1)
    else:
        region, isp = info, "未知ISP"
    grouped[region].append((ip, isp))

output_file = f"ip_{'_'.join(c.upper() for c in target_countries)}.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for region in sorted(grouped.keys()):
        for idx, (ip, isp) in enumerate(sorted(grouped[region]), 1):
            f.write(f"{ip}#{region}-{idx}#{isp}\n")
        f.write("\n")

print(f"✅ 共保存 {len(results)} 个唯一 IP，已写入 {output_file}。")
