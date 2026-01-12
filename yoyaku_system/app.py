import streamlit as st
import datetime
import urllib.parse

# --- 1. 定数とクラスの定義 ---
TIME_SLOTS = [
    "09:30 - 10:20", "10:20 - 11:10", "11:10 - 12:00",
    "13:00 - 13:50", "13:50 - 14:40", "14:40 - 15:30",
    "15:30 - 16:20", "16:20 - 17:10"
]
MAX_RES_PER_DAY = 72

ALLOWED_DATES = [
    datetime.date(2026, 2, 15),
    datetime.date(2026, 2, 16),
    datetime.date(2026, 2, 17)
]

class Reservation:
    def __init__(self, name, branch, group_id, tax_type, invoice, tax_method, skill, date, time, staff_id):
        self.name = name
        self.branch = branch
        self.group_id = group_id
        self.tax_type = tax_type
        self.invoice = invoice
        self.tax_method = tax_method
        self.skill = skill
        self.date = date
        self.time = time
        self.staff_id = staff_id

# --- 2. データの保管場所 ---
if 'reservations' not in st.session_state:
    st.session_state['reservations'] = []
if 'last_res' not in st.session_state:
    st.session_state['last_res'] = None

# --- 3. UIの設定 ---
st.set_page_config(page_title="予約システム", layout="centered")

st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #4E7B4F; color: white; height: 3.5em; border-radius: 10px; font-weight: bold; }
    .status-badge { padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 20px; color: white; }
    .receipt-box { padding: 20px; border: 2px solid #4E7B4F; border-radius: 10px; background-color: #f9f9f9; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 予約完了画面エリア ---

# --- 修正後の予約完了画面（デザインと送信機能の改善版） ---
if st.session_state['last_res']:
    res = st.session_state['last_res']
    st.balloons()
    st.title("🎉 予約が完了しました")
    
    # 1. 保存・送信用のテキスト
    save_text = f"""確定申告学習会 予約控え
---------------------------------
お名前　　：{res.name} 様
所属分会　：{res.branch} ({res.group_id}群)
予約日時　：{res.date.strftime('%Y/%m/%d')} {res.time}
ご案内場所：{res.staff_id}番デスク
---------------------------------"""

    # 2. 表示用のHTML
    display_html = save_text.replace('\n', '<br>')
    st.markdown(f'<div class="receipt-box">{display_html}</div>', unsafe_allow_html=True)

    # --- 3. 送信用データの準備 ---
    encoded_text = urllib.parse.quote(save_text)
    
    # LINEの最も安定したシェア用URL
    line_url = f"https://social-plugins.line.me/lineit/share?text={encoded_text}"
    mail_subject = urllib.parse.quote("確定申告学習会の予約控え")
    mail_url = f"mailto:?subject={mail_subject}&body={encoded_text}"

    # --- 4. CSSでサイズを「ミリ単位」で揃える ---
    st.markdown("""
        <style>
        /* 1. ファイル保存ボタン（Streamlit標準）を強制的に書き換え */
        div.stDownloadButton > button {
            width: 100% !important;
            height: 56px !important; /* 高さを56ピクセルで固定 */
            margin-bottom: 12px !important;
            background-color: #4E7B4F !important;
            color: white !important;
            border: none !important;
            font-size: 16px !important;
            font-weight: bold !important;
            border-radius: 10px !important;
        }

        /* 2. LINE・メールボタン（HTML）も同じ高さにする */
        .custom-link-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            text-decoration: none !important;
            width: 100%;
            height: 56px; /* Streamlitボタンと完全に一致させる */
            color: white !important;
            font-size: 16px;
            font-weight: bold;
            border-radius: 10px;
            margin-bottom: 12px;
            box-sizing: border-box; /* 枠線を含めた計算にする */
        }
        </style>
    """, unsafe_allow_html=True)

    # --- 5. ボタンの配置（縦並び） ---
    st.subheader("💾 控えを保存・共有する")

    # ファイル保存
    st.download_button("ファイルとして保存", data=save_text, file_name=f"yoyaku_{res.name}.txt")

    # LINEで送る
    st.markdown(f'<a href="{line_url}" target="_blank" rel="noopener noreferrer" class="custom-link-btn" style="background-color: #06C755;">LINEで送る</a>', unsafe_allow_html=True)

    # メールで送る
    st.markdown(f'<a href="{mail_url}" class="custom-link-btn" style="background-color: #4A90E2;">メールで送る</a>', unsafe_allow_html=True)

    st.divider()
    if st.button("トップに戻る"):
        st.session_state['last_res'] = None
        st.rerun()
    st.stop()

# --- 通常の入力画面 ---
st.title("確定申告学習会 予約フォーム")

# --- 4. 日付の選択と「ご案内予定時間」の表示 ---
st.subheader("1. 予約日の選択")
selected_date = st.date_input("カレンダーから日付を選んでください", value=ALLOWED_DATES[0], min_value=min(ALLOWED_DATES), max_value=max(ALLOWED_DATES))

current_date_res = [r for r in st.session_state['reservations'] if r.date == selected_date]
current_count = len(current_date_res)

is_date_allowed = selected_date in ALLOWED_DATES
is_full = current_count >= MAX_RES_PER_DAY

# 変数の初期化（エラー防止）
assigned_time = ""
assigned_staff_id = 0

if not is_date_allowed:
    st.markdown('<div class="status-badge" style="background-color: #757575;">設定のない日付です（予約不可）</div>', unsafe_allow_html=True)
    can_reserve_date = False
elif is_full:
    st.markdown(f'<div class="status-badge" style="background-color: #D32F2F;">{selected_date.strftime("%m/%d")} は満員です</div>', unsafe_allow_html=True)
    can_reserve_date = False
else:
    remaining = MAX_RES_PER_DAY - current_count
    st.markdown(f'<div class="status-badge" style="background-color: #4E7B4F;">{selected_date.strftime("%m/%d")} は予約可能です（残り {remaining} 名）</div>', unsafe_allow_html=True)
    can_reserve_date = True

    # --- ここで案内時間を計算して表示 ---
    assigned_staff_id = (current_count // 8) + 1
    slot_idx = current_count % 8
    assigned_time = TIME_SLOTS[slot_idx]
    st.info(f"現在受付中の予約枠：**{assigned_time}** （{assigned_staff_id}番デスク）")

# --- 5. 組合員情報の入力 ---
st.divider()
st.subheader("2. 組合員情報の入力")
name = st.text_input("お名前（必須）")
branch = st.selectbox("分会名", ["福生1分会", "あきる野1分会", "羽村1分会", "青梅１分会", "瑞穂1分会", "奥多摩", "日の出", "桧原", "山梨"], index=None)
group_id = st.text_input("群番号")

tax_type = st.radio("申告区分", ["白色申告", "青色申告"], horizontal=True)

# 予約可否の最終判定
can_submit = True
if tax_type == "青色申告":
    st.error("⚠️ 青色申告は電話でお申し込みください。")
    can_submit = False
elif not can_reserve_date:
    st.error("⚠️ 選択された日付では予約できません。")
    can_submit = False

invoice = st.radio("インボイス登録", ["なし", "あり"], horizontal=True)
tax_method = st.selectbox("課税方式", ["本則課税", "簡易課税"]) if invoice == "あり" else "なし"
skill_level = st.radio("確定申告の経験", ["初心者", "経験者"], horizontal=True)

# --- 6. 予約の確定 ---
st.divider()
if can_submit:
    # 案内時間はすでに上で表示・計算済み
    if st.button("この内容で予約を確定する"):
        if not name or not branch:
            st.warning("お名前と分会名を入力してください。")
        else:
            # 1. 中身（家具）を作って、new_res という名前をつける
            new_res = Reservation(
                name, branch, group_id, tax_type, invoice, 
                tax_method, skill_level, selected_date, 
                assigned_time, assigned_staff_id
            )
            
            # 2. 全体の予約リスト（倉庫）に保管する
            st.session_state['reservations'].append(new_res)
            
            # 3. 「最後に予約した人」として控え表示用に保存する
            st.session_state['last_res'] = new_res
            
            # 4. 画面を更新して「控え画面」に切り替える
            st.rerun()