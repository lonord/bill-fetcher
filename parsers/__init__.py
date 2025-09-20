"""
邮件解析器包

这个包包含了各种邮件格式的解析器，每个解析器都实现了标准的接口：
- match(subject, sender): 判断邮件是否匹配该解析器
- parse(msg, msg_id, output_dir): 解析邮件内容
- extract(filename, extract_dir, config): 提取文件内容
"""

from .parser_alipay import match as alipay_match, parse as alipay_parse, extract as alipay_extract
from .parser_cmbcc import match as cmbcc_match, parse as cmbcc_parse, extract as cmbcc_extract
from .parser_wechat import match as wechat_match, parse as wechat_parse, extract as wechat_extract

# 所有可用的解析器
PARSERS = [
    {
        "name": "支付宝",
        "match": alipay_match,
        "parse": alipay_parse,
        "extract": alipay_extract
    },
    {
        "name": "招商银行信用卡",
        "match": cmbcc_match,
        "parse": cmbcc_parse,
        "extract": cmbcc_extract
    },
    {
        "name": "微信支付",
        "match": wechat_match,
        "parse": wechat_parse,
        "extract": wechat_extract
    }
]

def get_parser_by_name(name):
    """根据名称获取解析器"""
    for parser in PARSERS:
        if parser["name"] == name:
            return parser
    return None

def get_all_parsers():
    """获取所有解析器"""
    return PARSERS

def find_matching_parser(subject, sender):
    """根据邮件主题和发件人找到匹配的解析器"""
    for parser in PARSERS:
        if parser["match"](subject, sender):
            return parser
    return None

# 为了向后兼容，也导出各个解析器模块
__all__ = [
    "PARSERS",
    "get_parser_by_name", 
    "get_all_parsers",
    "find_matching_parser",
    "alipay_match", "alipay_parse", "alipay_extract",
    "cmbcc_match", "cmbcc_parse", "cmbcc_extract", 
    "wechat_match", "wechat_parse", "wechat_extract"
]
