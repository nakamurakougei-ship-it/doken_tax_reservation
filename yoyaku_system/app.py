import streamlit as st
import datetime
import urllib.parse

# --- 1. 定数とクラスの定義 ---
TIME_SLOTS = ["09:30 - 10:20", "10:20 - 11:10", "11:10 - 12:00", "13:00 - 13:50", "13:50 - 14:40", "14:40 - 15:30", "15:30 - 16:20", "16:20 - 17:10"]
MAX_RES_PER_DAY = 72
ALLOWED_DATES = [datetime.date(2026, 2, 15), datetime.date(2026, 2, 16), datetime.date(2026, 2, 17)]

class Reservation:
    def __init__(self, name, branch, group_id, tax_type, invoice, tax_method, skill, date, time, staff_id):
        self.name, self.branch, self.group_id = name, branch, group_id
        self.tax_type, self.invoice, self.tax_method = tax_type, invoice, tax_method
        self.skill, self.date, self.time, self.staff_id = skill, date, time, staff_id

# --- 2. データの保管場所 ---
if 'reservations' not in st.session_state: st.session_state['reservations'] = []
if 'last_res' not in st.session_state: st.session_state['last_res'] = None

# --- 3. UIの設定（ライトモードに固定するための工夫） ---
st.set_page_config(page_title="予約システム", layout="centered")

st.markdown("""
    <style>
    /* 全体の背景と文字色を強制指定（ダークモード対策） */
    .main { background-color: #ffffff !important; color: #333333 !important; }
    h1, h2, h3, p, span, label { color: #333333 !important; }
    
    .stButton>button { width: 100%; background-color: #4E7B4F; color: white !important; height: 3.5em; border-radius: 10px; font-weight: bold; }
    
    /* 控え用ボックス：文字色を黒に固定 */
    .receipt-box { 
        padding: 20px; 
        border: 2px solid #4E7B4F; 
        border-radius: 10px; 
        background-color: #f9f9f9 !important; 
        color: #333333 !important; 
        margin-bottom: 20px; 
    }
    
    /* 各種ボタンの共通スタイル */
    .custom-link-btn {
        display: flex; align-items: center; justify-content: center;
        text-decoration: none !important; width: 100%; height: 56px;
        color: white !important; font-size: 16px; font-weight: bold;
        border-radius: 10px; margin-bottom: 12px;
    }
    div.stDownloadButton > button {
        width: 100% !important; height: 56px !important;
        background-color: #4E7B4F !important; color: white !important;
        margin-bottom: 12px !important; border-radius: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 完了画面
# --- 修正後の予約完了画面（アニメーションなし・安定重視） ---
if st.session_state['last_res']:
    res = st.session_state['last_res']
    
    # --- ダークモードを力技で「ライトモード」に反転させる魔法 ---
    st.markdown("""
        <style>
        /* Streamlitのシステム変数を直接白と黒に固定します */
        :root {
            --primary-color: #4E7B4F;
            --background-color: #ffffff;
            --secondary-background-color: #f0f4f0;
            --text-color: #111111;
            --font: sans-serif;
        }
        /* ダークモード設定が効いている場合でも強制的に白背景にします */
        [data-theme="dark"] {
            --background-color: #ffffff;
            --secondary-background-color: #f0f4f0;
            --text-color: #111111;
        }
        /* 画面全体の暗転（オーバーレイ）を強制解除 */
        .stApp {
            background-color: white !important;
        }
        /* 予約控えの枠内が絶対に見えるように指定 */
        .receipt-box { 
            background-color: #f9f9f9 !important; 
            color: #111111 !important;
            border: 2px solid #4E7B4F !important;
            padding: 20px;
            border-radius: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("✅ 予約を受け付けました")
    # ...以下、save_textの作成やボタンの表示へ続く
    
    # 65行目付近：カッコ()を使った管理しやすい書き方
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
    st.markdown(f'<div class="receipt-box">{display_html}</div>', unsafe_allow_html=True)

    # --- 送信用リンク（PC・スマホ両対応の公式プラグイン形式） ---
    encoded_text = urllib.parse.quote(save_text)
    # PCでもスマホでも動作が最も安定しているURL
    line_url = f"https://social-plugins.line.me/lineit/share?text={encoded_text}"
    mail_url = f"mailto:?subject={urllib.parse.quote('予約控え')}&body={encoded_text}"
    bom_save_text = "\ufeff" + save_text

    st.subheader("💾 控えを保存・共有する")
    st.download_button("ファイルとして保存", data=bom_save_text, file_name=f"yoyaku_{res.name}.txt")
    
    # LINEボタン（PCならログイン画面へ、スマホならアプリへ）
    st.markdown(f'<a href="{line_url}" target="_blank" rel="noopener noreferrer" class="custom-link-btn" style="background-color: #06C755;">LINEで送る</a>', unsafe_allow_html=True)
    st.markdown(f'<a href="{mail_url}" class="custom-link-btn" style="background-color: #4A90E2;">メールで送る</a>', unsafe_allow_html=True)

    st.divider()
    if st.button("トップに戻る"):
        st.session_state['last_res'] = None
        st.rerun()
    
    st.stop()

# --- 通常の入力画面 ---
st.title("確定申告学習会 予約フォーム")

# 4. 日付の選択
st.subheader("1. 予約日の選択")
selected_date = st.date_input("日付を選択", value=ALLOWED_DATES[0], min_value=min(ALLOWED_DATES), max_value=max(ALLOWED_DATES))
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

# 5. 組合員情報の入力
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
            new_res = Reservation(name, branch, group_id, tax_type, invoice, tax_method, skill_level, selected_date, assigned_time, assigned_staff_id)
            st.session_state['reservations'].append(new_res)
            st.session_state['last_res'] = new_res
            st.rerun()