import requests
import time
import hashlib

def generate_check_mac_value(params, hash_key, hash_iv):
    sorted_params = sorted(params.items())
    raw_string = f"HashKey={hash_key}&" + "&".join([f"{k}={v}" for k, v in sorted_params]) + f"&HashIV={hash_iv}"
    encoded_string = raw_string.encode('utf-8')
    check_mac_value = hashlib.md5(encoded_string).hexdigest().upper()
    return check_mac_value

def query_logistics_status(order_id):
    url = "https://logistics-stage.ecpay.com.tw/QueryLogisticsInfo"
    merchant_id = "3389555"
    hash_key = "GVYRwEdpjQIjmA66"
    hash_iv = "3EC4utIqqc2O3dzS"

    params = {
        'MerchantID': merchant_id,
        'AllPayLogisticsID': order_id,
        'TimeStamp': int(time.time()),
        'LogisticsSubType': 'HILIFE',  # 或者其他物流子類型，如 HILIFEUNIMART
    }
    params['CheckMacValue'] = generate_check_mac_value(params, hash_key, hash_iv)

    response = requests.post(url, data=params)
    if response.status_code == 200:
        result = response.json()
        if result.get('RtnCode') == '1':
            return f"訂單號碼：{order_id}\n物流狀態：{result['LogisticsStatus']}"
        else:
            return f"查詢失敗：{result.get('RtnMsg')}"
    else:
        return "無法與綠界系統通訊，請稍後再試。"

# 測試功能
order_id = input("請輸入訂單號碼：")
status = query_logistics_status(order_id)
print(status)