import os
import time
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 設定 Chrome Driver (Colab 專用的無頭模式設定)
def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # 使用新的無頭模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu') # 禁用 GPU 硬體加速
    options.add_argument('--window-size=1920,1080') # 設定視窗大小
    options.add_argument('--disable-extensions') # 禁用瀏覽器擴充功能
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    # 使用 ChromeDriverManager 自動下載並設置正確版本的 ChromeDriver
    return webdriver.Chrome(service=webdriver.ChromeService(ChromeDriverManager().install()), options=options)

# 定義爬蟲與資料處理的核心函數
def fetch_and_process(station_code, url):
    print(f"[{datetime.now()}] 正在處理站點: {station_code} ...")
    driver = get_driver()
    
    try:
        driver.get(url)
        # 等待網頁表格渲染，稍微加長等待時間確保資料完整
        time.sleep(30) 
        
        # 取得網頁內容
        page_content = driver.find_element(By.TAG_NAME, "body").text
        raw_data_list = page_content.split('\n')
        
        # 用來存放所有處理好的資料列
        all_processed_rows = []
        
        # 建立時間格式的正則表達式 (6位數字+Z)
        time_pattern = re.compile(r'\d{6}Z')

        print(f"找到網頁總行數: {len(raw_data_list)}，開始篩選...")

        for line in raw_data_list:
            # 1. 篩選邏輯：必須包含 站點名稱 AND 時間戳記
            if station_code in line and time_pattern.search(line):
                # 排除標題列 (例如包含 '24Hrs' 或 'Station' 的行)
                if "24Hrs" in line or "JSession" in line:
                    continue
                
                # --- 資料處理邏輯 (對每一行都做一次) ---
                current_line = line
                
                # (a) 捨棄 COR 與 RMK
                current_line = current_line.replace("COR ", "")
                current_line = current_line.replace("RMK ", "")
                
                # (b) 捨棄末尾符號 =
                current_line = current_line.replace("=", "")
                
                # (c) 切割欄位
                tokens = re.split(r'[ /]+', current_line.strip())
                tokens = [t for t in tokens if t] # 去除空字串

                row_data = []
                cloud_layer_start_index = -1
                
                for i, token in enumerate(tokens):
                    # (c) 第4個欄位 (Index 3) 拆分風向風速
                    if i == 3 and len(token) > 3 and token[:3].isdigit():
                        part1 = token[:3]
                        part2 = token[3:]
                        row_data.append(part1)
                        row_data.append(part2)
                    
                    # (d) 雲層合併 (FEW/SCT/BKN/OVC)
                    elif re.match(r'^(FEW|SCT|BKN|OVC)', token):
                        if cloud_layer_start_index == -1:
                            cloud_layer_start_index = len(row_data)
                            row_data.append(token)
                        else:
                            # 確保 cloud_layer_start_index 在範圍內
                            if cloud_layer_start_index < len(row_data):
                                row_data[cloud_layer_start_index] += f" {token}"
                            else:
                                row_data.append(token)
                    else:
                        row_data.append(token)
                
                # 將處理好的一列加入總表
                if row_data:
                    all_processed_rows.append(row_data)

        # 檢查是否有抓到資料
        if not all_processed_rows:
            print(f"⚠️ 在 {station_code} 未找到任何有效資料列。")
            return

        # 轉成 DataFrame
        df = pd.DataFrame(all_processed_rows)
        
        # 檔名設定
        now_str = datetime.now().strftime("%y%m%d_%H%M")
        filename = f"{now_str}_{station_code}.csv"
        
        # 存檔
        df.to_csv(filename, index=False, header=False, encoding='utf-8-sig')
        print(f"✅ 成功擷取 {len(all_processed_rows)} 筆資料，已存檔: {filename}")
        # 顯示前3筆讓使用者確認
        print("前 3 筆資料預覽:")
        print(df.head(3))

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        driver.quit()

# 主程式迴圈
def main_loop():
    sites = [
        ("RCKU", "https://aiss.anws.gov.tw/aes/ext/wfis/index.html;jsessionid=CF52B50A47A2353C7DD92FC2CFE7532A#/seqmetar?station=RCKU")
    ]

    print("\n=== 開始執行新一輪爬蟲任務 ===")
    for station, url in sites:
      fetch_and_process(station, url)

# 開始執行
if __name__ == "__main__":
    main_loop()
