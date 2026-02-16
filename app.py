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

# --- 3. 仕様書に基づいた追加ロジック（UID・ログ） ---

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
    """操作ログを記録"""
    try:
        log_sheet = doc.worksheet("操作ログ")
        log_sheet.append_row([
            datetime.datetime.now().isoformat(),
            uid,
            action,
            status,
            message
        ])
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

# --- 4. UI/CSS設定 ---
st.set_page_config(page_title="確定申告予約システム", layout="centered")
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
        f"場所　：{res['staff_id']}\n"
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

# 1. 分会の選択
bunkai_list = [None] + list(config["bunkai_master"].keys())
selected_bunkai = st.selectbox("あなたの分会を選択", options=bunkai_list)

if selected_bunkai:
    target_date_str = config["bunkai_master"][selected_bunkai]
    st.info(f"📅 {selected_bunkai} の受付日： **{target_date_str}**")
    
    with st.form("reserve_form"):
        # 2. 情報の入力
        name = st.text_input("お名前（必須）")
        tel = st.text_input("電話番号（必須・半角数字のみ）")
        group_id = st.text_input("群番号")
        
        # 申告区分
        tax_type = st.radio("申告区分", ["白色申告", "青色申告（電話予約のみ）"], horizontal=True)
        
        # インボイス
        st.write("**インボイス**")
        has_invoice = st.radio("インボイスの登録はありますか？", ["なし", "あり"], horizontal=True, label_visibility="collapsed")
        
        taxation_method = "-"
        if has_invoice == "あり":
            taxation_method = st.selectbox("課税方式を選択してください", ["本則課税", "簡易課税"])
            invoice_status = f"あり（{taxation_method}）"
        else:
            invoice_status = "なし"
            
        # 経験（確定申告は初めて？）
        st.write("**確定申告は初めて？**")
        is_first_time = st.radio("今回が初めての確定申告ですか？", ["はい", "いいえ"], horizontal=True, label_visibility="collapsed")
        
        st.write("---")
        st.write("上記の内容で間違いなければ、「予約を確定する」を押してください。")
        submit = st.form_submit_button("予約を確定する")
        
        if submit:
            if not name or not tel:
                st.warning("お名前と電話番号は必須入力です。")
            elif "青色" in tax_type:
                st.error("青色申告は電話でお申し込みください。")
            else:
                with st.spinner('予約を処理中...'):
                    final_time, final_staff = get_next_available_slot(branch_doc, target_date_str)
                    
                    if final_time:
                        uid = get_or_create_uid(branch_doc, name, tel, selected_bunkai)
                        
                        # 予約台帳へ書き込み（備考1にインボイス、備考2に初めてフラグを格納）
                        new_row = [
                            f"{target_date_str} {final_time}", # A: 日時＋枠
                            name,                             # B: 氏名
                            selected_bunkai,                  # C: 分会
                            group_id,                         # D: 群番号
                            tel,                              # E: 電話番号
                            tax_type,                         # F: 申告区分
                            invoice_status,                   # G: 備考1（インボイス）
                            f"初めて:{is_first_time}",          # H: 備考2（経験）
                            "-",                              # I: 備考3
                            f"{final_staff}番デスク",          # J: デスク番号
                            uid                               # K: UID
                        ]
                        branch_doc.worksheet("予約台帳").append_row(new_row)
                        
                        write_action_log(branch_doc, uid, "RESERVE_CREATE", "SUCCESS", f"Slot: {final_time}")
                        
                        st.session_state['last_res'] = {
                            "uid": uid, "name": name, "bunkai": selected_bunkai, 
                            "date": target_date_str, "time": final_time, "staff_id": f"{final_staff}番デスク"
                        }
                        st.rerun()
                    else:
                        st.error("申し訳ありません。満員となりました。")
                        write_action_log(branch_doc, "GUEST", "RESERVE_CREATE", "FAILED", "Full capacity")
