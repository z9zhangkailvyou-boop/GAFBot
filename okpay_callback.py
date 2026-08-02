"""
OKPay 回调接口
接收 OKPay 支付成功通知，验证签名后更新订单状态并通知 bot
"""
import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from okpay_sign import verify
from pay import get_order, remove_order, load_all_orders, save_all_orders
import requests as http_requests

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [CALLBACK] %(message)s')

OKPAY_TOKEN = os.getenv('OKPAY_TOKEN', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# 回调通知文件（bot 轮询读取）
CALLBACK_FILE = '/root/GAFBot/callback_notifications.json'


def load_notifications():
    if os.path.exists(CALLBACK_FILE):
        try:
            with open(CALLBACK_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []


def save_notification(notification):
    """保存通知供 bot 读取"""
    notifications = load_notifications()
    notifications.append(notification)
    with open(CALLBACK_FILE, 'w') as f:
        json.dump(notifications, f, ensure_ascii=False, indent=2)


def notify_bot_via_telegram(chat_id, text):
    """通过 Telegram Bot API 直接发消息通知用户"""
    if not BOT_TOKEN:
        logging.warning("BOT_TOKEN 未配置，无法发送通知")
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        resp = http_requests.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=5)
        logging.info(f"Telegram 通知结果: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        logging.error(f"Telegram 通知失败: {e}")
        return False


@app.route('/okpay/callback', methods=['POST'])
def okpay_callback():
    """OKPay 支付回调"""
    try:
        # 获取回调数据
        data = request.form.to_dict()
        if not data:
            data = request.get_json(force=True) or {}

        logging.info(f"收到 OKPay 回调: {data}")

        # 验证签名
        if not verify(data, OKPAY_TOKEN):
            logging.warning(f"签名验证失败: {data}")
            return jsonify({'status': 'error', 'msg': '签名验证失败'}), 403

        # 验证状态
        if data.get('status') != 'success' or str(data.get('code')) != '10000':
            logging.warning(f"非成功状态回调: {data}")
            return jsonify({'status': 'success'})

        # 提取回调信息
        callback_data = data.get('data', data)
        if isinstance(callback_data, str):
            try:
                callback_data = json.loads(callback_data)
            except:
                callback_data = data

        order_id = callback_data.get('order_id', data.get('order_id', ''))
        unique_id = callback_data.get('unique_id', data.get('unique_id', ''))
        pay_user_id = callback_data.get('pay_user_id', data.get('pay_user_id', ''))
        amount = callback_data.get('amount', data.get('amount', ''))
        coin = callback_data.get('coin', data.get('coin', ''))

        logging.info(f"支付成功 - 订单: {order_id}, unique_id: {unique_id}, "
                     f"用户: {pay_user_id}, 金额: {amount} {coin}")

        # 查找本地订单并通知用户
        order = get_order(order_id)
        if order:
            chat_id = order.get('chat_id')
            user_id = order.get('user_id')
            # 更新订单状态
            orders = load_all_orders()
            if order_id in orders:
                orders[order_id]['status'] = 'paid'
                orders[order_id]['pay_user_id'] = pay_user_id
                orders[order_id]['amount'] = amount
                orders[order_id]['coin'] = coin
                save_all_orders(orders)

            # 通知用户
            if chat_id:
                notify_bot_via_telegram(
                    chat_id,
                    f"✅ <b>支付成功</b>\n\n"
                    f"💰 金额: {amount} {coin}\n"
                    f"📋 订单号: <code>{order_id}</code>"
                )

        # 保存通知记录
        save_notification({
            'order_id': order_id,
            'unique_id': unique_id,
            'pay_user_id': pay_user_id,
            'amount': amount,
            'coin': coin,
            'timestamp': __import__('time').time()
        })

        # 返回成功（OKPay 要求返回 status: success）
        return jsonify({'status': 'success'})

    except Exception as e:
        logging.error(f"回调处理异常: {e}", exc_info=True)
        return jsonify({'status': 'success'})


@app.route('/okpay/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'okpay_callback'})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5088, debug=False)
