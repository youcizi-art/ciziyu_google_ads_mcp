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

"""Tools for creating and modifying Google Ads campaigns, ad groups, budgets, and keywords."""

from typing import Any, Dict, List, Optional
import uuid
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from google.ads.googleads.errors import GoogleAdsException
from google.api_core import protobuf_helpers

import ads_mcp.utils as utils

mutate_mcp = FastMCP("mutate")


@mutate_mcp.tool()
def create_paused_search_campaign(
    customer_id: str | int,
    campaign_name: str,
    daily_budget_amount: float = 10.0,
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """在指定 Google Ads 账号中创建一个处于【已暂停 (PAUSED)】状态的搜索广告系列，只设置不开启投放。

    Args:
        customer_id: 10位目标客户广告账号 ID（不含连字符）
        campaign_name: 要创建的广告系列名称
        daily_budget_amount: 每日预算金额（按账号当地币种计算，默认 10.0，因处于暂停状态不会产生实际扣费）
        login_customer_id: 可选的 MCC 经理账号 ID

    Returns:
        Dict[str, Any]: 创建成功的预算与广告系列资源信息
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    client = utils.get_googleads_client(login_customer_id=login_customer_id)

    try:
        # 1. 创建独立日预算
        budget_service = utils.get_googleads_service(
            "CampaignBudgetService", login_customer_id=login_customer_id
        )
        budget_operation = client.get_type("CampaignBudgetOperation")
        budget = budget_operation.create
        budget.name = f"{campaign_name}_Budget_{uuid.uuid4().hex[:6]}"
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget.amount_micros = int(round(daily_budget_amount * 1_000_000))
        budget.explicitly_shared = False

        budget_response = budget_service.mutate_campaign_budgets(
            customer_id=cleaned_customer_id, operations=[budget_operation]
        )
        budget_resource_name = budget_response.results[0].resource_name

        # 2. 创建搜索广告系列，强制设置为 PAUSED（已暂停，绝不自动开启）
        campaign_service = utils.get_googleads_service(
            "CampaignService", login_customer_id=login_customer_id
        )
        campaign_operation = client.get_type("CampaignOperation")
        campaign = campaign_operation.create
        campaign.name = campaign_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.SEARCH
        )
        # NOTE: 严格遵循安全要求，仅设置广告系列而不开启投放
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.campaign_budget = budget_resource_name

        client.copy_from(campaign.manual_cpc, client.get_type("ManualCpc"))

        campaign.network_settings.target_google_search = True
        campaign.network_settings.target_search_network = True
        campaign.network_settings.target_content_network = False
        campaign.network_settings.target_partner_search_network = False

        if hasattr(campaign, "contains_eu_political_advertising"):
            campaign.contains_eu_political_advertising = (
                client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
            )

        campaign_response = campaign_service.mutate_campaigns(
            customer_id=cleaned_customer_id, operations=[campaign_operation]
        )
        campaign_resource_name = campaign_response.results[0].resource_name

        return {
            "status": "SUCCESS",
            "customer_id": cleaned_customer_id,
            "campaign_name": campaign_name,
            "campaign_status": "PAUSED",
            "campaign_resource_name": campaign_resource_name,
            "budget_resource_name": budget_resource_name,
            "daily_budget_amount": daily_budget_amount,
        }
    except GoogleAdsException as ex:
        error_msgs = [
            f"Google Ads API Error: {error.message}"
            for error in ex.failure.errors
        ]
        raise ToolError(
            f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs)
        )


@mutate_mcp.tool()
def update_campaign_status(
    customer_id: str | int,
    campaign_id: str | int,
    status: str = "PAUSED",
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """修改指定广告系列的状态（PAUSED 暂停 或 ENABLED 启用）。

    Args:
        customer_id: 10位目标客户广告账号 ID
        campaign_id: 广告系列 ID
        status: 目标状态，可选 'PAUSED' 或 'ENABLED'
        login_customer_id: 可选的 MCC 经理账号 ID
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    cleaned_campaign_id = utils.clean_customer_id(campaign_id)
    normalized_status = status.strip().upper()
    if normalized_status not in ("PAUSED", "ENABLED"):
        raise ToolError("status 仅允许传入 'PAUSED' 或 'ENABLED'")

    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    try:
        campaign_service = utils.get_googleads_service(
            "CampaignService", login_customer_id=login_customer_id
        )
        campaign_operation = client.get_type("CampaignOperation")
        campaign = campaign_operation.update
        campaign.resource_name = campaign_service.campaign_path(
            cleaned_customer_id, cleaned_campaign_id
        )
        campaign.status = client.enums.CampaignStatusEnum[normalized_status].value

        client.copy_from(
            campaign_operation.update_mask,
            protobuf_helpers.field_mask(None, campaign._pb),
        )

        response = campaign_service.mutate_campaigns(
            customer_id=cleaned_customer_id, operations=[campaign_operation]
        )
        return {
            "status": "SUCCESS",
            "campaign_resource_name": response.results[0].resource_name,
            "new_status": normalized_status,
        }
    except GoogleAdsException as ex:
        error_msgs = [
            f"Google Ads API Error: {error.message}"
            for error in ex.failure.errors
        ]
        raise ToolError(
            f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs)
        )


@mutate_mcp.tool()
def update_campaign_budget(
    customer_id: str | int,
    budget_id: str | int,
    daily_budget_amount: float,
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """修改指定预算（CampaignBudget）的每日预算金额。

    Args:
        customer_id: 10位目标客户广告账号 ID
        budget_id: 预算 ID（可通过 search 查询 campaign_budget.id 获取）
        daily_budget_amount: 新的每日预算金额（按账号当地币种计算，如 20.0）
        login_customer_id: 可选的 MCC 经理账号 ID
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    cleaned_budget_id = utils.clean_customer_id(budget_id)
    client = utils.get_googleads_client(login_customer_id=login_customer_id)

    try:
        budget_service = utils.get_googleads_service(
            "CampaignBudgetService", login_customer_id=login_customer_id
        )
        budget_operation = client.get_type("CampaignBudgetOperation")
        budget = budget_operation.update
        budget.resource_name = budget_service.campaign_budget_path(
            cleaned_customer_id, cleaned_budget_id
        )
        budget.amount_micros = int(round(daily_budget_amount * 1_000_000))

        client.copy_from(
            budget_operation.update_mask,
            protobuf_helpers.field_mask(None, budget._pb),
        )

        response = budget_service.mutate_campaign_budgets(
            customer_id=cleaned_customer_id, operations=[budget_operation]
        )
        return {
            "status": "SUCCESS",
            "budget_resource_name": response.results[0].resource_name,
            "new_daily_budget_amount": daily_budget_amount,
        }
    except GoogleAdsException as ex:
        error_msgs = [
            f"Google Ads API Error: {error.message}"
            for error in ex.failure.errors
        ]
        raise ToolError(
            f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs)
        )


@mutate_mcp.tool()
def create_ad_group(
    customer_id: str | int,
    campaign_id: str | int,
    ad_group_name: str,
    cpc_bid_amount: float = 1.0,
    status: str = "PAUSED",
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """在指定广告系列下创建一个广告组（Ad Group），默认处于 PAUSED（暂停）状态。

    Args:
        customer_id: 10位目标客户广告账号 ID
        campaign_id: 所属广告系列 ID
        ad_group_name: 广告组名称
        cpc_bid_amount: 默认单次点击最高出价（按账号币种计算，如 1.0）
        status: 状态，可选 'PAUSED'（默认）或 'ENABLED'
        login_customer_id: 可选的 MCC 经理账号 ID
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    cleaned_campaign_id = utils.clean_customer_id(campaign_id)
    normalized_status = status.strip().upper()
    if normalized_status not in ("PAUSED", "ENABLED"):
        raise ToolError("status 仅允许传入 'PAUSED' 或 'ENABLED'")

    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    try:
        ad_group_service = utils.get_googleads_service(
            "AdGroupService", login_customer_id=login_customer_id
        )
        campaign_service = utils.get_googleads_service(
            "CampaignService", login_customer_id=login_customer_id
        )
        operation = client.get_type("AdGroupOperation")
        ad_group = operation.create
        ad_group.name = ad_group_name
        ad_group.status = client.enums.AdGroupStatusEnum[normalized_status].value
        ad_group.campaign = campaign_service.campaign_path(
            cleaned_customer_id, cleaned_campaign_id
        )
        ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        ad_group.cpc_bid_micros = int(round(cpc_bid_amount * 1_000_000))

        response = ad_group_service.mutate_ad_groups(
            customer_id=cleaned_customer_id, operations=[operation]
        )
        return {
            "status": "SUCCESS",
            "ad_group_resource_name": response.results[0].resource_name,
            "ad_group_name": ad_group_name,
            "ad_group_status": normalized_status,
        }
    except GoogleAdsException as ex:
        error_msgs = [
            f"Google Ads API Error: {error.message}"
            for error in ex.failure.errors
        ]
        raise ToolError(
            f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs)
        )


@mutate_mcp.tool()
def add_keyword_to_ad_group(
    customer_id: str | int,
    ad_group_id: str | int,
    keyword_text: str,
    match_type: str = "EXACT",
    negative: bool = False,
    status: str = "PAUSED",
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """向指定广告组添加关键词或否定关键词。

    Args:
        customer_id: 10位目标客户广告账号 ID
        ad_group_id: 目标广告组 ID
        keyword_text: 关键词文本
        match_type: 匹配模式，可选 'EXACT'（完全匹配）、'PHRASE'（词组匹配）、'BROAD'（广泛匹配）
        negative: 是否为否定关键词（True 为否定关键词，False 为正向投放关键词）
        status: 关键词状态，可选 'PAUSED'（默认）或 'ENABLED'
        login_customer_id: 可选的 MCC 经理账号 ID
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    cleaned_ad_group_id = utils.clean_customer_id(ad_group_id)
    normalized_match = match_type.strip().upper()
    if normalized_match not in ("EXACT", "PHRASE", "BROAD"):
        raise ToolError("match_type 仅允许传入 'EXACT', 'PHRASE' 或 'BROAD'")
    normalized_status = status.strip().upper()
    if normalized_status not in ("PAUSED", "ENABLED"):
        raise ToolError("status 仅允许传入 'PAUSED' 或 'ENABLED'")

    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    try:
        criterion_service = utils.get_googleads_service(
            "AdGroupCriterionService", login_customer_id=login_customer_id
        )
        ad_group_service = utils.get_googleads_service(
            "AdGroupService", login_customer_id=login_customer_id
        )
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = ad_group_service.ad_group_path(
            cleaned_customer_id, cleaned_ad_group_id
        )
        if negative:
            criterion.negative = True
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        else:
            criterion.status = client.enums.AdGroupCriterionStatusEnum[
                normalized_status
            ].value

        criterion.keyword.text = keyword_text
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
            normalized_match
        ].value

        response = criterion_service.mutate_ad_group_criteria(
            customer_id=cleaned_customer_id, operations=[operation]
        )
        return {
            "status": "SUCCESS",
            "keyword_resource_name": response.results[0].resource_name,
            "keyword_text": keyword_text,
            "match_type": normalized_match,
            "negative": negative,
            "keyword_status": "ENABLED" if negative else normalized_status,
        }
    except GoogleAdsException as ex:
        error_msgs = [
            f"Google Ads API Error: {error.message}"
            for error in ex.failure.errors
        ]
        raise ToolError(
            f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs)
        )


@mutate_mcp.tool()
def set_campaign_geo_targets(
    customer_id: str | int,
    campaign_id: str | int,
    target_countries: List[str] | None = None,
    exclude_countries: List[str] | None = None,
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """Sets positive target geographic locations and negative excluded geographic locations for a campaign.

    Args:
        customer_id: The Google Ads customer ID (e.g. '620-450-6866').
        campaign_id: The ID of the campaign to target or exclude locations on.
        target_countries: List of 2-letter ISO country codes or geo constants to positively target (e.g. ['US', 'DE', 'MX', 'VN']).
        exclude_countries: List of 2-letter ISO country codes or geo constants to exclude (e.g. ['IN', 'PK', 'NG']).
        login_customer_id: Optional manager MCC customer ID.
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    cleaned_campaign_id = str(campaign_id).strip()

    from ads_mcp.tools.keywords import BUILTIN_COUNTRIES

    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    criterion_service = utils.get_googleads_service(
        "CampaignCriterionService", login_customer_id=login_customer_id
    )

    operations = []
    targeted_list = []
    excluded_list = []

    def resolve_geo_constant(code_or_name: str) -> tuple[str, str]:
        upper = code_or_name.strip().upper()
        if upper in BUILTIN_COUNTRIES:
            geo_id, name = BUILTIN_COUNTRIES[upper]
            return f"geoTargetConstants/{geo_id}", f"{name} ({upper})"
        if code_or_name.startswith("geoTargetConstants/"):
            return code_or_name, code_or_name
        if code_or_name.isdigit():
            return f"geoTargetConstants/{code_or_name}", f"GeoTarget/{code_or_name}"
        # Fallback to search
        return f"geoTargetConstants/{code_or_name}", code_or_name

    if target_countries:
        for c in target_countries:
            geo_res, name = resolve_geo_constant(c)
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = f"customers/{cleaned_customer_id}/campaigns/{cleaned_campaign_id}"
            crit.location.geo_target_constant = geo_res
            crit.negative = False
            operations.append(op)
            targeted_list.append(name)

    if exclude_countries:
        for c in exclude_countries:
            geo_res, name = resolve_geo_constant(c)
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = f"customers/{cleaned_customer_id}/campaigns/{cleaned_campaign_id}"
            crit.location.geo_target_constant = geo_res
            crit.negative = True
            operations.append(op)
            excluded_list.append(name)

    if not operations:
        return {
            "status": "SKIPPED",
            "message": "No target or exclude countries provided."
        }

    try:
        response = criterion_service.mutate_campaign_criteria(
            customer_id=cleaned_customer_id, operations=operations
        )
        return {
            "status": "SUCCESS",
            "campaign_id": cleaned_campaign_id,
            "targeted_locations": targeted_list,
            "excluded_locations": excluded_list,
            "total_criteria_mutated": len(response.results),
            "summary": f"成功为广告系列 {cleaned_campaign_id} 配置地理定向：定向 {len(targeted_list)} 个地区，排除 {len(excluded_list)} 个地区。"
        }
    except GoogleAdsException as ex:
        error_msgs = [f"Google Ads API Error: {error.message}" for error in ex.failure.errors]
        raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))


@mutate_mcp.tool()
def set_campaign_ad_schedule(
    customer_id: str | int,
    campaign_id: str | int,
    schedule_preset: str = "B2B_BUSINESS_HOURS",
    custom_schedules: List[Dict[str, Any]] | None = None,
    login_customer_id: str | int | None = None,
) -> Dict[str, Any]:
    """Sets precise ad delivery schedules for a campaign (e.g. B2B business hours or custom time slots).

    Args:
        customer_id: The Google Ads customer ID (e.g. '620-450-6866').
        campaign_id: The ID of the campaign to schedule.
        schedule_preset: 'B2B_BUSINESS_HOURS' (Mon-Fri 08:00-18:00 target timezone), 'ALL_WEEK_WORK_HOURS' (Mon-Sun 08:00-22:00), or 'CUSTOM'.
        custom_schedules: List of dicts if schedule_preset='CUSTOM', each containing:
            - 'day_of_week': 'MONDAY', 'TUESDAY', etc.
            - 'start_hour': int (0-23)
            - 'start_minute': 'ZERO', 'FIFTEEN', 'THIRTY', or 'FORTY_FIVE'
            - 'end_hour': int (0-24)
            - 'end_minute': 'ZERO', 'FIFTEEN', 'THIRTY', or 'FORTY_FIVE'
        login_customer_id: Optional manager MCC customer ID.
    """
    cleaned_customer_id = utils.clean_customer_id(customer_id)
    cleaned_campaign_id = str(campaign_id).strip()

    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    criterion_service = utils.get_googleads_service(
        "CampaignCriterionService", login_customer_id=login_customer_id
    )

    operations = []
    slots_info = []

    if schedule_preset == "B2B_BUSINESS_HOURS":
        work_days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
        for day in work_days:
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = f"customers/{cleaned_customer_id}/campaigns/{cleaned_campaign_id}"
            crit.ad_schedule.day_of_week = client.enums.DayOfWeekEnum[day].value
            crit.ad_schedule.start_hour = 8
            crit.ad_schedule.start_minute = client.enums.MinuteOfHourEnum.ZERO.value
            crit.ad_schedule.end_hour = 19
            crit.ad_schedule.end_minute = client.enums.MinuteOfHourEnum.ZERO.value
            operations.append(op)
            slots_info.append(f"{day} 08:00 - 19:00")
    elif schedule_preset == "ALL_WEEK_WORK_HOURS":
        all_days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        for day in all_days:
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = f"customers/{cleaned_customer_id}/campaigns/{cleaned_campaign_id}"
            crit.ad_schedule.day_of_week = client.enums.DayOfWeekEnum[day].value
            crit.ad_schedule.start_hour = 8
            crit.ad_schedule.start_minute = client.enums.MinuteOfHourEnum.ZERO.value
            crit.ad_schedule.end_hour = 22
            crit.ad_schedule.end_minute = client.enums.MinuteOfHourEnum.ZERO.value
            operations.append(op)
            slots_info.append(f"{day} 08:00 - 22:00")
    elif custom_schedules:
        for slot in custom_schedules:
            op = client.get_type("CampaignCriterionOperation")
            crit = op.create
            crit.campaign = f"customers/{cleaned_customer_id}/campaigns/{cleaned_campaign_id}"
            day = slot["day_of_week"].upper()
            crit.ad_schedule.day_of_week = client.enums.DayOfWeekEnum[day].value
            crit.ad_schedule.start_hour = int(slot["start_hour"])
            crit.ad_schedule.start_minute = client.enums.MinuteOfHourEnum[slot.get("start_minute", "ZERO")].value
            crit.ad_schedule.end_hour = int(slot["end_hour"])
            crit.ad_schedule.end_minute = client.enums.MinuteOfHourEnum[slot.get("end_minute", "ZERO")].value
            operations.append(op)
            slots_info.append(f"{day} {slot['start_hour']}:00 - {slot['end_hour']}:00")

    if not operations:
        return {
            "status": "SKIPPED",
            "message": "No schedule slots created."
        }

    try:
        response = criterion_service.mutate_campaign_criteria(
            customer_id=cleaned_customer_id, operations=operations
        )
        return {
            "status": "SUCCESS",
            "campaign_id": cleaned_campaign_id,
            "preset_applied": schedule_preset,
            "scheduled_slots": slots_info,
            "total_slots_created": len(response.results),
            "summary": f"成功为广告系列 {cleaned_campaign_id} 设置精准排期：共添加 {len(slots_info)} 个投放时段。"
        }
    except GoogleAdsException as ex:
        error_msgs = [f"Google Ads API Error: {error.message}" for error in ex.failure.errors]
        raise ToolError(f"Request ID: {ex.request_id}\n" + "\n".join(error_msgs))

