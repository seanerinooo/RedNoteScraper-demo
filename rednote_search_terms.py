# -*- coding: utf-8 -*-
"""
rednote_search_terms.py — keyword config for finding Singapore 地陪 / 地接 /
agency-affiliated individuals who can route diners to Ipoh Town Kopitiam (Jewel Changi).

Import into RedNoteScraper:
    from rednote_search_terms import ALL_TERMS, TIERS, BIO_SIGNALS, NEGATIVE_KEYWORDS

Notes on RedNote search behaviour:
  - No boolean operators. Two-token phrases ("新加坡 地陪") work best.
  - Sort by 最新 for active operators; 最热 for viral-post discovery.
  - Broad terms (新加坡旅游) are ~99% tourist UGC — deprioritise or skip.
  - The people you want usually have a WeChat ID in bio and pinned 报价 notes.
"""

# ---------------------------------------------------------------------------
# TIER 1 — Operator identity terms. Highest hit rate for people who take bookings.
# ---------------------------------------------------------------------------
TIER_1_OPERATOR_IDENTITY = [
    "新加坡地陪",
    "新加坡地接",
    "新加坡地接社",
    "新加坡导游",
    "新加坡中文导游",
    "新加坡华人导游",
    "新加坡私人导游",
    "新加坡持证导游",
    "新加坡专业导游",
    "新加坡包车",
    "新加坡包车导游",
    "新加坡包车一日游",
    "新加坡接机",
    "新加坡接送机",
    "新加坡定制游",
    "新加坡定制行程",
    "新加坡当地导游",
    "新加坡随行翻译",
]

# ---------------------------------------------------------------------------
# TIER 2 — Trade / agency-affiliation signals. Finds 计调, OP, and agency staff
# running personal accounts (the pattern flagged in Chinese trade press: most
# "individual" accounts are actually agency-backed).
# ---------------------------------------------------------------------------
TIER_2_TRADE_AFFILIATION = [
    "新加坡旅行社",
    "新加坡旅游公司",
    "新加坡组团社",
    "新加坡计调",
    "新加坡同业",
    "同业合作 新加坡",
    "新加坡同业报价",
    "新加坡地接报价",
    "新加坡收客",
    "新加坡带团",
    "新加坡领队",
    "新马地接",
    "新马泰地接",
]

# ---------------------------------------------------------------------------
# TIER 3 — Group-type terms. These are the itinerary-controlled, meal-included
# segments — the ones where a guide actually decides where the bus stops.
# Highest commercial value for a group-menu pitch.
# ---------------------------------------------------------------------------
TIER_3_GROUP_SEGMENTS = [
    "新加坡研学",
    "新加坡研学团",
    "新加坡游学",
    "新加坡夏令营",
    "新加坡冬令营",
    "新加坡商务考察",
    "新加坡考察团",
    "新加坡参访团",
    "新加坡会奖",
    "新加坡团建",
    "新加坡企业出海",
    "新加坡亲子团",
    "新加坡亲子游 行程",
    "新加坡老年团",
    "新加坡银发团",
    "新加坡医疗团",
    "新加坡体检团",
    "新马旅游团",
    "新马六日游",
    "新加坡跟团游",
]

# ---------------------------------------------------------------------------
# TIER 4 — Geographic proximity. Creators already posting about Jewel/Changi are
# the warmest content-collab targets — no education needed on the location.
# ---------------------------------------------------------------------------
TIER_4_JEWEL_CHANGI = [
    "星耀樟宜",
    "星耀樟宜 美食",
    "星耀樟宜 攻略",
    "星耀樟宜 一日游",
    "樟宜机场 攻略",
    "樟宜机场 美食",
    "樟宜机场 转机",
    "樟宜机场 长转机",
    "新加坡转机 一日游",
    "新加坡机场 落地",
]

# ---------------------------------------------------------------------------
# TIER 5 — F&B / kopitiam intent. For food-vertical KOLs and 探店 accounts.
# Use for tasting-collab outreach rather than commission deals.
# ---------------------------------------------------------------------------
TIER_5_FNB_INTENT = [
    "新加坡美食攻略",
    "新加坡探店",
    "新加坡必吃",
    "新加坡早餐",
    "新加坡老字号",
    "新加坡南洋咖啡",
    "新加坡咖椰吐司",
    "新加坡半熟蛋",
    "怡保白咖啡",
    "新加坡 娘惹",
    "新加坡 咖啡店文化",
]

# ---------------------------------------------------------------------------
# TIER 6 — English / bilingual. Lower volume on RedNote but catches SG-resident
# creators and inbound-facing operators who post in both languages.
# ---------------------------------------------------------------------------
TIER_6_ENGLISH = [
    "Singapore private tour guide",
    "Singapore tour guide Chinese",
    "Singapore itinerary planner",
    "Singapore charter car",
    "Jewel Changi food guide",
    "Singapore layover tour",
]

TIERS = {
    1: TIER_1_OPERATOR_IDENTITY,
    2: TIER_2_TRADE_AFFILIATION,
    3: TIER_3_GROUP_SEGMENTS,
    4: TIER_4_JEWEL_CHANGI,
    5: TIER_5_FNB_INTENT,
    6: TIER_6_ENGLISH,
}

ALL_TERMS = [t for tier in TIERS.values() for t in tier]

# ---------------------------------------------------------------------------
# POST-FILTER: bio/caption signals that a profile actually takes bookings.
# Score a profile by how many of these appear — 2+ is a strong lead.
# ---------------------------------------------------------------------------
BIO_SIGNALS = {
    "contact_route": ["微信", "wx", "加v", "加V", "私信", "vx", "WhatsApp", "whatsapp"],
    "commercial_intent": ["咨询", "报价", "接单", "可约", "名额", "预定", "预订",
                          "招募", "拼团", "已成团", "余位", "行程单"],
    "operator_role": ["地陪", "地接", "导游", "领队", "计调", "包车", "定制",
                      "旅行社", "同业", "OP", "接机"],
    "group_capability": ["研学", "考察", "团建", "会奖", "亲子团", "散拼",
                         "大巴", "旅游巴士", "45座", "商务车"],
}

# Terms that indicate noise — drop profiles matching these unless they also
# score high on operator_role.
NEGATIVE_KEYWORDS = [
    "移民", "留学中介", "房产", "买房", "招聘", "求职", "代购",
    "签证代办", "公司注册", "开户", "理财", "保险", "美容", "医美",
]

# ---------------------------------------------------------------------------
# LEAD SCORING — rough priority for outreach ordering.
# ---------------------------------------------------------------------------
def score_profile(bio: str, followers: int = 0, top_likes: int = 0) -> int:
    """Higher = better lead. Operator identity beats raw follower count:
    a 2k-follower 地陪 who moves 40-pax buses is worth more than a 50k lifestyle KOL."""
    bio = bio or ""
    score = 0
    for kw in BIO_SIGNALS["operator_role"]:
        if kw in bio:
            score += 25
            break
    for kw in BIO_SIGNALS["group_capability"]:
        if kw in bio:
            score += 20
            break
    for kw in BIO_SIGNALS["contact_route"]:
        if kw in bio:
            score += 15
            break
    for kw in BIO_SIGNALS["commercial_intent"]:
        if kw in bio:
            score += 10
            break
    if followers >= 50_000:
        score += 15
    elif followers >= 10_000:
        score += 10
    elif followers >= 2_000:
        score += 5
    if top_likes >= 10_000:
        score += 10
    elif top_likes >= 5_000:
        score += 5
    for kw in NEGATIVE_KEYWORDS:
        if kw in bio:
            score -= 30
            break
    return score


if __name__ == "__main__":
    print(f"{len(ALL_TERMS)} terms across {len(TIERS)} tiers")
    for n, terms in TIERS.items():
        print(f"  Tier {n}: {len(terms)}")
