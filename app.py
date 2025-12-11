from flask import Flask, request, abort
import requests
import os
from dotenv import load_dotenv
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    TemplateMessage,
    ImageCarouselColumn,
    ImageCarouselTemplate,
    URIAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent
)

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# 從環境變數讀取 LINE Bot 設定
configuration = Configuration(access_token=os.environ.get('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET'))

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
        products = get_products_from_woocommerce()
        if products:
            messages = []
            for product in products[:5]:  # 回覆前5個產品
                messages.append(TextMessage(
                    text=f"產品名稱: {product['name']}\n價格: {product['price']}\n網址: {product['permalink']}"
                ))

            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                ))
        else:
            reply_message(event.reply_token, "無法取得產品資料，請稍後再試。")
    else:
        reply_message(event.reply_token, "請輸入 '社群' 或 '最新產品' 以獲取相關資訊。")

def get_products_from_woocommerce():
    api_url = "https://dudushop77.com/wp-json/wc/v3/products"
    consumer_key = os.environ.get('WOOCOMMERCE_CONSUMER_KEY')
    consumer_secret = os.environ.get('WOOCOMMERCE_CONSUMER_SECRET')

    try:
        response = requests.get(api_url, auth=(consumer_key, consumer_secret))
        if response.status_code == 200:
            return response.json()  # 返回產品數據
    except requests.exceptions.RequestException as e:
        print("發生錯誤：", e)

    return None

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
    app.run()
