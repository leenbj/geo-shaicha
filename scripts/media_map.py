# -*- coding: utf-8 -*-
"""来源域名 -> 媒体名映射。新增媒体直接往 RULES 里加。"""
import re

RULES = [
    (r"baijiahao\.baidu\.com", "百家号"),
    (r"sohu\.com", "搜狐号"),
    (r"toutiao\.com|toutiaohao", "头条号"),
    (r"163\.com", "网易号"),
    (r"qcc\.com", "企查查"),
    (r"tianyancha\.com", "天眼查"),
    (r"aiqicha\.baidu\.com", "爱企查"),
    (r"qixin\.com", "启信宝"),
    (r"shuidi\.cn", "水滴信用"),
    (r"mp\.weixin\.qq\.com|weixin\.qq\.com", "微信公众号"),
    (r"zhihu\.com", "知乎"),
    (r"baike\.baidu\.com", "百度百科"),
    (r"baidu\.com/s\?|baidu\.com/link", "百度搜索结果"),
    (r"xiaohongshu\.com|xhslink", "小红书"),
    (r"douyin\.com", "抖音"),
    (r"bilibili\.com", "B站"),
    (r"1688\.com", "1688"),
    (r"made-in-china\.com", "中国制造网"),
    (r"\.gov\.cn", "政务/监管网站"),
    (r"36kr\.com", "36氪"),
    (r"eastmoney\.com|sina\.com\.cn|cnstock", "财经媒体"),
    (r"chinadaily|people\.com\.cn|xinhuanet", "央媒"),
]

SELF_HINTS = (r"\.网址",)


def media_of(url: str) -> str:
    u = (url or "").lower()
    if not u:
        return ""
    if ".网址" in u:
        return "企业自有 .网址 站点"
    for pat, name in RULES:
        if re.search(pat, u):
            return name
    m = re.match(r"https?://([^/]+)/?", u)
    return m.group(1) if m else "其他"
