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

"""Tools for professional Google Ads optimization, dynamic multi-language negative keyword guardrails, search term auditing, and ad copy generation."""

import json
import re
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import ads_mcp.utils as utils
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

pro_optimizer_mcp = FastMCP("optimizer")

# =========================================================================
# 多语言高频原生否定词基准库（Native Multilingual Negative Seed Corpus）
# 针对出海核心 7 大主流语言（英语、中文、西班牙语、德语、法语、日语、葡萄牙语）深度本地化
# =========================================================================
MULTILINGUAL_NEGATIVE_SEEDS = {
    "free_and_cheap": {
        "en": [
            "free",
            "cheap",
            "cheapest",
            "cracked",
            "keygen",
            "pirate",
            "torrent",
            "freeware",
            "nulled",
            "hack",
            "bypass",
        ],
        "zh": [
            "免费",
            "便宜",
            "白嫖",
            "破解",
            "破解版",
            "注册机",
            "绿色版",
            "激活码",
            "盗版",
            "外挂",
        ],
        "es": [
            "gratis",
            "gratuito",
            "barato",
            "economico",
            "crackeado",
            "pirata",
            "keygen",
            "hackear",
            "descargar gratis",
        ],
        "de": [
            "kostenlos",
            "gratis",
            "billig",
            "umsonst",
            "geknackt",
            "raubkopie",
            "keygen",
            "freeware",
            "kostenfrei",
        ],
        "fr": [
            "gratuit",
            "pas cher",
            "bon marche",
            "cracke",
            "pirate",
            "keygen",
            "telecharger gratuit",
            "hack",
        ],
        "ja": [
            "無料",
            "タダ",
            "格安",
            "激安",
            "海賊版",
            "割れ",
            "クラック",
            "アクティベーションコード",
            "チート",
        ],
        "pt": [
            "gratis",
            "gratuito",
            "barato",
            "craqueado",
            "pirata",
            "keygen",
            "baixar gratis",
            "hackear",
        ],
    },
    "jobs_and_careers": {
        "en": [
            "job",
            "jobs",
            "career",
            "careers",
            "hiring",
            "internship",
            "salary",
            "salaries",
            "resume",
            "cv",
            "work from home",
        ],
        "zh": [
            "招聘",
            "求职",
            "找工作",
            "面试",
            "兼职",
            "全职",
            "实习",
            "薪资",
            "工资",
            "简历",
        ],
        "es": [
            "empleo",
            "empleos",
            "trabajo",
            "trabajar",
            "carrera",
            "salario",
            "sueldo",
            "curriculum",
            "cv",
            "pasantia",
        ],
        "de": [
            "job",
            "jobs",
            "karriere",
            "stellenangebote",
            "gehalt",
            "lohn",
            "lebenslauf",
            "praktikum",
            "bewerbung",
        ],
        "fr": [
            "emploi",
            "emplois",
            "recrutement",
            "salaire",
            "stage",
            "cv",
            "carriere",
            "travail a domicile",
        ],
        "ja": [
            "求人",
            "採用",
            "転職",
            "就職",
            "バイト",
            "パート",
            "給料",
            "年収",
            "履歴書",
            "インターン",
        ],
        "pt": [
            "emprego",
            "empregos",
            "trabalho",
            "vagas",
            "salario",
            "curriculo",
            "cv",
            "estagio",
            "carreira",
        ],
    },
    "learning_and_docs": {
        "en": [
            "how to",
            "tutorial",
            "course",
            "training",
            "certification",
            "pdf",
            "ebook",
            "slides",
            "ppt",
            "wiki",
            "wikipedia",
            "meaning",
        ],
        "zh": [
            "教程",
            "指南",
            "培训",
            "课程",
            "课件",
            "考试",
            "认证",
            "维基百科",
            "百科",
            "电子书",
            "是什么意思",
        ],
        "es": [
            "tutorial",
            "como hacer",
            "curso",
            "capacitacion",
            "certificacion",
            "pdf",
            "libro",
            "diapositivas",
            "significado",
        ],
        "de": [
            "anleitung",
            "tutorial",
            "kurs",
            "schulung",
            "zertifizierung",
            "pdf",
            "buch",
            "vorlage",
            "bedeutung",
        ],
        "fr": [
            "tutoriel",
            "comment faire",
            "cours",
            "formation",
            "certification",
            "pdf",
            "livre",
            "signification",
        ],
        "ja": [
            "やり方",
            "チュートリアル",
            "講座",
            "講習",
            "資格",
            "勉強",
            "とは",
            "意味",
            "資料",
            "ウィキペディア",
        ],
        "pt": [
            "tutorial",
            "como fazer",
            "curso",
            "treinamento",
            "certificacao",
            "pdf",
            "livro",
            "significado",
        ],
    },
    "b2b_only_exclusions": {
        "en": [
            "diy",
            "do it yourself",
            "home",
            "personal",
            "family",
            "for kids",
            "student",
            "hobby",
            "consumer",
        ],
        "zh": [
            "家用",
            "自制",
            "手工",
            "个人版",
            "学生版",
            "儿童",
            "家庭版",
            "业余",
        ],
        "es": [
            "casero",
            "hazlo tu mismo",
            "hogar",
            "personal",
            "familia",
            "para ninos",
            "estudiante",
        ],
        "de": [
            "selber machen",
            "zuhause",
            "personlich",
            "familie",
            "fur kinder",
            "student",
            "hobby",
        ],
        "fr": [
            "maison",
            "bricolage",
            "personnel",
            "famille",
            "pour enfants",
            "etudiant",
        ],
        "ja": ["家庭用", "自作", "個人用", "子供用", "学生", "趣味", "DIY"],
        "pt": [
            "caseiro",
            "faca voce mesmo",
            "casa",
            "pessoal",
            "familia",
            "para criancas",
            "estudante",
        ],
    },
    "support_and_login": {
        "en": [
            "login",
            "log in",
            "sign in",
            "signin",
            "customer service",
            "support phone",
            "portal",
            "contact number",
        ],
        "zh": [
            "登录",
            "登陆",
            "登录入口",
            "后台登录",
            "客服电话",
            "售后服务",
            "联系电话",
            "官方热线",
        ],
        "es": [
            "iniciar sesion",
            "entrar",
            "servicio al cliente",
            "telefono soporte",
            "portal",
            "atencion al cliente",
        ],
        "de": [
            "anmelden",
            "einloggen",
            "kundenservice",
            "support telefon",
            "portal",
            "kontaktnummer",
        ],
        "fr": [
            "connexion",
            "se connecter",
            "service client",
            "telephone support",
            "espace client",
        ],
        "ja": [
            "ログイン",
            "サインイン",
            "カスタマーサポート",
            "問い合わせ電話",
            "マイページ",
        ],
        "pt": [
            "login",
            "entrar",
            "servico ao cliente",
            "telefone suporte",
            "portal",
            "atendimento",
        ],
    },
}


def _dynamic_translate_keyword(text: str, target_lang: str) -> Optional[str]:
  """通过公网翻译通道，将自定义业务词动态翻译为目标投放市场的本地语言表达。"""
  clean_text = text.strip()
  if not clean_text:
    return None

  # 规范化目标语言代码
  lang_norm = target_lang.lower().split("-")[0].split("_")[0]

  encoded = urllib.parse.quote(clean_text)
  url = (
      f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_norm}&dt=t&q={encoded}"
  )
  req = urllib.request.Request(
      url,
      headers={
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          )
      },
  )
  try:
    with urllib.request.urlopen(req, timeout=4) as resp:
      data = json.loads(resp.read().decode("utf-8"))
      translated = "".join([part[0] for part in data[0] if part[0]])
      return translated.strip().lower()
  except Exception:
    return None


# =========================================================================
# 1. 动态多语言投放安全护栏（Dynamic Multilingual Guardrail）
# =========================================================================
@pro_optimizer_mcp.tool()
def apply_multilingual_negative_guardrail(
    customer_id: str | int,
    campaign_id: str | int,
    target_languages: List[str] = ["en"],
    library_presets: List[str] = [
        "free_and_cheap",
        "jobs_and_careers",
        "learning_and_docs",
    ],
    custom_negatives: Optional[List[str]] = None,
    auto_translate_custom_negatives: bool = True,
    match_type: str = "PHRASE",
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【动态多语言投放安全护栏】根据目标投放市场的一组或多组语言（如 ['es', 'fr', 'en']），动态组装该语种本土的防烧钱否定词库，并支持将自定义否定词自动翻译扩展为多语种本土表达，彻底防止跨国跨语种跑飞漏网。

  预置词库分类：
  - 'free_and_cheap'：免费/便宜/破解/白嫖类词（必选）
  - 'jobs_and_careers'：求职/招聘/薪资/实习类词
  - 'learning_and_docs'：PDF文档/教程/课程/维基百科类词
  - 'b2b_only_exclusions'：B2B投放专用（排除家用/个人/DIY/儿童）
  - 'support_and_login'：排除老客户误点登录入口/客服电话

  Args:
      customer_id: 10位客户广告账号 ID
      campaign_id: 目标广告系列 ID
      target_languages: 目标语种代码列表，支持如 ['es']（西语）、['de']（德语）、['zh']（中文）、['en']（英语）、['ja']（日语）、['fr']（法语）等
      library_presets: 需要生效的预置否定词库分类列表
      custom_negatives:
        用户自定义需要排除的行业/业务词（如“某竞品品牌”、“某型号”）
      auto_translate_custom_negatives:
        是否将自定义否定词自动翻译并扩充为所有目标语言的本地表达（默认 True）
      match_type: 否定词匹配模式，默认 'PHRASE'（词组匹配，最稳健防漏）或 'EXACT'
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  cleaned_customer_id = utils.clean_customer_id(customer_id)
  cleaned_campaign_id = utils.clean_customer_id(campaign_id)
  norm_match = match_type.strip().upper()

  final_negatives_set = set()
  language_breakdown = {}

  for lang in target_languages:
    l_code = lang.lower().split("-")[0].split("_")[0]
    lang_words = set()

    # 1. 提取内置原生多语言种子词库
    for preset in library_presets:
      if preset in MULTILINGUAL_NEGATIVE_SEEDS:
        cat_dict = MULTILINGUAL_NEGATIVE_SEEDS[preset]
        # 命中对应语种原生词
        if l_code in cat_dict:
          for word in cat_dict[l_code]:
            lang_words.add(word)
            final_negatives_set.add(word)
        # 同时保留英语基础词（国际通用跨语言拦截）
        if "en" in cat_dict:
          for word in cat_dict["en"]:
            lang_words.add(word)
            final_negatives_set.add(word)

    # 2. 如果开启了自定义词动态翻译
    if custom_negatives and auto_translate_custom_negatives:
      for user_w in custom_negatives:
        user_w = user_w.strip()
        if not user_w:
          continue
        final_negatives_set.add(user_w)
        # 若不是原词所属语言，则动态翻译补充本地表达
        trans_w = _dynamic_translate_keyword(user_w, target_lang=l_code)
        if trans_w and trans_w != user_w.lower():
          lang_words.add(trans_w)
          final_negatives_set.add(trans_w)

    language_breakdown[lang] = len(lang_words)

  # 如果有自定义词但关闭了翻译，直接加入
  if custom_negatives and not auto_translate_custom_negatives:
    for user_w in custom_negatives:
      if user_w.strip():
        final_negatives_set.add(user_w.strip())

  if not final_negatives_set:
    raise ToolError("组装后的多语言否定词库为空，请检查输入的语言代码或分类参数！")

  client = utils.get_googleads_client(login_customer_id=login_customer_id)
  campaign_criterion_service = utils.get_googleads_service(
      "CampaignCriterionService", login_customer_id=login_customer_id
  )
  campaign_service = utils.get_googleads_service(
      "CampaignService", login_customer_id=login_customer_id
  )

  operations = []
  for kw_text in final_negatives_set:
    op = client.get_type("CampaignCriterionOperation")
    criterion = op.create
    criterion.campaign = campaign_service.campaign_path(
        cleaned_customer_id, cleaned_campaign_id
    )
    criterion.negative = True
    criterion.keyword.text = kw_text
    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
        norm_match
    ].value
    operations.append(op)

  try:
    response = campaign_criterion_service.mutate_campaign_criteria(
        customer_id=cleaned_customer_id, operations=operations
    )
    return {
        "status": "SUCCESS",
        "campaign_id": cleaned_campaign_id,
        "languages_covered": target_languages,
        "total_unique_negatives_injected": len(response.results),
        "language_word_counts": language_breakdown,
        "match_type": norm_match,
        "sample_words_injected": list(final_negatives_set)[:15],
        "summary": (
            f"成功为广告系列 {cleaned_campaign_id} 动态生成并注入"
            f" {len(response.results)} 个覆盖 {target_languages}"
            " 本地语种的专业否定词，实现跨国全语种防漏！"
        ),
    }
  except GoogleAdsException as ex:
    error_msgs = [
        f"Google Ads API Error: {error.message}" for error in ex.failure.errors
    ]
    raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))


# =========================================================================
# 2. 智能搜索词审计与一键止血（保持现有稳健能力）
# =========================================================================
@pro_optimizer_mcp.tool()
def audit_and_mine_negative_search_terms(
    customer_id: str | int,
    campaign_id: Optional[str | int] = None,
    cost_threshold: float = 10.0,
    max_conversions: float = 0.0,
    auto_apply: bool = False,
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【搜索词智能审计与止血】自动扫描真实用户搜索词，找出“高烧钱、零转化”的垃圾搜索词，并可一键将其转为否定词，杜绝重复扣费。

  Args:
      customer_id: 10位客户广告账号 ID
      campaign_id: 可选，指定审计的广告系列 ID
      cost_threshold: 烧钱阈值（默认消耗超过 10.0 元/美元 且转化 <= max_conversions
        的词判定为垃圾词）
      max_conversions: 最大转化阈值（默认 0，表示完全没有带来转化的词）
      auto_apply: 是否直接自动将识别出的垃圾词加到广告系列的否定词库中（True
        立即添加止血，False 仅列出供人工确认）
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  from ads_mcp.tools.search import search as gaql_search

  cleaned_customer_id = utils.clean_customer_id(customer_id)

  fields = [
      "search_term_view.search_term",
      "search_term_view.status",
      "campaign.id",
      "campaign.name",
      "ad_group.id",
      "ad_group.name",
      "metrics.impressions",
      "metrics.clicks",
      "metrics.cost_micros",
      "metrics.conversions",
  ]

  conditions = []
  if campaign_id:
    conditions.append(f"campaign.id = {utils.clean_customer_id(campaign_id)}")

  rows = gaql_search(
      customer_id=cleaned_customer_id,
      fields=fields,
      resource="search_term_view",
      conditions=conditions,
      orderings=["metrics.cost_micros DESC"],
      limit=100,
      login_customer_id=login_customer_id,
  )

  flagged_wasteful_terms = []
  terms_to_block = []

  for r in rows:
    cost_micros = r.get("metrics.cost_micros", 0)
    actual_cost = round(cost_micros / 1_000_000, 2)
    conversions = r.get("metrics.conversions", 0.0)
    term = r.get("search_term_view.search_term")

    if actual_cost >= cost_threshold and conversions <= max_conversions:
      flagged_wasteful_terms.append({
          "search_term": term,
          "campaign_id": str(r.get("campaign.id")),
          "campaign_name": r.get("campaign.name"),
          "ad_group_id": str(r.get("ad_group.id")),
          "clicks": r.get("metrics.clicks"),
          "wasted_cost": actual_cost,
          "conversions": conversions,
      })
      terms_to_block.append(term)

  total_wasted_money = sum(t["wasted_cost"] for t in flagged_wasteful_terms)

  applied_results = None
  if auto_apply and terms_to_block and campaign_id:
    applied_results = apply_multilingual_negative_guardrail(
        customer_id=cleaned_customer_id,
        campaign_id=campaign_id,
        target_languages=["en"],
        library_presets=[],
        custom_negatives=terms_to_block,
        auto_translate_custom_negatives=False,
        match_type="EXACT",
        login_customer_id=login_customer_id,
    )

  return {
      "status": "SUCCESS",
      "total_searched_terms_analyzed": len(rows),
      "flagged_wasteful_count": len(flagged_wasteful_terms),
      "total_wasted_money_discovered": round(total_wasted_money, 2),
      "flagged_terms": flagged_wasteful_terms,
      "auto_applied_as_negatives": auto_apply,
      "apply_details": applied_results,
  }


# =========================================================================
# 3. 自适应搜索广告（RSA）生成、合规审计与创建工具
# =========================================================================
@pro_optimizer_mcp.tool()
def create_responsive_search_ad(
    customer_id: str | int,
    ad_group_id: str | int,
    final_url: str,
    headlines: List[str],
    descriptions: List[str],
    path1: Optional[str] = None,
    path2: Optional[str] = None,
    status: str = "PAUSED",
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【专业自适应搜索广告创建工具】创建符合 Google Ads 官方高分规范的自适应搜索广告 (Responsive Search Ad)，内置字符数严格校验与违禁绝对词过滤。

  官方规范约束：
  - 标题 (Headlines)：至少 3 个，最多 15 个，每个不得超过 30 个半角字符 (15 个汉字)。
  - 描述 (Descriptions)：至少 2 个，最多 4 个，每个不得超过 90 个半角字符 (45 个汉字)。
  - 路径 (Paths)：可选，每个不得超过 15 个半角字符。

  Args:
      customer_id: 10位客户广告账号 ID
      ad_group_id: 目标广告组 ID
      final_url: 落地页最终网址（如 "https://yourdomain.com/landing"）
      headlines: 广告标题文本列表（建议 5~10 个）
      descriptions: 广告描述文本列表（建议 2~4 个）
      path1: 可选显示网址路径 1（如 "Promo"）
      path2: 可选显示网址路径 2（如 "2026"）
      status: 广告初始状态，默认 'PAUSED'（已暂停，确保小白审核后再上线）
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  cleaned_customer_id = utils.clean_customer_id(customer_id)
  cleaned_ad_group_id = utils.clean_customer_id(ad_group_id)
  norm_status = status.strip().upper()

  if len(headlines) < 3:
    raise ToolError("Google Ads 规定自适应搜索广告至少需要提供 3 个标题！")
  if len(descriptions) < 2:
    raise ToolError("Google Ads 规定自适应搜索广告至少需要提供 2 个描述！")

  prohibited_patterns = [r"\b#1\b", r"\bbest in the world\b", r"\b100% free\b"]

  valid_headlines = []
  for idx, h in enumerate(headlines[:15]):
    h_text = h.strip()
    if len(h_text) > 30:
      raise ToolError(
          f"标题 '{h_text}' 超出 30 字符长度限制（当前长度: {len(h_text)}）！"
      )
    for p in prohibited_patterns:
      if re.search(p, h_text, re.IGNORECASE):
        raise ToolError(
            f"标题 '{h_text}' 包含违反 Google 广告政策的绝对化词汇 '{p}'！"
        )
    valid_headlines.append(h_text)

  valid_descriptions = []
  for idx, d in enumerate(descriptions[:4]):
    d_text = d.strip()
    if len(d_text) > 90:
      raise ToolError(
          f"描述 '{d_text}' 超出 90 字符长度限制（当前长度: {len(d_text)}）！"
      )
    valid_descriptions.append(d_text)

  client = utils.get_googleads_client(login_customer_id=login_customer_id)
  ad_group_ad_service = utils.get_googleads_service(
      "AdGroupAdService", login_customer_id=login_customer_id
  )
  ad_group_service = utils.get_googleads_service(
      "AdGroupService", login_customer_id=login_customer_id
  )

  op = client.get_type("AdGroupAdOperation")
  ad_group_ad = op.create
  ad_group_ad.status = client.enums.AdGroupAdStatusEnum[norm_status].value
  ad_group_ad.ad_group = ad_group_service.ad_group_path(
      cleaned_customer_id, cleaned_ad_group_id
  )

  ad = ad_group_ad.ad
  ad.final_urls.append(final_url.strip())

  if path1:
    ad.responsive_search_ad.path1 = path1.strip()[:15]
  if path2:
    ad.responsive_search_ad.path2 = path2.strip()[:15]

  for h_text in valid_headlines:
    hl = client.get_type("AdTextAsset")
    hl.text = h_text
    ad.responsive_search_ad.headlines.append(hl)

  for d_text in valid_descriptions:
    ds = client.get_type("AdTextAsset")
    ds.text = d_text
    ad.responsive_search_ad.descriptions.append(ds)

  try:
    resp = ad_group_ad_service.mutate_ad_group_ads(
        customer_id=cleaned_customer_id, operations=[op]
    )
    return {
        "status": "SUCCESS",
        "ad_resource_name": resp.results[0].resource_name,
        "ad_group_id": cleaned_ad_group_id,
        "headlines_count": len(valid_headlines),
        "descriptions_count": len(valid_descriptions),
        "ad_status": norm_status,
        "summary": (
            f"成功创建自适应搜索广告！包含 {len(valid_headlines)} 个优质标题与"
            f" {len(valid_descriptions)} 个描述，初始状态为 {norm_status}。"
        ),
    }
  except GoogleAdsException as ex:
    error_msgs = [
        f"Google Ads API Error: {error.message}" for error in ex.failure.errors
    ]
    raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))


@pro_optimizer_mcp.tool()
def generate_high_converting_rsa_assets(
    product_name: str,
    target_audience: str,
    concrete_proof_points: List[str],
    price_or_threshold_filter: str | None = None,
    disqualifier_tags: List[str] | None = None,
    language_code: str = "zh",
) -> Dict[str, Any]:
    """Generates high-converting, professional RSA headlines & descriptions engineered with concrete proof, quantified value, and qualification filters.

    Filters out tire-kickers/unqualified clicks (e.g. B2C shoppers or zero-budget users) while compelling ideal buyers to take action.

    Args:
        product_name: Name of product/service (e.g. '磁帧鱼 B2B建站系统', 'Industrial Solar Inverter').
        target_audience: Specific buyer persona (e.g. '工贸一体出海工厂', 'Wholesale Distributors').
        concrete_proof_points: Hard facts/numbers (e.g. ['每年仅需几十元域名费告别昂贵服务器', '新站一周内被谷歌收录', '夜间AI自动承接WhatsApp询盘']).
        price_or_threshold_filter: Explicit price or threshold to filter out low-budget clicks (e.g. '最低起订500件', '首年仅$1起', '起价¥2980').
        disqualifier_tags: Audience qualifiers to deter wrong traffic (e.g. ['仅限B2B企业', '不适合个人零售', '专为外贸工厂定制']).
        language_code: 'zh', 'en', 'de', 'es', etc.
    """
    clean_prod = product_name.strip()
    norm_lang = language_code.lower()

    headlines = []
    descriptions = []

    # 1. 过滤型精准标题 (Disqualifier & Persona Filter) - 阻挡错误点击，节省广告费
    if disqualifier_tags:
        for tag in disqualifier_tags[:2]:
            h = f"{clean_prod} - {tag}"
            headlines.append(h[:30])
    if price_or_threshold_filter:
        headlines.append(f"{clean_prod} {price_or_threshold_filter}"[:30])

    # 2. 量化利益与实证标题 (Quantified Value & Proof) - 击中真实痛点
    for proof in concrete_proof_points[:4]:
        # 保证不超过 30 字符
        proof_h = proof.strip()
        if len(proof_h) > 28:
            proof_h = proof_h[:28]
        headlines.append(proof_h)

    # 3. 强力行动召唤 (High-intent CTA)
    if "zh" in norm_lang:
        headlines.extend([
            f"立即索取{clean_prod}报价",
            "预约专业出海建站诊断",
            "查看工贸一体成功案例"
        ])
    else:
        headlines.extend([
            f"Get {clean_prod} Quote",
            "Direct Factory Price List",
            "Book Live Demo Online"
        ])

    # 4. 4 组长文案描述（严格在 90 字符内，包含痛点+证明+门槛+行动）
    if "zh" in norm_lang:
        descriptions = [
            f"专为{target_audience}打造！{concrete_proof_points[0] if concrete_proof_points else '告别传统高昂服务器开销'}，系统完全由您自有账户掌控。",
            f"还在为没有海外询盘发愁？{concrete_proof_points[1] if len(concrete_proof_points)>1 else '技术底座谷歌98分秒级打开'}，内置AI客服守住夜间线索！",
            f"{price_or_threshold_filter if price_or_threshold_filter else '按需灵活选购透明交付'}。{disqualifier_tags[0] if disqualifier_tags else '专注B2B官网与营销站'}，立即在线咨询方案。",
            "支持多语言站群与全方位SEO架构，海外采购商主动找上门。今天预约即享专属出海建站优化指导！"
        ]
    else:
        descriptions = [
            f"Engineered for {target_audience}. {concrete_proof_points[0] if concrete_proof_points else 'Fast global deployment'} with 100% data ownership.",
            f"Stop wasting budget on slow hosting. {concrete_proof_points[1] if len(concrete_proof_points)>1 else 'Rank faster on Google'} with built-in AI lead capture.",
            f"{price_or_threshold_filter if price_or_threshold_filter else 'Transparent pricing'}. {disqualifier_tags[0] if disqualifier_tags else 'Built strictly for B2B enterprises'}.",
            "Get a custom overseas expansion proposal today. Talk with our deployment specialists now!"
        ]

    # 清洗确保长度符合 Google 规范 (Headline <= 30, Description <= 90)
    final_headlines = [h[:30] for h in headlines][:12]
    final_descriptions = [d[:90] for d in descriptions][:4]

    return {
        "status": "SUCCESS",
        "product_name": product_name,
        "language_code": norm_lang,
        "total_headlines": len(final_headlines),
        "total_descriptions": len(final_descriptions),
        "headlines": final_headlines,
        "descriptions": final_descriptions,
        "marketing_psychology_highlights": {
            "filter_mechanism": "通过标注明确门槛与受众身份，在用户点击前主动阻断无效/零散个人点击，降低废点击率；",
            "proof_mechanism": "用硬核可感知的利益（如具体费用、收录时效、具体时段接单）替代空洞抽象的技术宣称；",
            "cta_alignment": "引导明确商业行动，拉升落地页表单转化率。"
        }
    }

