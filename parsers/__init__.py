"""
Email Parser Package

This package contains parsers for various email formats, each implementing a standard interface:
- match(subject, sender): Determine if email matches this parser
- parse(msg, msg_id, output_dir): Parse email content
- extract(filename, extract_dir, config): Extract file content
"""

from .parser_alipay import match as alipay_match, parse as alipay_parse, extract as alipay_extract
from .parser_cmbcc import match as cmbcc_match, parse as cmbcc_parse, extract as cmbcc_extract
from .parser_wechat import match as wechat_match, parse as wechat_parse, extract as wechat_extract

# All available parsers
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
    """Get parser by name"""
    for parser in PARSERS:
        if parser["name"] == name:
            return parser
    return None

def get_all_parsers():
    """Get all parsers"""
    return PARSERS

def find_matching_parser(subject, sender):
    """Find matching parser based on email subject and sender"""
    for parser in PARSERS:
        if parser["match"](subject, sender):
            return parser
    return None

# For backward compatibility, also export individual parser modules
__all__ = [
    "PARSERS",
    "get_parser_by_name", 
    "get_all_parsers",
    "find_matching_parser",
    "alipay_match", "alipay_parse", "alipay_extract",
    "cmbcc_match", "cmbcc_parse", "cmbcc_extract", 
    "wechat_match", "wechat_parse", "wechat_extract"
]
