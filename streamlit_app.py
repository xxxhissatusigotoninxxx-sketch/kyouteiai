import os
import json
import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components

# predict.py から必要な関数や定数をインポート
from predict import run_prediction_flow, STADIUM_MAP

# ページの初期設定 (プレミアム感のあるダークテーマを想定)
st.set_page_config(
    page_title="🚤 AI競艇予想＆最適資金配分シミュレータ",
    page_icon="🚤",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# カスタムCSSでさらにプレミアムな雰囲気に調整
st.markdown("""
    <style>
    .main {
        background-color: #070913;
        color: #f1f5f9;
    }
    div[data-testid="stSidebar"] {
        background-color: #0f1322;
    }
    div[data-testid="stHeader"] {
        background-color: rgba(7, 9, 19, 0.8);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .stButton>button {
        background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
        color: white;
        border: none;
        padding: 0.6rem 2rem;
        border-radius: 8px;
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
        transition: all 0.3s;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
        background: linear-gradient(135deg, #4f46e5 0%, #0891b2 100%);
        color: white;
    }
    .stDownloadButton>button {
        background-color: rgba(255, 255, 255, 0.03) !important;
        color: #06b6d4 !important;
        border: 1px solid rgba(6, 182, 212, 0.3) !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton>button:hover {
        background-color: rgba(6, 182, 212, 0.1) !important;
        border-color: #06b6d4 !important;
        color: #22d3ee !important;
    }
    </style>
""", unsafe_allow_html=True)

# タイトル表示
st.title("🚤 AI競艇予想＆最適資金配分シミュレータ Web")
st.markdown("サーバー上で最新データをリアルタイム取得してAI解析し、ブラウザ内で資金配分をインタラクティブに再計算します。")

# 入力フォームエリア
st.markdown("---")
col1, col2, col3, col4 = st.columns([2, 1, 1.5, 1.5])

with col1:
    stadium_options = {v: k for k, v in STADIUM_MAP.items()}
    selected_stadium_name = st.selectbox(
        "開催場を選択",
        options=sorted(stadium_options.keys()),
        index=sorted(stadium_options.keys()).index("大村") if "大村" in stadium_options else 0
    )
    jcd = stadium_options[selected_stadium_name]
    
with col2:
    rno = st.number_input("レース番号 (R)", min_value=1, max_value=12, value=1, step=1)
    
with col3:
    budget = st.number_input("総賭け金 (円)", min_value=100, value=3100, step=100)
    
with col4:
    date_picker = st.date_input("対象日", datetime.today())
    date_str = date_picker.strftime("%Y%m%d")

st.markdown("---")

# 実行ボタン
if st.button("🚀 AI予想＆シミュレータを実行"):
    with st.spinner("最新データを公式サイトから取得中（出走表・オッズ・直前情報・コース入着率）..."):
        try:
            # 予測フローを実行
            data = run_prediction_flow(jcd, rno, budget, date_str)
            
            # HTMLテンプレートを読み込み、データを注入してHTML文字列を構築
            base_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(base_dir, "report_template.html")
            
            if not os.path.exists(template_path):
                st.error(f"エラー: テンプレートファイル '{template_path}' が見つかりません。")
            else:
                with open(template_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                
                data_json = json.dumps(data, ensure_ascii=False)
                html_content = html_content.replace("const DATA_PLACEHOLDER = null;", f"const DATA_PLACEHOLDER = {data_json};")
                
                st.success(f"🎉 {selected_stadium_name} {rno}R の解析が完了しました！")
                
                # ダウンロードボタンの設置
                st.download_button(
                    label="💾 ローカル保存用予想レポートHTMLをダウンロード",
                    data=html_content,
                    file_name=f"kyotei_ai_report_{jcd}_{rno}_{date_str}.html",
                    mime="text/html",
                )
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # iframe 埋め込み
                components.html(html_content, height=1350, scrolling=True)
                
        except Exception as e:
            st.error(f"❌ 処理中にエラーが発生しました: {str(e)}")
            st.info("※オッズがまだ公開されていないか、対象レースのデータが公式サイトにない可能性があります。深夜・早朝の場合は過去日付（昨日の日付など）を指定してお試しください。")
