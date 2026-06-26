"""快递鸟 API 查询服务。"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Final

from django.conf import settings

logger = logging.getLogger("apps.express_query")

# 快递鸟 API 配置（从 Django settings 读取）
_KDNIAO_API_URL: Final[str] = "https://api.kdniao.com/api/dist"
_KDNIAO_REQUEST_TYPE: Final[str] = "8002"  # 快递查询


@dataclass
class KdniaoConfig:
    """快递鸟 API 凭据。"""

    e_business_id: str
    app_key: str


def _get_config() -> KdniaoConfig:
    """从 Django settings 读取快递鸟配置。"""
    return KdniaoConfig(
        e_business_id=getattr(settings, "KDNIAO_EBUSINESS_ID", ""),
        app_key=getattr(settings, "KDNIAO_APP_KEY", ""),
    )


def _make_sign(param_json: str, app_key: str) -> str:
    """生成快递鸟 API 签名: base64(md5_hex(param + appKey))。"""
    raw = param_json + app_key
    md5_hex = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return __import__("base64").b64encode(md5_hex.encode("utf-8")).decode("utf-8")


def query_express(tracking_number: str, carrier_code: str | None = None, phone_suffix: str | None = None) -> dict:
    """
    调用快递鸟快递查询 API。

    Args:
        tracking_number: 运单号
        carrier_code: 快递公司编码（可选，8002 会自动识别）
        phone_suffix: 收/寄件人手机尾号（顺丰必填）

    Returns:
        API 返回的完整 JSON dict
    """
    config = _get_config()
    if not config.e_business_id or not config.app_key:
        raise ValueError("快递鸟 API 凭据未配置（KDNIAO_EBUSINESS_ID / KDNIAO_APP_KEY）")

    param: dict = {"LogisticCode": tracking_number}
    if carrier_code:
        param["ShipperCode"] = carrier_code
    if phone_suffix:
        param["CustomerName"] = phone_suffix

    param_json = json.dumps(param, separators=(",", ":"))
    data_sign = _make_sign(param_json, config.app_key)

    form_data = urllib.parse.urlencode({
        "RequestData": urllib.parse.quote_plus(param_json),
        "EBusinessID": config.e_business_id,
        "RequestType": _KDNIAO_REQUEST_TYPE,
        "DataSign": urllib.parse.quote_plus(data_sign),
        "DataType": "2",
    })

    req = urllib.request.Request(
        _KDNIAO_API_URL,
        data=form_data.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    logger.info("快递鸟查询请求", extra={"tracking_number": tracking_number, "carrier_code": carrier_code})

    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode("utf-8"))

    logger.info(
        "快递鸟查询结果",
        extra={
            "tracking_number": tracking_number,
            "success": result.get("Success"),
            "carrier": result.get("ShipperCode"),
            "state": result.get("State"),
            "trace_count": len(result.get("Traces", [])),
        },
    )

    return result
