import streamlit as st

# --- CSS: 불렛 없애고, 글자 크기 키우기 ---
st.markdown("""
    <style>
    .sidebar-menu a {
        display: block;
        font-size: 20px; /* 글자 크기 */
        text-decoration: none;
        padding: 8px 4px;
    }
    .sidebar-menu a:hover {
        font-weight: bold;
        color: #FF4B4B; /* hover 시 색 */
    }
    </style>
""", unsafe_allow_html=True)

# --- 사이드바 메뉴 ---
st.sidebar.markdown("## 메뉴")
menu_items = {
    "📅 스케줄": "schedule",
    "✍️ 세션": "session",
    "👥 멤버": "member",
    "📋 리포트": "report",
    "🍒": "cherry"
}

# 상태 저장
if "page" not in st.session_state:
    st.session_state.page = "schedule"

# 메뉴 출력
for label, key in menu_items.items():
    if st.sidebar.button(label, key=key):
        st.session_state.page = key

# 선택된 페이지 보여주기
if st.session_state.page == "schedule":
    st.title("📅 스케줄")
elif st.session_state.page == "session":
    st.title("✍️ 세션")
elif st.session_state.page == "member":
    st.title("👥 멤버")
elif st.session_state.page == "report":
    st.title("📋 리포트")
elif st.session_state.page == "cherry":
    st.title("🍒 수입 관리")
