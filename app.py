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
    master_sheet = doc.worksheet("利用者名簿")
    records = master_sheet.get_all_values()
    # 電話番号は5列目（インデックス4）
    for row in records[1:]:
        if len(row) > 4 and row[4] == tel:
            return row[0]
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

# --- 4. UI/CSS設定 ---
st.set_page_config(page_title="確定申告予約システム", layout="centered")
# ★ここがエラーの箇所。閉じクォーテーションを確実に配置したぞ
st.markdown("""
    <style>
    .stApp { background-color: white; }
    .receipt-box { 
        padding: 20px; border: 2px solid #4E7B4F; border-radius: 10px; 
        background-color: #f9f9f9; color: #333; margin-bottom: 20px; 
    }
    div.stButton > button {
        width: 100%; height: 3.5em; background-color: #4E7B4F; 
        color: white; font-weight: bold; border-radius: 10px;
    }
    .custom-link-btn { 
        display: flex; align-items: center; justify-content: center; 
        text-decoration: none !important; width: 100%; height: 50px; 
        color: white !important; font-size: 16px; font-weight: bold; 
        border-radius: 10px; margin-bottom: 10px; background-color: #06C755;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 5. メイン処理 ---
branch_id = st.query_params.get("id")
config = load_master_config(branch_id)
branch_doc = get_branch_sheet()
VENUE_NAME = "西多摩支部会館３階"

# 【完了画面】
if 'last_res' in st.session_state and st.session_state['last_res']:
    res = st.session_state['last_res']
    st.title(f"✅ {config['branch_name']}")
    st.subheader("予約が確定しました")
    
    save_text = (
        f"【{config['branch_name']} 予約控え】\n"
        f"---------------------------------\n"
        f"予約ID：{res['uid']}\n"
        f"お名前：{res['name']} 様\n"
        f"分会名：{res['bunkai']}\n"
        f"日時　：{res['date']} {res['time']}\n"
        f"場所　：{VENUE_NAME}\n"
        f"---------------------------------\n"
        f"■インボイス：{res['invoice']}\n"
        f"■確定申告：{res['first_time']}\n"
        f"---------------------------------\n"
        f"★変更・キャンセルは以下よりお願いします\n"
        f"{config['dify_url']}"
    )
    
    st.markdown(f'<div class="receipt-box">{save_text.replace("\n","<br>")}</div>', unsafe_allow_html=True)
    st.info("💡 画面をスクリーンショットして保存してください。")
    encoded_text = urllib.parse.quote(save_text)
    st.markdown(f'<a href="https://line.me/R/share?text={encoded_text}" class="custom-link-btn">LINEで送る</a>', unsafe_allow_html=True)
    
    if st.button("トップに戻る"):
        st.session_state['last_res'] = None
        st.rerun()
    st.stop()

# 【入力画面】
st.title(f"{config['branch_name']}")
st.subheader("確定申告学習会 予約フォーム")

bunkai_list = [None] + list(config["bunkai_master"].keys())
selected_bunkai = st.selectbox("あなたの所属分会名を教えてください", options=bunkai_list)

if selected_bunkai:
    target_date_str = config["bunkai_master"][selected_bunkai]
    st.info(f"📅 {selected_bunkai} の受付日： **{target_date_str}**")
    
    # リアルタイム反映のため、st.form は使用しない
    name = st.text_input("お名前（必須）")
    raw_tel = st.text_input("電話番号（必須・ハイフンなしで入力）")
    # 電話番号からハイフンとスペースを自動除去
    tel = raw_tel.replace("-", "").replace(" ", "")
    
    group_id = st.text_input("群番号")
    
    tax_type = st.radio("申告区分", ["白色申告", "青色申告（電話予約のみ）"], horizontal=True)
    if "青色" in tax_type:
        st.error("⚠️ 青色申告の方は、お手数ですが直接支部へお電話で予約してください。\n\n 📞 西多摩支部：0428-22-3721")

    st.write("**インボイス**")
    has_invoice = st.radio("インボイスの登録はありますか？", ["なし", "あり"], horizontal=True, label_visibility="collapsed")
    
    invoice_status = "なし"
    if has_invoice == "あり":
        tax_method = st.selectbox("課税方式を選択してください", ["本則課税", "簡易課税"])
        invoice_status = f"あり（{tax_method}）"
        
    st.write("**確定申告は初めて？**")
    first_time_val = st.radio("今回が初めての確定申告ですか？", ["はい", "いいえ"], horizontal=True, label_visibility="collapsed")
    is_first_time = "初めて" if first_time_val == "はい" else "経験あり"

    st.write("---")
    st.write("上記の内容で間違いなければ、「予約を確定する」を押してください。")
    
    if st.button("予約を確定する"):
        if not name or not tel:
            st.warning("お名前と電話番号は必須入力です。")
        elif "青色" in tax_type:
            st.error("青色申告の方は、直接支部へお電話ください。")
        elif not tel.isdigit():
            st.warning("電話番号は数字のみで入力してください。")
        else:
            with st.spinner('予約を処理中...'):
                final_time, final_staff = get_next_available_slot(branch_doc, target_date_str)
                if final_time:
                    uid = get_or_create_uid(branch_doc, name, tel, selected_bunkai)
                    new_row = [
                        f"{target_date_str} {final_time}", 
                        name, 
                        selected_bunkai, 
                        group_id, 
                        tel, # 数字のみ保存
                        tax_type, 
                        invoice_status, 
                        is_first_time, 
                        "-", 
                        f"{final_staff}番デスク", 
                        uid
                    ]
                    branch_doc.worksheet("予約台帳").append_row(new_row)
                    write_action_log(branch_doc, uid, "RESERVE_CREATE", "SUCCESS", f"Slot: {final_time}")
                    
                    st.session_state['last_res'] = {
                        "uid": uid, "name": name, "bunkai": selected_bunkai, 
                        "date": target_date_str, "time": final_time,
                        "invoice": invoice_status, "first_time": is_first_time
                    }
                    st.rerun()
                else:
                    st.error("申し訳ありません。満員となりました。")