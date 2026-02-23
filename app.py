import streamlit as st
import datetime
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import gspread
from google.oauth2.service_account import Credentials
import time
import requests  # GAS通信用に必要

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
    # 電話番号は5列目（インデックス4）
    for row in records[1:]:
        if len(row) > 4 and row[4] == tel:
            return row[0]
    
    new_uid = f"U{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
    # 名簿への追加もGAS経由にするのが理想だが、頻度が低いため一旦現状維持
    master_sheet.append_row([new_uid, name, bunkai, "-", tel, datetime.datetime.now().isoformat()])
    return new_uid

def write_action_log(doc, uid, action, status, message=""):
    """操作ログを記録"""
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
    """最新の空き枠を検索"""
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

def make_ics(branch_name: str, date_str: str, time_str: str, venue: str, description: str) -> str:
    """予約内容から iCalendar(.ics) 形式の文字列を生成。iPhone/Android 両対応。"""
    # time_str は "09:30 - 10:20" 形式
    parts = time_str.split("-")
    start_part = (parts[0].strip() if len(parts) > 0 else "09:30").replace(" ", "")
    end_part = (parts[1].strip() if len(parts) > 1 else "10:20").replace(" ", "")
    def hm(s):
        p = s.split(":")
        h = p[0].strip().zfill(2) if p else "09"
        m = p[1].strip().zfill(2) if len(p) > 1 else "00"
        return h, m
    start_h, start_m = hm(start_part)
    end_h, end_m = hm(end_part)
    # date_str は "2025-03-15" 形式 → 20250315
    date_compact = date_str.replace("-", "")
    dt_start = f"{date_compact}T{start_h}{start_m}00"
    dt_end = f"{date_compact}T{end_h}{end_m}00"
    summary = f"{branch_name} 確定申告学習会 予約"
    # DESCRIPTION は改行を \n で、カンマ・バックスラッシュはエスケープ
    desc_escaped = description.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//YoyakuSystem//JP\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART:{dt_start}\r\n"
        f"DTEND:{dt_end}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"LOCATION:{venue}\r\n"
        f"DESCRIPTION:{desc_escaped}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return ics

def send_reservation_email(to_addr: str, subject: str, body: str) -> bool:
    """控えメールをSMTPで送信。secrets に [smtp] が無い場合は何もしない。"""
    if "smtp" not in st.secrets:
        return False
    try:
        smtp = st.secrets["smtp"]
        host = smtp.get("host", "smtp.gmail.com")
        port = int(smtp.get("port", 587))
        user = smtp.get("user", "")
        password = smtp.get("password", "")
        from_addr = smtp.get("from_addr", user)
        if not user or not password:
            return False
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = from_addr
        msg["To"] = to_addr
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        return True
    except Exception:
        return False

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
    .custom-link-btn.mail {
        background-color: #2563eb;
    }
    .custom-link-btn.mail:hover { background-color: #1d4ed8; }
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
    st.info("画面をスクリーンショットして保存するか、以下のいずれかを利用して保存してください。")
    encoded_text = urllib.parse.quote(save_text)
    st.markdown(f'<a href="https://line.me/R/share?text={encoded_text}" class="custom-link-btn">LINEで送る</a>', unsafe_allow_html=True)
    mail_subject = urllib.parse.quote(f"【{config['branch_name']}】予約控え {res.get('uid','')}")
    mail_body = urllib.parse.quote(save_text)
    st.markdown(f'<a href="mailto:?subject={mail_subject}&body={mail_body}" class="custom-link-btn mail">メールで送る</a>', unsafe_allow_html=True)
    ics_content = make_ics(config["branch_name"], res["date"], res["time"], VENUE_NAME, save_text)
    st.download_button(
        "📅 カレンダーに追加",
        data=ics_content.encode("utf-8"),
        file_name="yoyaku.ics",
        mime="text/calendar",
        use_container_width=True,
    )
    st.caption("※ iPhone・Android でダウンロード後、ファイルを開くとカレンダーに追加できます。")
    if res.get("email_sent"):
        st.success(f"控えを {res.get('email','')} に送信しました。")

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
    tel = raw_tel.replace("-", "").replace(" ", "")
    email = st.text_input("メールアドレス（任意・控えを送る場合）", placeholder="example@email.com").strip()
   
    group_id = st.text_input("群番号")
   
    tax_type = st.radio("申告区分", ["白色申告", "青色申告（電話予約のみ）"], horizontal=True)
    if "青色" in tax_type:
        st.error("青色申告の方は、お手数ですが直接支部へお電話で予約してください。\n\n 西多摩支部：0428-22-3721")

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
            with st.spinner('予約枠を確保中...'):
                # 1. 最新の空き状況を確認
                final_time, final_staff = get_next_available_slot(branch_doc, target_date_str)
                
                if final_time:
                    uid = get_or_create_uid(branch_doc, name, tel, selected_bunkai)
                    
                    # 2. GASへ送信するデータの準備
                   
                    GAS_URL = "https://script.google.com/macros/s/AKfycbydoy0NUt60tUsQ4s1MAto29K_hbb7ePlEQtGCOE84TVxI2P4g191-RWMa5_L8QMlQ6rQ/exec"
                    
                    payload = {
                        "datetime": f"{target_date_str} {final_time}",
                        "name": name,
                        "bunkai": selected_bunkai,
                        "group_id": group_id,
                        "tel": tel,
                        "tax_type": tax_type,
                        "invoice_status": invoice_status,
                        "is_first_time": is_first_time,
                        "staff_desk": f"{final_staff}番デスク",
                        "uid": uid
                    }
                    
                    try:
                        # 3. GAS経由で書き込み（LockServiceが効く）
                        response = requests.post(GAS_URL, json=payload, timeout=15)
                        
                        if response.status_code == 200:
                            write_action_log(branch_doc, uid, "RESERVE_CREATE", "SUCCESS", f"Slot: {final_time}")
                            save_text_for_email = (
                                f"【{config['branch_name']} 予約控え】\n"
                                f"---------------------------------\n"
                                f"予約ID：{uid}\n"
                                f"お名前：{name} 様\n"
                                f"分会名：{selected_bunkai}\n"
                                f"日時　：{target_date_str} {final_time}\n"
                                f"場所　：{VENUE_NAME}\n"
                                f"---------------------------------\n"
                                f"■インボイス：{invoice_status}\n"
                                f"■確定申告：{is_first_time}\n"
                                f"---------------------------------\n"
                                f"★変更・キャンセルは以下よりお願いします\n"
                                f"{config['dify_url']}"
                            )
                            email_sent = False
                            if email and "@" in email:
                                email_sent = send_reservation_email(
                                    email,
                                    f"【{config['branch_name']}】予約控え {uid}",
                                    save_text_for_email,
                                )
                            st.session_state['last_res'] = {
                                "uid": uid, "name": name, "bunkai": selected_bunkai,
                                "date": target_date_str, "time": final_time,
                                "invoice": invoice_status, "first_time": is_first_time,
                                "email": email or None, "email_sent": email_sent,
                            }
                            st.rerun()
                        else:
                            st.error("予約の書き込みに失敗しました。時間をおいて再度お試しください。")
                    except Exception as e:
                        st.error(f"システムエラーが発生しました: {e}")
                else:
                    st.error("申し訳ありません。手続き中に他の予約が入り、満員となりました。")