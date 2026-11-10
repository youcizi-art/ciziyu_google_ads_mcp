# Google Ads MCP 专家营销系统客户交付与架构手册

## 一、 系统架构总览

本系统为面向全球出海客户（工贸一体出口、跨境B2B/B2C、商业服务、SaaS软件、教育出海等）打造的企业级 **AI 驱动 Google Ads 自动化专家操盘手系统**。

系统部署于 `C:\scripts\`，由以下三大核心子项目协同构成：
1. **`google-ads-mcp`**：Google Ads 官方 API 标准 MCP 服务，挂载 20+ 个自动化操作工具。
2. **`marketing-scout-mcp`**：前置官网与竞品落地页信息侦察 MCP 服务。
3. **`google-ads-skills`**：6 大核心出海操盘手实战技能工坊（涵盖意图漏斗、高转化物料、风控财务、落地页审计、推演决策与客户交互表单）。

---

## 二、 MCP 核心工具清单与功能定义

### 1. 意图挖掘与多市场研究工具 (`ads_mcp.tools.keywords`)
- `build_comprehensive_intent_keyword_pool`: 从 6 大买家搜索意图发散关键词，经由 Google Ads API 验证出价，实现 **PPC 竞价词** 与 **SEO 免费引流词** 的智能分流。
- `mine_b2b_intent_longtail_keywords`: 自动挖掘包含供应商身份、批量询价、定制参数的 B2B 核心高转化长尾词（母语原生）。
- `universal_keyword_research`: 支持全球任意国家 + 任意语种的 Google Ads 官方搜索量、竞争度、历史 12 个月趋势与页首出价区间查询。
- `analyze_youtube_market`: YouTube 视频供给量、头部频道垄断度与中位数播放量分析，指导视频广告切入策略。
- `discover_partner_sites`: 发现目标国垂直行业站点、客座博客与行业黄页，拓展展示广告与再营销位。
- `search_market_constants`: 查询全球国家/地区 `geoTargetConstants` 与语言 `languageConstants`。

### 2. 精准定向与系列构建工具 (`ads_mcp.tools.mutate`)
- `create_paused_search_campaign`: 创建安全的搜索广告系列，状态锁定为 `PAUSED`（杜绝未经审批自动扣费）。
- `set_campaign_geo_targets`: 设置积极定向国家/地区，同时排除点击农场与非目标欺诈区域。
- `set_campaign_ad_schedule`: 精准排期，支持 B2B 工作日时段（周一至周五 08:00~19:00），避免深夜闲逛点击浪费预算。
- `create_ad_group`: 创建 STAG 紧密主题广告组。
- `add_keyword_to_ad_group`: 添加精确匹配（EXACT）与词组匹配（PHRASE）关键词。
- `update_campaign_budget`: 动态调整每日预算。
- `update_campaign_status`: 变更系列状态（PAUSED / ENABLED）。

### 3. 高转化文案与风控工具 (`ads_mcp.tools.optimizer`)
- `generate_high_converting_rsa_assets`: 营销文案生成引擎。集成**门槛过滤机制（阻断非目标用户）**与**量化硬核实证（替代空洞套话）**。
- `create_responsive_search_ad`: 创建自适应搜索广告（RSA），状态锁定为 `PAUSED`。
- `apply_multilingual_negative_guardrail`: 跨国动态多语种否定词保护网，自动排除求职、免费、破解等无效流量。
- `audit_and_mine_negative_search_terms`: 搜索词历史审计与漏斗清洗。

### 4. 附加资产工具 (`ads_mcp.tools.assets`)
- `add_campaign_sitelinks`: 绑定 4 组带有完整双描述的 Sitelinks 附加链接。
- `add_campaign_callouts`: 绑定 4~6 条宣传信息亮点。
- `add_campaign_structured_snippets`: 绑定结构化摘要。

---

## 三、 标准业务交付 SOP

```
   [客户输入官网/产品]
           │
           ▼
   步骤 1：落地页侦察 (Scout) 提取产品特点、门槛与客群
           │
           ▼
   步骤 2：多维意图发散与 PPC / SEO 分流
           │
           ▼
   步骤 3：输出《已预填客户确认表单》并与客户交互确认
           │
           ▼
   步骤 4：在 Google Ads 账户中安全构建真实资产 (PAUSED 状态)
           │
           ▼
   步骤 5：出具《交付确认卡》，由客户或授权人工一键激活
```

---

## 四、 环境变量与运行配置

在运行环境或客户端中注入：
```env
GOOGLE_ADS_DEVELOPER_TOKEN="您的开发者令牌"
GOOGLE_ADS_LOGIN_CUSTOMER_ID="您的MCC经理账号ID(如有)"
PYTHONUTF8="1"
```
MCP 配置文件位于全局 `mcp_config.json`，已默认挂载 `google-ads-mcp` 与 `marketing-scout-mcp`。
