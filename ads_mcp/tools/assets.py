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

"""Tools for creating and managing Google Ads assets (Sitelinks, Callouts, Structured Snippets)."""

from typing import Any, Dict, List, Optional
import uuid
import ads_mcp.utils as utils
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException

assets_mcp = FastMCP("assets")


@assets_mcp.tool()
def add_campaign_sitelinks(
    customer_id: str | int,
    campaign_id: str | int,
    sitelinks: List[Dict[str, str]],
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【附加链接资产创建与绑定】为指定广告系列批量创建并绑定 Sitelinks 附加链接（最多4~8个），大幅扩展广告屏幕展示面积并提升点击率（CTR）。

  每个 Sitelink 字典格式要求：
  - 'link_text' (必填): 链接标题文本（最多 25 个半角字符 / 12 个汉字，如 'Pricing Plans' 或 '关于我们'）
  - 'final_url' (必填): 对应的独立二级跳转网址（如 'https://example.com/pricing'）
  - 'description1' (选填): 描述文本 1（最多 35 个半角字符）
  - 'description2' (选填): 描述文本 2（最多 35 个半角字符）

  Args:
      customer_id: 10位客户广告账号 ID
      campaign_id: 目标广告系列 ID
      sitelinks: Sitelink 配置列表
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  if not sitelinks:
    raise ToolError("提供的 sitelinks 列表不能为空")

  cleaned_customer_id = utils.clean_customer_id(customer_id)
  cleaned_campaign_id = utils.clean_customer_id(campaign_id)

  client = utils.get_googleads_client(login_customer_id=login_customer_id)
  asset_service = utils.get_googleads_service(
      "AssetService", login_customer_id=login_customer_id
  )
  camp_asset_service = utils.get_googleads_service(
      "CampaignAssetService", login_customer_id=login_customer_id
  )
  campaign_service = utils.get_googleads_service(
      "CampaignService", login_customer_id=login_customer_id
  )

  # 1. 批量创建 Sitelink Assets
  asset_ops = []
  for idx, s in enumerate(sitelinks):
    link_text = s.get("link_text", "").strip()
    final_url = s.get("final_url", "").strip()
    if not link_text or not final_url:
      raise ToolError(f"第 {idx + 1} 个 Sitelink 缺少必填的 link_text 或 final_url！")
    if len(link_text) > 25:
      raise ToolError(
          f"Sitelink 标题 '{link_text}' 超出 25 字符限制（当前: {len(link_text)}）"
      )

    desc1 = s.get("description1", "").strip()
    desc2 = s.get("description2", "").strip()
    if len(desc1) > 35 or len(desc2) > 35:
      raise ToolError("Sitelink 描述文本不得超过 35 个字符限制！")

    op = client.get_type("AssetOperation")
    asset = op.create
    asset.name = f"Sitelink_{link_text[:10]}_{uuid.uuid4().hex[:6]}"
    asset.final_urls.append(final_url)
    asset.sitelink_asset.link_text = link_text
    # 官方规则：如果设置了 description1，则 description2 也必须同时提供；若两者都未提供，则仅以单标题链接创建
    if desc1 and desc2:
      asset.sitelink_asset.description1 = desc1
      asset.sitelink_asset.description2 = desc2
    elif desc1 and not desc2:
      asset.sitelink_asset.description1 = desc1
      asset.sitelink_asset.description2 = desc1  # 自动回退对齐避免被拒
    asset_ops.append(op)

  try:
    resp_assets = asset_service.mutate_assets(
        customer_id=cleaned_customer_id, operations=asset_ops
    )
    created_asset_res_names = [r.resource_name for r in resp_assets.results]

    # 2. 将创建好的 Assets 绑定至目标广告系列
    camp_asset_ops = []
    campaign_path = campaign_service.campaign_path(
        cleaned_customer_id, cleaned_campaign_id
    )
    for asset_res in created_asset_res_names:
      op = client.get_type("CampaignAssetOperation")
      camp_asset = op.create
      camp_asset.campaign = campaign_path
      camp_asset.asset = asset_res
      camp_asset.field_type = client.enums.AssetFieldTypeEnum.SITELINK
      camp_asset_ops.append(op)

    resp_bind = camp_asset_service.mutate_campaign_assets(
        customer_id=cleaned_customer_id, operations=camp_asset_ops
    )
    bound_campaign_assets = [r.resource_name for r in resp_bind.results]

    return {
        "status": "SUCCESS",
        "campaign_id": cleaned_campaign_id,
        "created_sitelinks_count": len(bound_campaign_assets),
        "campaign_asset_resources": bound_campaign_assets,
        "summary": (
            f"成功为广告系列 {cleaned_campaign_id} 绑定"
            f" {len(bound_campaign_assets)} 个 Sitelink 附加链接！"
        ),
    }
  except GoogleAdsException as ex:
    error_msgs = [
        f"Google Ads API Error: {error.message}" for error in ex.failure.errors
    ]
    raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))


@assets_mcp.tool()
def add_campaign_callouts(
    customer_id: str | int,
    campaign_id: str | int,
    callout_texts: List[str],
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【宣传信息资产创建与绑定】为指定广告系列批量创建并绑定 Callout 宣传标签（如 '24/7 Support', 'Free Trial', '极速响应' 等），强化信任背书。

  规范约束：每个宣传文本不得超过 25 个字符（12 个汉字），建议单次传入 4~6 个。

  Args:
      customer_id: 10位客户广告账号 ID
      campaign_id: 目标广告系列 ID
      callout_texts: 宣传短标签列表，例如 ["24/7 Support", "No Hidden Fees",
        "Instant Setup", "ISO 27001 Certified"]
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  if not callout_texts:
    raise ToolError("提供的 callout_texts 列表不能为空")

  cleaned_customer_id = utils.clean_customer_id(customer_id)
  cleaned_campaign_id = utils.clean_customer_id(campaign_id)

  client = utils.get_googleads_client(login_customer_id=login_customer_id)
  asset_service = utils.get_googleads_service(
      "AssetService", login_customer_id=login_customer_id
  )
  camp_asset_service = utils.get_googleads_service(
      "CampaignAssetService", login_customer_id=login_customer_id
  )
  campaign_service = utils.get_googleads_service(
      "CampaignService", login_customer_id=login_customer_id
  )

  asset_ops = []
  for idx, txt in enumerate(callout_texts):
    clean_t = txt.strip()
    if not clean_t:
      continue
    if len(clean_t) > 25:
      raise ToolError(
          f"宣传文本 '{clean_t}' 超出 25 字符限制（当前: {len(clean_t)}）！"
      )

    op = client.get_type("AssetOperation")
    asset = op.create
    asset.name = f"Callout_{clean_t[:10]}_{uuid.uuid4().hex[:6]}"
    asset.callout_asset.callout_text = clean_t
    asset_ops.append(op)

  try:
    resp_assets = asset_service.mutate_assets(
        customer_id=cleaned_customer_id, operations=asset_ops
    )
    created_asset_res_names = [r.resource_name for r in resp_assets.results]

    camp_asset_ops = []
    campaign_path = campaign_service.campaign_path(
        cleaned_customer_id, cleaned_campaign_id
    )
    for asset_res in created_asset_res_names:
      op = client.get_type("CampaignAssetOperation")
      camp_asset = op.create
      camp_asset.campaign = campaign_path
      camp_asset.asset = asset_res
      camp_asset.field_type = client.enums.AssetFieldTypeEnum.CALLOUT
      camp_asset_ops.append(op)

    resp_bind = camp_asset_service.mutate_campaign_assets(
        customer_id=cleaned_customer_id, operations=camp_asset_ops
    )
    bound_campaign_assets = [r.resource_name for r in resp_bind.results]

    return {
        "status": "SUCCESS",
        "campaign_id": cleaned_campaign_id,
        "created_callouts_count": len(bound_campaign_assets),
        "campaign_asset_resources": bound_campaign_assets,
        "summary": (
            f"成功为广告系列 {cleaned_campaign_id} 绑定"
            f" {len(bound_campaign_assets)} 个 Callout 宣传信息资产！"
        ),
    }
  except GoogleAdsException as ex:
    error_msgs = [
        f"Google Ads API Error: {error.message}" for error in ex.failure.errors
    ]
    raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))


@assets_mcp.tool()
def add_campaign_structured_snippets(
    customer_id: str | int,
    campaign_id: str | int,
    header: str,
    values: List[str],
    login_customer_id: Optional[str | int] = None,
) -> Dict[str, Any]:
  """【结构化摘要资产创建与绑定】为指定广告系列创建并绑定 Structured Snippets 结构化摘要（如服务类型、品牌、机型、目的地等），进一步丰富广告展示细节。

  可用官方标题 (Header) 常见预选值：
  'Amenities', 'Brands', 'Courses', 'Degree programs', 'Destinations',
  'Featured hotels', 'Insurance coverage', 'Models', 'Neighborhoods',
  'Service catalog', 'Shows', 'Styles', 'Types'

  Args:
      customer_id: 10位客户广告账号 ID
      campaign_id: 目标广告系列 ID
      header: 官方支持的 Header 类别，如 'Service catalog' 或 'Types' 或 'Brands'
      values: 对应的业务特性/子类列表，例如：
        - 机械制造: ['Hydraulic Presses', 'CNC Milling Machines', 'Laser Cutters']
        - 商业法律: ['Mergers & Acquisitions', 'Contract Law', 'Tax Advisory']
        - 教育培训: ['Business Courses', 'Engineering Programs', 'Language Classes']
        - 通用服务: ['Free Consultation', '24/7 Support', 'Global Delivery']
      login_customer_id: 可选的 MCC 经理账号 ID
  """
  if not values:
    raise ToolError("提供的 values 列表不能为空")

  cleaned_customer_id = utils.clean_customer_id(customer_id)
  cleaned_campaign_id = utils.clean_customer_id(campaign_id)

  client = utils.get_googleads_client(login_customer_id=login_customer_id)
  asset_service = utils.get_googleads_service(
      "AssetService", login_customer_id=login_customer_id
  )
  camp_asset_service = utils.get_googleads_service(
      "CampaignAssetService", login_customer_id=login_customer_id
  )
  campaign_service = utils.get_googleads_service(
      "CampaignService", login_customer_id=login_customer_id
  )

  op = client.get_type("AssetOperation")
  asset = op.create
  asset.name = f"Snippet_{header[:10]}_{uuid.uuid4().hex[:6]}"
  asset.structured_snippet_asset.header = header.strip()
  for val in values:
    v_clean = val.strip()
    if v_clean:
      if len(v_clean) > 25:
        raise ToolError(f"摘要值 '{v_clean}' 超出 25 字符限制！")
      asset.structured_snippet_asset.values.append(v_clean)

  try:
    resp_asset = asset_service.mutate_assets(
        customer_id=cleaned_customer_id, operations=[op]
    )
    asset_res = resp_asset.results[0].resource_name

    op_bind = client.get_type("CampaignAssetOperation")
    camp_asset = op_bind.create
    camp_asset.campaign = campaign_service.campaign_path(
        cleaned_customer_id, cleaned_campaign_id
    )
    camp_asset.asset = asset_res
    camp_asset.field_type = client.enums.AssetFieldTypeEnum.STRUCTURED_SNIPPET

    resp_bind = camp_asset_service.mutate_campaign_assets(
        customer_id=cleaned_customer_id, operations=[op_bind]
    )

    return {
        "status": "SUCCESS",
        "campaign_id": cleaned_campaign_id,
        "header": header,
        "values_count": len(values),
        "campaign_asset_resource": resp_bind.results[0].resource_name,
        "summary": (
            f"成功为广告系列 {cleaned_campaign_id} 绑定结构化摘要 [{header}]:"
            f" {values}"
        ),
    }
  except GoogleAdsException as ex:
    error_msgs = [
        f"Google Ads API Error: {error.message}" for error in ex.failure.errors
    ]
    raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))
