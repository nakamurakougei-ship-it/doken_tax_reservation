import streamlit as st
import datetime
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials
import time

# --- 1. 定数・基本設定 ---
TIME_SLOTS = ["09:30 - 10:20", "10:20 - 11:10", "11:10 - 12:00", "13:00 - 13:50", "13:50 - 14:40", "14:40 - 15:30", "15:30 - 16:20", "16:20 - 17:10"]

# --- 2. Googleスプレッドシート接続用関数 ---
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    conf = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(conf, scopes=scope)
    return gspread.authorize(credentials)

def get_branch_sheet():
    query_params = st.query_params
    branch_id = query_params.get("id")
    if not branch_id:
        st.error("支部IDが指定されていません。")
        st.stop()
    try:
        sheet_id = st.secrets["branches"][branch_id]
        client = get_gspread_client()
        return client.open_by_key(sheet_id)
    except Exception as e:
        st.error(f"データの接続に失敗しました。")
        st.stop()

# --- 3. 共通ロジック ---
def get_or_create_uid(doc, name, tel, bunkai):
    """電話番号をキーにUIDを取得、なければ新規発行して名簿に登録"""
    master_sheet = doc.worksheet("利用者名簿")
    records = master_sheet.get_all_values()
    # 既存チェック（電話番号は5列目：インデックス4）
    for row in records[1:]:
        if len(row) > 4 and row[4] == tel:
            return row[0]
    # 新規発行
    new_uid = f"U{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
    master_sheet.append_row([new_uid, name, bunkai, "-", tel, datetime.datetime.now().isoformat()])
    return new_uid

def write_action_log(doc, uid, action, status, message=""):
    try:
        log_sheet = doc.worksheet("操作ログ")
        log_sheet.append_row([datetime.datetime.now().isoformat(), uid, action, status, message])
    except:
        pass

@st.cache_data(ttl=600)
def load_master_config(branch_id):
    doc = get_branch_sheet()
    config_sheet = doc.worksheet("設定")
    records = config_sheet.get_all_records()
    if not records:
        st.error("設定データが空です。")
        st.stop()
    branch_name = records[0].get("支部名", "建設労働組合")
    dify_url = records[0].get("DifyURL", "")
    bunkai_master = {r["分会名"]: r["受付日"] for r in records if r["分会名"]}
    return {"branch_name": branch_name, "dify_url": dify_url, "bunkai_master": bunkai_master}

def get_next_available_slot(doc, target_date_str):
    sheet = doc.worksheet("予約台帳")
    all_records = sheet.get_all_values()[1:]
    occupied_slots = set()
    for row in all_records:
        if len(row) >= 10:
            occupied_slots.add((row[0], row[9]))
    for s_id in range(1, 11): 
        staff_str = f"{s_id}番デスク"
        for t_str in TIME_SLOTS:
            dt_key = f"{target_date_str} {t_str}"
            if (dt_key, staff_str) not in occupied_slots:
                return t_str, s_id
    return None, None

# --- 4. UI設定 ---
st.set_page_config(page_title="確定申告予約システム", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: white; }
    .receipt-box { 
        padding: 20px; border: 2px solid #4E7B4F; border-radius: 10px; 
        background-color: #f9f9f9; color: #333; margin-bottom: 20px; 
    }
    div.stButton > button {
        width: 100%; height: 3.5em; background-color: #4E7