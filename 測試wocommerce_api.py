import requests


def test_woocommerce_api():
    # 設定 WooCommerce API 的網址和金鑰
    api_url = "https://dudushop77.com/wp-json/wc/v3/products"
    consumer_key = "ck_13c3a730ff33adfa9744fcc7e93c7e6fad9bec87"
    consumer_secret = "cs_1eab3ed099dd34f9f65059a3d03ad4237cf81df0"

    try:
        # 發送請求
        response = requests.get(api_url, auth=(consumer_key, consumer_secret))

        # 檢查回應狀態碼
        if response.status_code == 200:
            print("成功取得產品資料：")
            products = response.json()

            # 顯示產品資訊
            for product in products:
                print(f"產品名稱: {product['name']}")
                print(f"價格: {product['price']}")
                print(f"描述: {product['description']}")
                print(f"網址: {product['permalink']}")

                # 顯示尺寸、顏色和庫存資訊
                if 'attributes' in product:
                    for attribute in product['attributes']:
                        print(f"{attribute['name']}: {', '.join(attribute['options'])}")

                if 'stock_quantity' in product:
                    print(f"庫存: {product['stock_quantity']}")

                print("-" * 30)
        else:
            print(f"API 請求失敗，狀態碼：{response.status_code}")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print("發生錯誤：", e)

if __name__ == "__main__":
    test_woocommerce_api()
