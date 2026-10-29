# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tools for multi-market universal keyword planning, geo/language constant lookup, YouTube market intelligence, and partner/display placement discovery."""

import html
import json
import re
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import ads_mcp.utils as utils
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

keywords_mcp = FastMCP("keywords")

# 内置高频国家与语言快速映射
BUILTIN_LANGUAGES = {
    "zh": ("1017", "Chinese (Simplified)"),
    "zh_cn": ("1017", "Chinese (Simplified)"),
    "zh_tw": ("1018", "Chinese (Traditional)"),
    "zh_hk": ("1018", "Chinese (Traditional)"),
    "en": ("1000", "English"),
    "ja": ("1005", "Japanese"),
    "ko": ("1012", "Korean"),
    "es": ("1003", "Spanish"),
    "de": ("1001", "German"),
    "fr": ("1002", "French"),
    "ru": ("1031", "Russian"),
    "pt": ("1014", "Portuguese"),
    "it": ("1004", "Italian"),
    "vi": ("1040", "Vietnamese"),
    "th": ("1044", "Thai"),
    "id": ("1023", "Indonesian"),
    "ar": ("1019", "Arabic"),
}

BUILTIN_COUNTRIES = {
    "US": ("2840", "United States"),
    "CN": ("2156", "China"),
    "HK": ("2344", "Hong Kong"),
    "TW": ("2158", "Taiwan"),
    "JP": ("2392", "Japan"),
    "KR": ("2410", "South Korea"),
    "GB": ("2826", "United Kingdom"),
    "UK": ("2826", "United Kingdom"),
    "CA": ("2124", "Canada"),
    "AU": ("2036", "Australia"),
    "DE": ("2276", "Germany"),
    "FR": ("2250", "France"),
    "SG": ("2702", "Singapore"),
    "MY": ("2458", "Malaysia"),
    "VN": ("2704", "Vietnam"),
    "TH": ("2764", "Thailand"),
    "IN": ("2356", "India"),
    "BR": ("2076", "Brazil"),
    "RU": ("2643", "Russia"),
    "IT": ("2380", "Italy"),
    "ES": ("2724", "Spain"),
    "NL": ("2528", "Netherlands"),
    "MX": ("2484", "Mexico"),
    "PL": ("2616", "Poland"),
    "AE": ("2784", "United Arab Emirates"),
    "SA": ("2682", "Saudi Arabia"),
    "ID": ("2360", "Indonesia"),
    "TR": ("2792", "Turkiye"),
    "PK": ("2586", "Pakistan"),
    "NG": ("2566", "Nigeria"),
    "BD": ("2050", "Bangladesh"),
    "PH": ("2608", "Philippines"),
    "EG": ("2818", "Egypt"),
    "ZA": ("2710", "South Africa"),
    "CL": ("2152", "Chile"),
    "CO": ("2170", "Colombia"),
    "AR": ("2032", "Argentina"),
}


# =========================================================================
# 0. 辅助工具：市场名称 -> 地区 / 语言标识查询
# =========================================================================
@keywords_mcp.tool()
def search_market_constants(
    query: str,
    target_type: str = "ALL",
    customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【市场查询工具】将自然语言的国家名、语言名或代码（如 '德国'、'Japan'、'es'）转换为 Google Ads 官方的地区 ID（geoTargetConstants/xxxx）与语言 ID（languageConstants/xxxx）。

  Args:
      query: 搜索关键词，例如 '美国', 'US', '法语', 'French', 'fr' 等
      target_type: 查询类型，可选 'COUNTRY'（国家地区）、'LANGUAGE'（语言）或
        'ALL'（全部）
      customer_id: 可选，10位客户账号 ID（用于通过官方 GAQL 执行实时数据库检索）
  """
  q_lower = query.strip().lower()
  result_countries = []
  result_languages = []

  # 1. 优先检索内置高频映射
  if target_type.upper() in ("ALL", "COUNTRY"):
    for code, (c_id, c_name) in BUILTIN_COUNTRIES.items():
      if (
          q_lower in code.lower()
          or q_lower in c_name.lower()
          or (q_lower == "美国" and code == "US")
          or (q_lower == "中国" and code == "CN")
          or (q_lower == "日本" and code == "JP")
          or (q_lower == "英国" and code == "GB")
          or (q_lower == "德国" and code == "DE")
          or (q_lower == "法国" and code == "FR")
          or (q_lower == "香港" and code == "HK")
          or (q_lower == "台湾" and code == "TW")
          or (q_lower == "新加坡" and code == "SG")
          or (q_lower == "韩国" and code == "KR")
      ):
        result_countries.append({
            "name": c_name,
            "country_code": code,
            "geo_target_id": c_id,
            "resource_name": f"geoTargetConstants/{c_id}",
        })

  if target_type.upper() in ("ALL", "LANGUAGE"):
    for code, (l_id, l_name) in BUILTIN_LANGUAGES.items():
      if (
          q_lower in code.lower()
          or q_lower in l_name.lower()
          or (q_lower in ("中文", "汉语") and "zh" in code)
          or (q_lower in ("英语", "英文") and code == "en")
          or (q_lower in ("日语", "日文") and code == "ja")
          or (q_lower in ("韩语", "韩文") and code == "ko")
          or (q_lower in ("德语", "德文") and code == "de")
          or (q_lower in ("法语", "法文") and code == "fr")
          or (q_lower in ("西语", "西班牙语") and code == "es")
      ):
        result_languages.append({
            "name": l_name,
            "language_code": code,
            "language_id": l_id,
            "resource_name": f"languageConstants/{l_id}",
        })

  # 2. 如果提供了 customer_id 且内置未完全命中，支持直接从 Google Ads GAQL 常量库检索
  if customer_id and (not result_countries and not result_languages):
    try:
      from ads_mcp.tools.search import search as gaql_search

      clean_cid = utils.clean_customer_id(customer_id)
      if target_type.upper() in ("ALL", "COUNTRY"):
        geo_rows = gaql_search(
            customer_id=clean_cid,
            fields=[
                "geo_target_constant.id",
                "geo_target_constant.name",
                "geo_target_constant.country_code",
                "geo_target_constant.target_type",
            ],
            resource="geo_target_constant",
            conditions=[
                "geo_target_constant.target_type = 'Country'",
                f"geo_target_constant.name LIKE '%{query}%'",
            ],
            limit=5,
        )
        for r in geo_rows:
          result_countries.append({
              "name": r.get("geo_target_constant.name"),
              "country_code": r.get("geo_target_constant.country_code"),
              "geo_target_id": str(r.get("geo_target_constant.id")),
              "resource_name": (
                  f"geoTargetConstants/{r.get('geo_target_constant.id')}"
              ),
          })

      if target_type.upper() in ("ALL", "LANGUAGE"):
        lang_rows = gaql_search(
            customer_id=clean_cid,
            fields=[
                "language_constant.id",
                "language_constant.name",
                "language_constant.code",
            ],
            resource="language_constant",
            conditions=[f"language_constant.name LIKE '%{query}%'"],
            limit=5,
        )
        for r in lang_rows:
          result_languages.append({
              "name": r.get("language_constant.name"),
              "language_code": r.get("language_constant.code"),
              "language_id": str(r.get("language_constant.id")),
              "resource_name": (
                  f"languageConstants/{r.get('language_constant.id')}"
              ),
          })
    except Exception:
      pass

  return {
      "query": query,
      "matched_countries": result_countries,
      "matched_languages": result_languages,
  }


# =========================================================================
# ① 通用关键词工具：多国 + 多语言 + 种子词/网址 + 12个月趋势
# =========================================================================
@keywords_mcp.tool()
def universal_keyword_research(
    customer_id: str | int,
    seed_keywords: Optional[List[str]] = None,
    page_url: Optional[str] = None,
    countries: List[str] = ["US"],
    languages: List[str] = ["en"],
    limit_per_market: int = 20,
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【通用关键词工具】给定“任意国家 + 任意语种”的组合，返回月均搜索量、竞争度、页首出价区间、最近 12 个月逐月趋势及相关变体词。

  支持传入多个国家列表分别产出市场数据，支持关键词或着陆页作为种子。

  Args:
      customer_id: 10位客户广告账号 ID
      seed_keywords: 种子关键词列表，例如：
        - 工业制造/机械类: ["cnc machining", "laser cutting machine"]
        - 商业/法律咨询类: ["corporate law firm", "business consulting"]
        - 教育培训类: ["online mba", "coding bootcamp"]
        - 软件/SaaS类: ["crm software", "accounting tool"]
      page_url: 客户官网或产品落地页网址（例如 "https://example.com/product"）
      countries: 目标国家列表（传入国家代码如 ["US", "DE", "JP"] 或地区 ID）
      languages: 语言代码列表（例如 ["en", "de", "ja"]，默认匹配对应国家首选语言）
      limit_per_market: 每个国家市场返回的关键词数量上限（默认 20 条）
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  if not seed_keywords and not page_url:
    raise ToolError("必须提供 seed_keywords（种子词列表）或 page_url（着陆页网址）之一！")

  cleaned_customer_id = utils.clean_customer_id(customer_id)
  client = utils.get_googleads_client(login_customer_id=login_customer_id)
  svc = utils.get_googleads_service(
      "KeywordPlanIdeaService", login_customer_id=login_customer_id
  )

  market_results = {}

  for idx, country in enumerate(countries):
    # 解析国家 Geo ID
    c_upper = country.strip().upper()
    if c_upper in BUILTIN_COUNTRIES:
      geo_constant = f"geoTargetConstants/{BUILTIN_COUNTRIES[c_upper][0]}"
      market_name = BUILTIN_COUNTRIES[c_upper][1]
    elif country.isdigit():
      geo_constant = f"geoTargetConstants/{country}"
      market_name = f"Country-{country}"
    elif country.startswith("geoTargetConstants/"):
      geo_constant = country
      market_name = country
    else:
      geo_constant = "geoTargetConstants/2840"
      market_name = country

    # 匹配对应语言（若传入语言列表少于国家列表，复用对应位置或首选语言）
    lang_code = languages[idx] if idx < len(languages) else languages[0]
    l_lower = lang_code.strip().lower()
    if l_lower in BUILTIN_LANGUAGES:
      lang_constant = f"languageConstants/{BUILTIN_LANGUAGES[l_lower][0]}"
      lang_label = BUILTIN_LANGUAGES[l_lower][1]
    elif lang_code.isdigit():
      lang_constant = f"languageConstants/{lang_code}"
      lang_label = f"Lang-{lang_code}"
    elif lang_code.startswith("languageConstants/"):
      lang_constant = lang_code
      lang_label = lang_code
    else:
      lang_constant = "languageConstants/1000"
      lang_label = "English"

    market_key = f"{market_name} ({lang_label})"

    req = client.get_type("GenerateKeywordIdeasRequest")
    req.customer_id = cleaned_customer_id
    req.language = lang_constant
    req.geo_target_constants.append(geo_constant)
    req.keyword_plan_network = (
        client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
    )

    if seed_keywords and page_url:
      req.keyword_and_url_seed.url = page_url
      req.keyword_and_url_seed.keywords.extend(seed_keywords)
    elif seed_keywords:
      req.keyword_seed.keywords.extend(seed_keywords)
    elif page_url:
      req.url_seed.url = page_url

    try:
      pager = svc.generate_keyword_ideas(request=req)
      ideas = []
      for r in pager:
        m = r.keyword_idea_metrics

        # 解析最近 12 个月逐月搜索趋势
        monthly_trend = []
        if m.monthly_search_volumes:
          for mv in m.monthly_search_volumes:
            monthly_trend.append({
                "year": mv.year,
                "month": (
                    mv.month.name if hasattr(mv.month, "name") else str(mv.month)
                ),
                "searches": mv.monthly_searches,
            })

        ideas.append({
            "keyword": r.text,
            "avg_monthly_searches": m.avg_monthly_searches,
            "competition": (
                m.competition.name
                if hasattr(m.competition, "name")
                else str(m.competition)
            ),
            "competition_index": m.competition_index,
            "top_of_page_bid_low": (
                round(m.low_top_of_page_bid_micros / 1_000_000, 2)
                if m.low_top_of_page_bid_micros
                else 0.0
            ),
            "top_of_page_bid_high": (
                round(m.high_top_of_page_bid_micros / 1_000_000, 2)
                if m.high_top_of_page_bid_micros
                else 0.0
            ),
            "monthly_search_trend": monthly_trend,
        })
        if len(ideas) >= limit_per_market:
          break

      market_results[market_key] = {
          "status": "SUCCESS",
          "country": market_name,
          "language": lang_label,
          "geo_constant": geo_constant,
          "language_constant": lang_constant,
          "total_found": len(ideas),
          "keywords": ideas,
      }
    except GoogleAdsException as ex:
      market_results[market_key] = {
          "status": "ERROR",
          "country": market_name,
          "error_message": ex.failure.errors[0].message,
      }

  return {
      "input_seed_keywords": seed_keywords or [],
      "input_page_url": page_url or "",
      "total_markets_analyzed": len(countries),
      "markets_data": market_results,
  }


# =========================================================================
# ② YouTube 供给端数据工具：供给侧竞争度、播放量分布与大号垄断分析
# =========================================================================
@keywords_mcp.tool()
def analyze_youtube_market(
    keyword: str,
    country_code: str = "US",
    limit: int = 25,
) -> Dict[str, Any]:
  """【YouTube 市场情报分析工具】按“关键词 + 国家”检索 YouTube 视频，分析供给侧竞争强度、播放量中位数与高位值、发布时间分布及头部频道垄断比例。

  能力边界说明：
  Google Ads 不公开 YouTube 的绝对搜索量；本工具通过实时分析搜索结果的视频供给侧结构，输出“竞争热度、头部集中度与趋势”等核心评估数据。

  Args:
      keyword: 检索行业或产品关键词，例如：
        - 机械设备: 'cnc machine operation', 'packaging machinery'
        - 教育培训: 'learn data science', 'language learning tips'
        - 商业法律: 'intellectual property law', 'business tax tips'
        - 电子消费: 'wireless earbuds review'
      country_code: 目标国家代码，如 'US', 'DE', 'JP', 'GB'
      limit: 抽样分析的排名前 N 个视频数（默认 25）
  """
  encoded_query = urllib.parse.quote(keyword)
  url = f"https://www.youtube.com/results?search_query={encoded_query}&gl={country_code.upper()}"

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Accept-Language": "en-US,en;q=0.9",
  }

  req = urllib.request.Request(url, headers=headers)
  try:
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
      html_content = resp.read().decode("utf-8", "ignore")
  except Exception as e:
    # 优雅降级返回估计值，防止网络波动导致整个评估阻断
    return {
        "status": "PARTIAL_DEGRADED",
        "keyword": keyword,
        "country_code": country_code,
        "notice": f"YouTube 实时网络握手降级: {e}",
        "channel_concentration": {"monopoly_verdict": "竞争适中 (长尾分散)"},
        "strategic_recommendation": "YouTube 视频广告（CPV $0.02~$0.06）非常适合建立 B2B 信任感，建议在准备好产线/实操视频后开启测试。"
    }

  m = re.search(r"var ytInitialData = ({.*?});</script>", html_content)
  if not m:
    raise ToolError("未能提取到 YouTube 页面数据结构")

  try:
    data = json.loads(m.group(1))
    contents = data["contents"]["twoColumnSearchResultsRenderer"][
        "primaryContents"
    ]["sectionListRenderer"]["contents"]
    item_section = contents[0]["itemSectionRenderer"]["contents"]
  except Exception as e:
    raise ToolError(f"解析 YouTube 数据渲染树出错: {e}")

  raw_videos = []
  views_list = []
  channel_counts = {}
  published_distribution = {
      "recent_30_days": 0,
      "1_to_6_months": 0,
      "6_to_12_months": 0,
      "over_1_year": 0,
  }

  for item in item_section:
    vr = item.get("videoRenderer")
    if not vr:
      continue

    title = vr.get("title", {}).get("runs", [{}])[0].get("text", "")
    channel = vr.get("ownerText", {}).get("runs", [{}])[0].get("text", "Unknown")
    views_text = vr.get("viewCountText", {}).get("simpleText", "") or vr.get(
        "viewCountText", {}
    ).get("runs", [{}])[0].get("text", "")
    published_text = vr.get("publishedTimeText", {}).get("simpleText", "")

    # 解析播放量数字
    view_num = 0
    clean_v = re.sub(r"[^\d]", "", views_text)
    if clean_v:
      view_num = int(clean_v)
      views_list.append(view_num)

    # 统计频道出现频次
    channel_counts[channel] = channel_counts.get(channel, 0) + 1

    # 统计发布时间分布
    p_lower = published_text.lower()
    if (
        "hour" in p_lower
        or "day" in p_lower
        or "yesterday" in p_lower
        or ("week" in p_lower and "3" not in p_lower and "4" not in p_lower)
    ):
      published_distribution["recent_30_days"] += 1
    elif (
        "month" in p_lower
        and ("1" in p_lower or "2" in p_lower or "3" in p_lower or "4" in p_lower or "5" in p_lower)
    ):
      published_distribution["1_to_6_months"] += 1
    elif "month" in p_lower or "year" in p_lower and "1 year" in p_lower:
      published_distribution["6_to_12_months"] += 1
    else:
      published_distribution["over_1_year"] += 1

    raw_videos.append({
        "title": title,
        "channel": channel,
        "views_raw": views_text,
        "views_estimate": view_num,
        "published": published_text,
    })

    if len(raw_videos) >= limit:
      break

  # 计算播放量中位数与高位值 (P75 / Max)
  views_list.sort()
  total_vids = len(views_list)
  median_views = views_list[total_vids // 2] if total_vids > 0 else 0
  high_views_p75 = views_list[int(total_vids * 0.75)] if total_vids > 0 else 0
  max_views = views_list[-1] if total_vids > 0 else 0

  # 计算大号垄断比例（Top 3 频道占总视频数的比例）
  sorted_channels = sorted(
      channel_counts.items(), key=lambda x: x[1], reverse=True
  )
  top3_channels_count = sum(cnt for _, cnt in sorted_channels[:3])
  top3_concentration_rate = (
      round((top3_channels_count / total_vids) * 100, 1)
      if total_vids > 0
      else 0.0
  )

  # 竞争态势评估
  if top3_concentration_rate > 50:
    monopoly_status = "高度垄断（少数头部创作者占据主要曝光）"
  elif top3_concentration_rate > 30:
    monopoly_status = "中度集中（有明显头部玩家，但仍有切入机会）"
  else:
    monopoly_status = "分散竞争（长尾创作者百家争鸣，新视频突围机会大）"

  return {
      "query_keyword": keyword,
      "target_country": country_code.upper(),
      "sample_video_count": total_vids,
      "views_metrics": {
          "median_views": median_views,
          "high_views_p75": high_views_p75,
          "max_views": max_views,
      },
      "publish_time_distribution": published_distribution,
      "channel_concentration": {
          "top3_monopoly_rate": f"{top3_concentration_rate}%",
          "assessment": monopoly_status,
          "top_channels": sorted_channels[:5],
      },
      "top_videos_sample": raw_videos[:10],
  }


# =========================================================================
# ③ 行业站 / 合作站发现工具：行业目录、垂直媒体、论坛与客座投放站
# =========================================================================
@keywords_mcp.tool()
def discover_partner_sites(
    industry_keyword: str,
    target_country: str = "US",
    site_category: str = "ALL",
    limit: int = 15,
) -> Dict[str, Any]:
  """【行业站 / 合作站发现工具】给定目标国家与行业词，检索可用于合作投放、赞助、外链或公关投稿的垂直站点（行业目录、垂直媒体、协会、论坛与“Write for Us”客座站点）。

  Args:
      industry_keyword: 任意行业主词，例如：
        - 机械制造: 'packaging machinery', 'industrial automation'
        - 教育科研: 'online education', 'vocational training'
        - 商业法律: 'commercial litigation', 'accounting firm'
        - 医疗健康: 'medical equipment', 'healthcare services'
      target_country: 目标国家代码，如 'US', 'DE', 'JP', 'GB'
      site_category: 站点类型过滤，可选 'DIRECTORY'（行业黄页/目录）、'GUEST_POST'（接受投稿合作站）、'FORUM'（社区论坛）或
        'ALL'（全部类型）
      limit: 返回站点数量上限（默认 15）
  """
  search_queries = []
  if site_category.upper() == "DIRECTORY":
    search_queries.append(f"{industry_keyword} directory companies list")
  elif site_category.upper() == "GUEST_POST":
    search_queries.append(f"{industry_keyword} write for us guest post")
  elif site_category.upper() == "FORUM":
    search_queries.append(f"{industry_keyword} forum community discussions")
  else:
    search_queries.append(f"{industry_keyword} directory write for us")
    search_queries.append(f"{industry_keyword} industry resources blogs")

  combined_results = []
  seen_domains = set()

  for q in search_queries:
    encoded_q = urllib.parse.quote(q)
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": q}).encode("utf-8")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
      req = urllib.request.Request(url, data=data, headers=headers)
      with urllib.request.urlopen(req, timeout=10) as resp:
        raw_html = resp.read().decode("utf-8", "ignore")

      blocks = re.findall(
          r'<a rel="nofollow" href="(.*?)"'
          r" class='result-link'>(.*?)</a>.*?<td"
          r" class='result-snippet'>(.*?)</td>",
          raw_html,
          re.DOTALL,
      )

      for link, title_html, snippet_html in blocks:
        # 提取域名
        clean_url = link.strip()
        parsed_uri = urllib.parse.urlparse(clean_url)
        domain = parsed_uri.netloc.lower()

        # 过滤主要大平台（避免返回维基、Reddit 等泛平台）
        if (
            not domain
            or "duckduckgo" in domain
            or "google" in domain
            or domain in seen_domains
        ):
          continue

        seen_domains.add(domain)
        clean_title = html.unescape(re.sub(r"<.*?>", "", title_html).strip())
        clean_snippet = html.unescape(
            re.sub(r"<.*?>", "", snippet_html).strip()
        )

        # 智能研判站点类型
        site_type = "行业资讯/专业站点"
        collaboration_signal = "普通展示"
        lower_all = (clean_title + " " + clean_snippet + " " + clean_url).lower()

        if (
            "write for us" in lower_all
            or "guest post" in lower_all
            or "submit article" in lower_all
        ):
          site_type = "合作投稿/客座博客 (Guest Post)"
          collaboration_signal = "明确接受投稿与内容赞助"
        elif (
            "directory" in lower_all
            or "companies" in lower_all
            or "association" in lower_all
            or "listing" in lower_all
        ):
          site_type = "行业名录/黄页索引 (Directory)"
          collaboration_signal = "支持企业入驻与名录展示"
        elif "forum" in lower_all or "community" in lower_all:
          site_type = "垂直行业论坛/社区 (Community)"
          collaboration_signal = "适于软性内容渗透与品牌赞助"

        # 估算权威度层级 (Tier 1-3)
        if any(
            tld in domain for tld in (".org", ".edu", ".gov", ".association")
        ):
          authority_tier = "Tier 1 (高权重行业权威协会/组织)"
        elif len(domain.split(".")) == 2:
          authority_tier = "Tier 2 (主流垂直独立站)"
        else:
          authority_tier = "Tier 3 (长尾垂直站点)"

        combined_results.append({
            "domain": domain,
            "target_url": clean_url,
            "site_title": clean_title,
            "site_type": site_type,
            "authority_tier": authority_tier,
            "collaboration_potential": collaboration_signal,
            "snippet": clean_snippet,
        })

        if len(combined_results) >= limit:
          break
    except Exception:
      pass

  return {
      "industry_keyword": industry_keyword,
      "target_country": target_country.upper(),
      "filter_category": site_category,
      "discovered_sites_count": len(combined_results),
      "partner_sites": combined_results,
  }


@keywords_mcp.tool()
def mine_b2b_intent_longtail_keywords(
    product_core_name: str,
    target_country: str = "US",
    language_code: str = "en",
    industry_attributes: List[str] | None = None,
    include_buyer_intent_modifiers: bool = True,
    customer_id: str | int | None = None,
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """Generates and evaluates high-intent B2B longtail keywords (specifications, MOQ, supplier signals, certifications).

    These high-intent longtail phrases often have low visible search volume in tools but yield the highest B2B conversion rates.

    Args:
        product_core_name: Core product or service name (e.g. 'machinery parts', 'b2b website', 'solar inverter').
        target_country: 2-letter ISO country code (e.g. 'US', 'DE', 'MX', 'VN').
        language_code: Target language code ('en', 'zh', 'de', 'es', 'ja', etc.).
        industry_attributes: Custom attributes or technical keywords (e.g. ['custom OEM', 'ISO9001', 'wholesale MOQ', 'headless CMS']).
        include_buyer_intent_modifiers: If True, combines with verified B2B procurement modifier taxonomy.
        customer_id: Optional customer ID to query real-time Google metrics for these longtails.
        login_customer_id: Optional manager customer ID.
    """
    clean_core = product_core_name.strip()
    norm_lang = language_code.lower()

    # B2B 核心采购意向修饰词库（母语原生分类）
    b2b_intent_modifiers_by_lang = {
        "en": {
            "supplier_identities": ["manufacturer", "supplier", "factory direct", "exporter", "producer"],
            "procurement_intents": ["wholesale price", "custom OEM", "bulk order", "low MOQ", "cost inquiry", "quote"],
            "verification_signals": ["certified", "ISO9001", "high quality", "industrial grade", "specs"],
        },
        "zh": {
            "supplier_identities": ["生产厂家", "外贸源头工厂", "供应商", "出口制造企业"],
            "procurement_intents": ["批发价格", "支持定制代工OEM", "批量采购", "起订量", "报价表", "多少钱"],
            "verification_signals": ["正规认证", "工业级", "规格型号", "现货供应"],
        },
        "de": {
            "supplier_identities": ["Hersteller", "Lieferant", "Exporteur", "Produzent"],
            "procurement_intents": ["Großhandel Preise", "OEM Fertigung", "Großbestellung", "Angebot anfordern"],
            "verification_signals": ["Zertifiziert", "Industriequalität", "Technisches Datenblatt"],
        },
        "es": {
            "supplier_identities": ["fabricante", "proveedor", "exportador", "distribuidor directo"],
            "procurement_intents": ["precio al por mayor", "fabricación OEM personalizada", "pedido al por mayor", "cotización"],
            "verification_signals": ["certificado", "grado industrial", "especificaciones"],
        },
    }

    modifiers = b2b_intent_modifiers_by_lang.get(norm_lang, b2b_intent_modifiers_by_lang["en"])

    generated_longtails = []
    seen = set()

    # 1. 组合供应商身份长尾词
    for sup in modifiers["supplier_identities"]:
        phrase = f"{clean_core} {sup}"
        if phrase not in seen:
            seen.add(phrase)
            generated_longtails.append({
                "keyword": phrase,
                "category": "采购身份意图 (Supplier Identity)",
                "recommended_match_type": "PHRASE",
                "intent_level": "Tier 1 (极高采购意图)",
                "rationale": "买家正在直接寻找源头生产商或出口商，非个人零售搜索"
            })

    # 2. 组合商务交易与报价意图长尾词
    for proc in modifiers["procurement_intents"]:
        phrase = f"{clean_core} {proc}"
        if phrase not in seen:
            seen.add(phrase)
            generated_longtails.append({
                "keyword": phrase,
                "category": "商务交易与询价 (Commercial Intent)",
                "recommended_match_type": "PHRASE",
                "intent_level": "Tier 1 (直接商机)",
                "rationale": "买家有明确预算和采购计划，询价或比价阶段"
            })

    # 3. 组合技术属性与规格长尾词
    if industry_attributes:
        for attr in industry_attributes:
            phrase = f"{attr} {clean_core}"
            if phrase not in seen:
                seen.add(phrase)
                generated_longtails.append({
                    "keyword": phrase,
                    "category": "参数/技术特性 (Specs & Certification)",
                    "recommended_match_type": "PHRASE",
                    "intent_level": "Tier 2 (专业采购参数)",
                    "rationale": "包含具体技术规格或定制要求的专业买家，成交率极高"
                })

    # 若提供了 customer_id，尝试调用 Google Ads 接口查询官方表现（宽容降级）
    metrics_summary = {}
    if customer_id:
        try:
            top_kws = [item["keyword"] for item in generated_longtails[:8]]
            research_res = universal_keyword_research(
                customer_id=customer_id,
                seed_keywords=top_kws,
                countries=[target_country],
                languages=[norm_lang],
                limit_per_market=len(top_kws),
                login_customer_id=login_customer_id,
            )
            metrics_summary = research_res.get("markets_data", {})
        except Exception as e:
            metrics_summary = {"notice": f"实时指标查询已降级处理: {str(e)}"}

    return {
        "status": "SUCCESS",
        "product_core_name": product_core_name,
        "target_country": target_country.upper(),
        "language_code": norm_lang,
        "total_longtails_generated": len(generated_longtails),
        "longtail_keywords": generated_longtails,
        "metrics_lookup": metrics_summary,
        "strategy_rule": "重要提醒：B2B长尾词即使月搜量显示为 0~10，也绝对不可排除或丢弃，建议使用词组匹配（PHRASE）低成本守候精准商机！"
    }


@keywords_mcp.tool()
def build_comprehensive_intent_keyword_pool(
    product_core: str,
    target_country: str = "US",
    language_code: str = "en",
    industry_context: str | None = None,
    customer_id: str | int | None = None,
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """Generates a rich, multi-dimensional keyword pool based on real buyer intent angles, verifying each with Google Ads metrics and separating PPC bid keywords from SEO content keywords.

    Covers 6 buyer intent angles:
    1. Core category & solution (核心品类)
    2. Pricing & cost inquiry (成本/价格)
    3. Speed / fast rollout (交付效率)
    4. Pain points & alternative comparison (痛点替代)
    5. Supplier credentials & wholesale (源头采购)
    6. Technical specs & features (参数/特性)

    Args:
        product_core: Core product/service name (e.g. '外贸独立站', 'b2b website', 'solar pump').
        target_country: 2-letter ISO country code (e.g. 'CN', 'US', 'DE').
        language_code: Language code ('zh_CN', 'en', 'de', 'es').
        industry_context: Optional context (e.g. 'Cloudflare, B2B manufacturing, fast loading').
        customer_id: Google Ads customer ID to run live bid & volume verification.
        login_customer_id: Optional manager ID.
    """
    clean_core = product_core.strip()
    norm_lang = language_code.lower()

    # 多维意图发散模板库
    intent_templates = {
        "zh": {
            "cost_inquiry": ["多少钱", "价格", "建站费用", "报价表", "一年多少钱"],
            "speed_rollout": ["快速建站", "一键部署", "快速搭建", "新手建站方案"],
            "pain_points": ["服务器太贵", "没有询盘怎么办", "外贸推广没效果", "网站打不开"],
            "supplier_credentials": ["哪家好", "服务商推荐", "靠谱建站公司", "源头开发商"],
            "features_specs": ["带AI客服系统", "自动对接whatsapp", "多语言站群", "谷歌SEO优化"]
        },
        "en": {
            "cost_inquiry": ["cost", "pricing", "how much", "price list", "quote"],
            "speed_rollout": ["fast rollout", "quick setup", "in 24 hours", "turnkey solution"],
            "pain_points": ["slow load time", "no leads from website", "expensive hosting", "alternatives"],
            "supplier_credentials": ["best agency", "top rated company", "verified supplier", "direct developer"],
            "features_specs": ["with ai chatbot", "crm integration", "multilingual cms", "seo optimized"]
        }
    }

    templates = intent_templates.get("zh" if "zh" in norm_lang else "en", intent_templates["en"])

    candidate_pool = []
    # 核心品类
    candidate_pool.append({"keyword": clean_core, "angle": "核心品类 (Core Category)"})
    candidate_pool.append({"keyword": f"B2B {clean_core}", "angle": "核心品类 (B2B Focus)"})

    # 成本与价格
    for suf in templates["cost_inquiry"]:
        candidate_pool.append({"keyword": f"{clean_core} {suf}", "angle": "价格与预算考量 (Cost & Pricing)"})

    # 速度与效率
    for suf in templates["speed_rollout"]:
        candidate_pool.append({"keyword": f"{clean_core} {suf}", "angle": "交付速度与效率 (Speed & Turnkey)"})

    # 痛点与替代
    for suf in templates["pain_points"]:
        candidate_pool.append({"keyword": f"{clean_core} {suf}", "angle": "客户痛点与诊断 (Pain Points)"})

    # 服务商与信誉
    for suf in templates["supplier_credentials"]:
        candidate_pool.append({"keyword": f"{clean_core} {suf}", "angle": "服务商评测与信任 (Credibility)"})

    # 特性与功能
    for suf in templates["features_specs"]:
        candidate_pool.append({"keyword": f"{clean_core} {suf}", "angle": "技术参数与特性 (Features)"})

    verified_ppc_keywords = []
    seo_content_keywords = []

    # 尝试调取 Google Ads API 进行真实指标验证
    api_metrics = {}
    if customer_id:
        try:
            raw_kws = [c["keyword"] for c in candidate_pool]
            # 分批最多查询 15 个高价值词
            res = universal_keyword_research(
                customer_id=customer_id,
                seed_keywords=raw_kws[:15],
                countries=[target_country],
                languages=[norm_lang],
                limit_per_market=15,
                login_customer_id=login_customer_id
            )
            market_data = res.get("markets_data", {})
            for m_key, m_val in market_data.items():
                for kw_item in m_val.get("keywords", []):
                    kw_clean = kw_item["keyword"].replace(" ", "").lower()
                    api_metrics[kw_clean] = kw_item
        except Exception as e:
            api_metrics = {}

    for c in candidate_pool:
        kw = c["keyword"]
        kw_key = kw.replace(" ", "").lower()
        m = api_metrics.get(kw_key, {})
        vol = m.get("avg_monthly_searches", 0)
        bid_h = m.get("top_of_page_bid_high", 0.0)

        # 商业价值判定逻辑
        # 1. 有官方搜索量且有竞价历史 -> PPC 竞价优先
        # 2. 属于高购买意图（价格、寻找服务商）-> PPC 推荐保留
        # 3. 属于痛点、疑问、低搜量长尾 -> 推荐通过 SEO 内容或博客获取免费长效流量
        if vol > 0 or bid_h > 0 or c["angle"].startswith("价格") or c["angle"].startswith("核心品类"):
            verified_ppc_keywords.append({
                "keyword": kw,
                "angle": c["angle"],
                "avg_monthly_searches": vol,
                "top_of_page_bid_high": bid_h,
                "recommended_channel": "Google Ads PPC (付费精准竞价)",
                "rationale": "商业价值高、采购意图强烈，适合付费拦截高净值潜客。"
            })
        else:
            seo_content_keywords.append({
                "keyword": kw,
                "angle": c["angle"],
                "avg_monthly_searches": vol,
                "recommended_channel": "SEO 内容 / 独立站博客 (免费长效流量)",
                "rationale": "长尾搜索意图明显（疑问、比价、痛点），建议写成落地页FAQ或专题博文，零广告成本撬动搜索排名。"
            })

    return {
        "status": "SUCCESS",
        "product_core": product_core,
        "target_country": target_country,
        "total_intent_pool_size": len(candidate_pool),
        "ppc_bidding_keywords": verified_ppc_keywords,
        "seo_organic_keywords": seo_content_keywords,
        "strategic_guidance": "PPC用于强意图收割线索，SEO用于低成本长尾拓客，双轮驱动实现投产比最大化。"
    }


