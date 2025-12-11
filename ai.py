from flask import Flask, request, abort
from linebot.v3.exceptions import InvalidSignatureError
import requests
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, TemplateMessage, ImageCarouselColumn, ImageCarouselTemplate, URIAction
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from openai import OpenAI
from apscheduler.schedulers.background import BackgroundScheduler # type: ignore
import re
import time
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 初始化 Flask 應用
app = Flask(__name__)

# 設置 LINE Bot 的配置信息（從環境變數讀取）
configuration = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

# 設定 OpenAI API 密鑰（從環境變數讀取）
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
# 用來緩存商品資料的全域變數
cached_products = []

# 用來儲存對話紀錄的全域變數（僅保留最近 3 條對話紀錄）
MAX_HISTORY = 3
conversation_history = []

# 載入所有產品資料到快取
def load_products():
    global cached_products
    products = get_products_from_woocommerce()
    if products:
        cached_products = [extract_product_info(product) for product in products]
        app.logger.info(f"成功載入 {len(cached_products)} 件商品資料")
        print(cached_products)  # 打印 cached_products 的內容
    else:
        app.logger.warning("無法載入商品資料")

# 定義更新商品資料的函數
def update_products():
    global cached_products
    products = get_products_from_woocommerce()
    if products:
        cached_products = [extract_product_info(product) for product in products]
        app.logger.info(f"成功更新商品資料，共有 {len(cached_products)} 件商品")
        print(cached_products)  # 打印 cached_products 的內容
    else:
        app.logger.warning("無法更新商品資料")

# 定時更新商品資料
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_products, 'interval', hours=12)  # 每 12 小時更新一次
    scheduler.start()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@app.route("/check_products", methods=['GET'])
def check_products():
    if cached_products:
        return {"products": cached_products[:5]}, 200  # 回傳前5個商品資料
    else:
        return {"message": "無法取得商品資料"}, 200

@handler.add(FollowEvent)
def handle_follow(event):
    app.logger.info("New follower detected.")
    send_image_carousel(event.reply_token)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()

    if text == "社群":
        send_image_carousel(event.reply_token)
    elif text == "最新產品":
        if cached_products:
            messages = []
            for product in cached_products[:4]:
                messages.append(TextMessage(
                    text=f"商品名稱: {product['name']}\n價格: {product['price']}\n尺寸: {product['size']}\n顏色: {product['color']}\n連結: {product['link']}"
                ))
# 加入提示訊息
            messages.append(TextMessage(text="其它最新商品請至官網挑選：https://dudushop77.com"))
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                ))
        else:
            reply_message(event.reply_token, "無法取得產品資料，請稍後再試。")
    else:
        chatgpt_response = get_chatgpt_response(text)
        reply_message(event.reply_token, chatgpt_response)

def extract_product_info(product):
    try:
         # 檢查庫存狀態
        stock_quantity = product.get("stock_quantity")  # 可能為 None
        in_stock = product.get("in_stock", False)  # 預設為 False

        # 判斷庫存
        if stock_quantity is None or stock_quantity > 0:
            stock_status =  f"有庫存"
        else:
            stock_status = "無庫存"
        return {
            "name": product.get("name"),
            "price": product.get("price"),
            "size": extract_size_from_description(product.get("description", "")),
            "color": extract_color_from_description(product.get("description", "")),
            "link": product.get("permalink"),
            "stock_status": stock_status,  # 添加庫存狀態
        }
    except Exception as e:
        print(f"提取商品資料時發生錯誤: {e}")
        return None

def extract_size_from_description(description):
    match = re.search(r"尺寸：([^<]*)", description)
    return match.group(1).strip() if match else "單一尺寸"

def extract_color_from_description(description):
    match = re.search(r"顏色：([^<]*)", description)
    return match.group(1).strip() if match else "單一顏色"

def update_conversation_history(role, content):
    global conversation_history
    if len(conversation_history) >= MAX_HISTORY:
        conversation_history.pop(0)
    conversation_history.append({"role": role, "content": content})

def get_chatgpt_response(user_input):
    try:
        # 檢查是否詢問商品相關資訊
        for product in cached_products:
            if product['name'] in user_input:
                # 將商品資訊組成適合 GPT 的提示
                gpt_prompt = (
                    f"用戶提問與商品『{product['name']}』相關：\n"
                    f"- 庫存狀態：{product['stock_status']}\n"
                    f"- 價格：{product['price']} 元\n"
                    f"- 顏色：{product['color']}\n"
                    f"- 尺寸：{product['size']}\n"
                    f"- 連結：{product['link']}\n"
                    "請使用友善的語氣回答用戶的問題，請針對cached_product的資料回覆，請勿捏造，並附上商品連結，回答字數20字以內。"
                )
                
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    max_tokens=100,
                    messages=[
                        {"role": "system", "content": "你是一個友善的電商助理，幫助回答用戶的商品問題，請根據 cached_products 的內容回答用戶問題，請勿捏造，並以熱情簡短的語氣回覆。如果問題超出 cached_products 範圍，請回應：『抱歉，我無法回答這個問題，請稍後會有專人回覆您，謝謝。』。"},
                        {"role": "user", "content": gpt_prompt},
                        {"role": "user", "content": user_input}
                    ]
                )
                return response.choices[0].message.content.strip()
            
                # 如果沒有匹配商品，回到 GPT 模型進行回應
        update_conversation_history("user", user_input)
         # 如果用戶詢問推薦商品，提供官網連結
        if "推薦" in user_input or "其他商品" in user_input:
            return "感謝您的詢問！請您到我們的官網 https://dudushop77.com 上挑選更多商品，期待您的光臨！"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=100,
            messages=[
                {"role": "assistant", "content": 
                 "你是一個友善的電商助理，請根據 cached_products 的內容回答用戶問題，並以熱情簡短的語氣回覆。如果問題超出 cached_products 範圍，請回應：『抱歉，我無法回答這個問題，請稍後會有專人回覆您，謝謝。』。"},
                *conversation_history
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"ChatGPT API 錯誤: {e}")
        return "抱歉，我暫時無法處理您的問題，稍後會有專人回覆。"

def get_products_from_woocommerce():
    api_url = "https://dudushop77.com/wp-json/wc/v3/products"
    consumer_key = os.environ.get('WOOCOMMERCE_CONSUMER_KEY')
    consumer_secret = os.environ.get('WOOCOMMERCE_CONSUMER_SECRET')
    per_page = 100
    page = 1
    all_products = []

    try:
        while True:
            response = requests.get(
                api_url,
                auth=(consumer_key, consumer_secret),
                params={"per_page": per_page, "page": page}
            )
            if response.status_code == 200:
                products = response.json()
                if not products:
                    break
                all_products.extend(products)
                page += 1
            else:
                print(f"API 請求失敗，狀態碼: {response.status_code}, 回應: {response.text}")
                break
    except requests.exceptions.RequestException as e:
        print(f"API 請求錯誤: {e}")
    
    return all_products

def reply_message(reply_token, text):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=text)]
        ))

def send_image_carousel(reply_token):
    url = request.url_root + 'static'
    url = url.replace("http", "https")
    app.logger.info("Constructed URL: " + url)

    image_carousel_template = ImageCarouselTemplate(
        columns=[
            ImageCarouselColumn(
                image_url=url + '/facebook.png',
                action=URIAction(
                    label='造訪FB',
                    uri='https://www.facebook.com/profile.php?id=100066671013478'
                )
            ),
            ImageCarouselColumn(
                image_url=url + '/instagram.png',
                action=URIAction(
                    label='造訪IG',
                    uri='https://www.instagram.com/dudu_shop77/'
                )
            ),
            ImageCarouselColumn(
                image_url=url + '/dudu.png',
                action=URIAction(
                    label='造訪官網',
                    uri='https://dudushop77.com/'
                )
            ),
        ]
    )

    image_carousel_message = TemplateMessage(
        alt_text='圖片輪播',
        template=image_carousel_template
    )

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=reply_token,
            messages=[image_carousel_message]
        ))

if __name__ == "__main__":
    load_products()
    start_scheduler()
    app.run()
