import hashlib
from urllib.parse import urlencode, unquote_plus


def sign(data: dict, shop_id: str, token: str) -> dict:
    """
    OKPay 签名逻辑（与 PHP SDK 完全一致）:
    1. 加入 id（商户ID）
    2. 去掉空值 (array_filter)
    3. 按 key 排序 (ksort)
    4. urlencode -> urldecode -> 拼接 &token=密钥
    5. MD5 转大写
    """
    data = dict(data)
    data['id'] = shop_id
    # 过滤空值
    data = {k: v for k, v in data.items() if v is not None and v != ''}
    # 按 key 排序
    sorted_data = dict(sorted(data.items()))
    # 生成签名字符串
    query_string = urlencode(sorted_data)
    decoded = unquote_plus(query_string)
    sign_string = decoded + '&token=' + token
    # MD5 签名
    sorted_data['sign'] = hashlib.md5(sign_string.encode()).hexdigest().upper()
    return sorted_data


def signed_request(data: dict, shop_id: str, token: str) -> dict:
    """兼容旧接口名称"""
    return sign(data, shop_id, token)


def verify(payload: dict, token: str) -> bool:
    """
    验证回调签名（用于回调通知校验）
    """
    data = dict(payload)
    received_sign = data.pop('sign', '')
    if not received_sign:
        return False
    # 过滤空值
    data = {k: v for k, v in data.items() if v is not None and v != ''}
    # 按 key 排序
    sorted_data = dict(sorted(data.items()))
    # 生成签名
    query_string = urlencode(sorted_data)
    decoded = unquote_plus(query_string)
    sign_string = decoded + '&token=' + token
    expected_sign = hashlib.md5(sign_string.encode()).hexdigest().upper()
    return received_sign.upper() == expected_sign
