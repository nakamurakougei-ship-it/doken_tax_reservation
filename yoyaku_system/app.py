import streamlit as st
import datetime
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials

# --- 1. Googleスプレッドシートへの接続関数 ---
def append_to_gsheet(data_list):
    try:
        # Secretsから認証情報を取得
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        conf = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(conf, scopes=scope)
        client = gspread.authorize(credentials)
        
        # スプレッドシートを開く
        sheet_id = st.secrets["spreadsheet"]["id"]
        sheet = client.open_by_key(sheet_id).sheet1
        
        # データを末尾に追加
        sheet.append_row(data_list)
        return True
    except Exception as e:
        st.error(f"スプレッドシートへの保存に失敗しました: {e}")
        return False

# --- 定数とクラスの定義（ここからは以前と同じ） ---
TIME_SLOTS = ["09:30 - 10:20", "10:20 - 11:10", "11:10 - 12:00", "13:00 - 13:50", "13:50 - 14:40", "14:40 - 15:30", "15:30 - 16:20", "16:20 - 17:10"]
MAX_RES_PER_DAY = 72
ALLOWED_DATES = [datetime.date(2026, 2, 15), datetime.date(2026, 2, 16), datetime.date(2026, 2, 17)]

class Reservation:
    def __init__(self, name, branch, group_id, tax_type, invoice, tax_method, skill, date, time, staff_id):
        self.name, self.branch, self.group_id = name, branch, group_id
        self.tax_type, self.invoice, self.tax_method = tax_type, invoice, tax_method
        self.skill, self.date, self.time, self.staff_id = skill, date, time, staff_id

if 'reservations' not in st.session_state: st.session_state['reservations'] = []
if 'last_res' not in st.session_state: st.session_state['last_res'] = None

st.set_page_config(page_title="予約システム", layout="centered")

# CSS設定（前回と同じ）
st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #4E7B4F; color: white !important; height: 3.5em; border-radius: 10px; font-weight: bold; border: none; }
    .receipt-box { padding: 20px; border: 2px solid #4E7B4F; border-radius: 10px; background-color: #f9f9f9; color: #333333; margin-bottom: 20px; font-family: sans-serif; }
    .custom-link-btn { display: flex; align-items: center; justify-content: center; text-decoration: none !important; width: 100%; height: 56px; color: white !important; font-size: 16px; font-weight: bold; border-radius: 10px; margin-bottom: 12px; }
    div.stDownloadButton > button { width: 100% !important; height: 56px !important; background-color: #4E7B4F !important; color: white !important; margin-bottom: 12px !important; border-radius: 10px !important; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 予約完了画面 ---
if st.session_state['last_res']:
    res = st.session_state['last_res']
    st.title("✅ 予約を受け付けました")
    
    save_text = (
        f"確定申告学習会 予約控え\n"
        f"---------------------------------\n"
        f"お名前　　：{res.name} 様\n"
        f"所属分会　：{res.branch} ({res.group_id}群)\n"
        f"予約日時　：{res.date.strftime('%Y/%m/%d')} {res.time}\n"
        f"ご案内場所：{res.staff_id}番デスク\n"
        f"---------------------------------"
    )
    display_html = save_text.replace('\n', '<br>')
    st.markdown(f'<div class="receipt-box" style="color: #333333;">{display_html}</div>', unsafe_allow_html=True)

    encoded_text = urllib.parse.quote(save_text)
    line_url = f"https://line.me/R/share?text={encoded_text}"
    mail_url = f"mailto:?subject={urllib.parse.quote('予約控え')}&body={encoded_text}"
    bom_save_text = "\ufeff" + save_text

    st.subheader("💾 控えを保存・共有する")
    st.download_button("ファイルとして保存", data=bom_save_text, file_name=f"yoyaku_{res.name}.txt")
    st.markdown(f'<a href="{line_url}" target="_blank" rel="noopener noreferrer" class="custom-link-btn" style="background-color: #06C755;">LINEで送る</a>', unsafe_allow_html=True)
    st.markdown(f'<a href="{mail_url}" class="custom-link-btn" style="background-color: #4A90E2;">メールで送る</a>', unsafe_allow_html=True)

    st.divider()
    if st.button("トップに戻る"):
        st.session_state['last_res'] = None
        st.rerun()
    st.stop()

# --- 入力画面 ---
st.title("確定申告学習会 予約フォーム")

st.subheader("1. 予約日の選択")
selected_date = st.date_input("日付を選択", value=ALLOWED_DATES[0], min_value=min(ALLOWED_DATES), max_value=max(ALLOWED_DATES))
# 本来はここでスプレッドシートから現在の予約数を数えるべきですが、一旦はセッション内のみでカウントします
current_date_res = [r for r in st.session_state['reservations'] if r.date == selected_date]
current_count = len(current_date_res)

can_reserve_date = False
if selected_date not in ALLOWED_DATES:
    st.error("予約設定がない日付です")
elif current_count >= MAX_RES_PER_DAY:
    st.error("満員です")
else:
    st.success(f"予約可能です（残り {MAX_RES_PER_DAY - current_count} 名）")
    can_reserve_date = True
    assigned_staff_id = (current_count // 8) + 1
    assigned_time = TIME_SLOTS[current_count % 8]
    st.info(f"ご案内予定：**{assigned_time}** （{assigned_staff_id}番デスク）")

st.divider()
st.subheader("2. 情報の入力")
name = st.text_input("お名前（必須）")
branch = st.selectbox("分会名", ["福生1分会", "あきる野1分会", "羽村1分会", "青梅１分会", "瑞穂1分会", "奥多摩", "日の出", "桧原", "山梨"], index=None)
group_id = st.text_input("群番号")
tax_type = st.radio("申告区分", ["白色申告", "青色申告"], horizontal=True)

can_submit = can_reserve_date
if tax_type == "青色申告":
    st.warning("⚠️ 青色申告は電話でお申し込みください。")
    can_submit = False

invoice = st.radio("インボイス", ["なし", "あり"], horizontal=True)
tax_method = st.selectbox("課税方式", ["本則課税", "簡易課税"]) if invoice == "あり" else "なし"
skill_level = st.radio("経験", ["初心者", "経験者"], horizontal=True)

if can_submit:
    if st.button("予約を確定する"):
        if not name or not branch:
            st.warning("お名前と分会名を入力してください。")
        else:
            # 1. 予約オブジェクト作成
            new_res = Reservation(name, branch, group_id, tax_type, invoice, tax_method, skill_level, selected_date, assigned_time, assigned_staff_id)
            
            # 2. スプレッドシートへ書き込み（ここが新しい！）
            data_to_save = [
                f"{new_res.date} {new_res.time}",
                new_res.name,
                new_res.branch,
                new_res.group_id,
                new_res.tax_type,
                new_res.invoice,
                new_res.tax_method,
                new_res.skill,
                f"{new_res.staff_id}番デスク"
            ]
            
            if append_to_gsheet(data_to_save):
                # 保存に成功したら画面を切り替える
                st.session_state['reservations'].append(new_res)
                st.session_state['last_res'] = new_res
                st.rerun()
            else:
                st.error("申し訳ありません。予約データの保存に失敗しました。事務局へ連絡してください。")