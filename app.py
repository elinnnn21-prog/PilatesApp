# app.py
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict

import pandas as pd
import streamlit as st

# ========== 기본 설정 ==========
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")
DATA_DIR = Path(".")
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
EX_JSON      = DATA_DIR / "exercise_db.json"

# 🍒 PIN (Streamlit Cloud secrets에 CHERRY_PW가 있으면 그 값 사용)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES = ["플로우", "리유", "방문"]
SITE_COLOR = {"플로우": "#d9f0ff", "리유": "#f0f0f0", "방문": "#e9fbe9"}

# ---------- 동작 기본 DB (요약본) ----------
EX_DB_DEFAULT: Dict[str, List[str]] = {
    # 이미지 자료의 큰 분류명과 대표 동작 일부. 사용 중 추가 입력하면 자동 누적 저장됩니다.
    "Mat(Basic)": [
        "Roll down","The hundred","Single leg circles","Rolling like a ball",
        "Single leg stretch","Double leg stretch","Spine stretch forward"
    ],
    "Mat(Intermediate/Advanced)": [
        "Criss cross","Open leg rocker","Saw","Neck pull","Side kick series",
        "Teaser","Swimming","Scissors","Bicycle","Jack knife"
    ],
    "Reformer": [
        "Footwork series","The hundred","Coordination","Long box - pulling straps",
        "Backstroke","Short box series","Long stretch series","Elephant",
        "Knee stretch series","Running","Pelvic lift","Side split","Front split"
    ],
    "Cadillac": [
        "Roll back","Leg spring series","Tower","Monkey",
        "Teaser w/push through bar","Arm series","Push through bar",
        "Hip circles","Shoulder bridge"
    ],
    "Wunda chair": [
        "Footwork series","Push down","Pull up","Spine stretch forward",
        "Teaser","Mountain climb","Tabletop","Front balance control"
    ],
    "Spine corrector/Barrel": [
        "Swan","Horseback","Side sit up","Ballet stretch side","Thigh stretch"
    ],
    "Electric chair": ["Pumping series","Going up front"],
    "Pedi-pull": ["Chest expansion","Arm circles","Knee bends","Centering"],
    "기타": []
}
# ===========================================

# ========== 파일/데이터 유틸 ==========
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","지점","등록일","총등록","남은횟수","메모"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","메모","취소","사유","분","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

def load_members() -> pd.DataFrame:
    return pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    # 타입 보정
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"])
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    # 날짜를 문자열로 저장
    df = df.copy()
    if not df.empty:
        df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_JSON, typ="series")
        d = {k: list(v) for k, v in raw.items()}
        # 키 누락 등 방지
        for k, v in EX_DB_DEFAULT.items():
            d.setdefault(k, v)
        return d
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_JSON, force_ascii=False)

ensure_files()

# ========== 가격 계산 ==========
def calc_pay(site: str, session_type: str, headcount: int, custom_visit_pay: float|None) -> tuple[float,float]:
    """
    returns (gross, net)
    플로우: 회당 35,000원, 3.3% 공제
    리유: 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣 35,000 (공제 없음)
    방문: 사용자 직접 입력 (gross=net=입력값)
    """
    gross = net = 0.0
    if site == "플로우":
        gross = 35000.0
        net = round(gross * 0.967, 0)  # 3.3% 공제
    elif site == "리유":
        if session_type == "개인":
            gross = net = 30000.0
        else:  # 그룹
            # headcount 기준 (요청 표)
            mapping = {3:40000.0, 2:30000.0, 1:25000.0}  # 1명=소그룹/프라이빗, 듀엣은 2명과 별개
            if headcount == 2:
                # 듀엣 별도
                gross = net = 35000.0
            else:
                gross = net = mapping.get(headcount, 30000.0)
    else:  # 방문
        gross = net = float(custom_visit_pay or 0)
    return gross, net

# ========== 공통 위젯 ==========
def big_info(msg: str, kind="info"):
    if kind == "warn":
        st.warning(msg)
    elif kind == "error":
        st.error(msg)
    else:
        st.info(msg)

def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

# ========== 네비게이션 (사이드바 / 기본 스케줄) ==========
if "nav" not in st.session_state:
    st.session_state["nav"] = "📅 스케줄"

nav = st.sidebar.radio(
    "Navigation",
    ["📅 스케줄","📝 세션","🧑‍🤝‍🧑 멤버","🍒 수입"],
    index=["📅 스케줄","📝 세션","🧑‍🤝‍🧑 멤버","🍒 수입"].index(st.session_state["nav"])
)
st.session_state["nav"] = nav

st.sidebar.markdown("**탭**")
st.sidebar.caption("이모지를 눌러 이동하세요.")

# ========== 데이터 로드 ==========
members = load_members()
sessions = load_sessions()
ex_db = load_ex_db()

# ==========================================================
# 🧑‍🤝‍🧑 멤버 (등록/수정/재등록/삭제 한 화면)
# ==========================================================
if nav == "🧑‍🤝‍🧑 멤버":
    st.header("멤버 관리")
    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])
        with left:
            existing_names = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", existing_names)
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel, placeholder="예: 김지현")
            phone = st.text_input("연락처", value="" if sel=="(새 회원)" else members.loc[members["이름"]==sel,"연락처"].iloc[0] if not members.empty and sel in members["이름"].values else "", placeholder="010-0000-0000")
        with right:
            site_default = "플로우"
            if sel != "(새 회원)" and sel in members["이름"].values:
                site_default = members.loc[members["이름"]==sel,"지점"].iloc[0] or "플로우"
            site = st.selectbox("기본 지점", SITES, index=SITES.index(site_default))
            reg_default = date.today()
            if sel != "(새 회원)" and sel in members["이름"].values:
                try:
                    reg_default = pd.to_datetime(members.loc[members["이름"]==sel,"등록일"].iloc[0]).date()
                except Exception:
                    reg_default = date.today()
            reg_date = st.date_input("등록일", reg_default)
            add_cnt = st.number_input("재등록 횟수(+)", 0, 100, 0, 1)

        note = st.text_input("메모(선택)", value="" if sel=="(새 회원)" else members.loc[members["이름"]==sel,"메모"].iloc[0] if not members.empty and sel in members["이름"].values else "")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                else:
                    if sel=="(새 회원)":
                        new_id = str(len(members)+1)
                        row = pd.DataFrame([{
                            "id":new_id,"이름":name.strip(),"연락처":phone.strip(),
                            "지점":site,"등록일":reg_date.isoformat(),
                            "총등록": "0","남은횟수":"0","메모":note
                        }])
                        members = pd.concat([members, row], ignore_index=True)
                        save_members(members)
                        st.success(f"신규 등록: {name}")
                    else:
                        idx = members.index[members["이름"]==sel][0]
                        members.loc[idx,"이름"] = name.strip()
                        members.loc[idx,"연락처"] = phone.strip()
                        members.loc[idx,"지점"] = site
                        members.loc[idx,"등록일"] = reg_date.isoformat()
                        members.loc[idx,"메모"] = note
                        save_members(members)
                        st.success("수정 완료")

        with c2:
            if st.button("재등록(+횟수 반영)", use_container_width=True, disabled=(sel=="(새 회원)")):
                if sel=="(새 회원)":
                    st.error("기존 회원을 먼저 선택하세요.")
                else:
                    idx = members.index[members["이름"]==sel][0]
                    total = int(float(members.loc[idx,"총등록"] or 0)) + int(add_cnt)
                    remain = int(float(members.loc[idx,"남은횟수"] or 0)) + int(add_cnt)
                    members.loc[idx,"총등록"] = str(total)
                    members.loc[idx,"남은횟수"] = str(remain)
                    save_members(members)
                    st.success(f"{sel} 재등록 +{add_cnt}회 반영")

        with c3:
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [])
            if st.button("멤버 삭제", use_container_width=True, disabled=members.empty):
                members = members[members["이름"]!=del_name].reset_index(drop=True)
                save_members(members)
                st.success(f"{del_name} 삭제 완료")

    with st.expander("📋 현재 멤버 보기 (토글)", expanded=False):
        if members.empty:
            big_info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            show["등록일"] = pd.to_datetime(show["등록일"], errors="coerce").dt.date.astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)

# ==========================================================
# 📝 세션 기록
# ==========================================================
elif nav == "📝 세션":
    st.header("세션 기록")
    if members.empty:
        big_info("먼저 멤버를 등록하세요.")
    # 공통 입력
    cols = st.columns([1,1,1,1])
    with cols[0]:
        day = st.date_input("날짜", value=date.today())
        time_str = st.time_input("시간", value=datetime.now().time())
    with cols[1]:
        session_type = st.radio("구분", ["개인","그룹"], horizontal=True)
    with cols[2]:
        # 개인은 멤버로부터 지점 자동
        if session_type=="개인":
            mname = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [])
            auto_site = members.loc[members["이름"]==mname,"지점"].iloc[0] if mname and mname in members["이름"].values else "플로우"
            site = st.selectbox("지점", SITES, index=SITES.index(auto_site))
        else:
            site = st.selectbox("지점", SITES)
            mname = ""
    with cols[3]:
        minutes = st.number_input("수업 분", 10, 180, 50, 5)

    c2 = st.columns([1,1,1,1])
    with c2[0]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"])
    with c2[1]:
        equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat","기타"])
    with c2[2]:
        headcount = st.number_input("인원(그룹)", 1, 10, 2 if session_type=="그룹" else 1, 1, disabled=(session_type=="개인"))
    with c2[3]:
        visit_pay = st.number_input("방문 수업 실수령(원)", 0, 1000000, 0, 1000, disabled=(site!="방문"))

    # 동작 선택(멀티) + 직접 추가
    # 분류 + 동작을 펼친 옵션으로 노출
    all_options = []
    for cat, moves in load_ex_db().items():
        for m in moves:
            all_options.append(f"{cat} · {m}")
    chosen = st.multiselect("운동 동작(복수 선택)", options=sorted(all_options))
    add_free = st.text_input("추가 동작(콤마 , 로 구분)", placeholder="예: Side bends, Mermaid")

    cancel = st.checkbox("취소")
    reason = st.text_input("사유(선택)", placeholder="예: 회원 사정/강사 사정 등")
    memo = st.text_area("메모(선택)", height=80)

    # 저장 버튼
    if st.button("세션 저장", use_container_width=True):
        when = datetime.combine(day, time_str)
        # 동작 DB에 사용자 추가 반영
        if add_free.strip():
            new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
            exdb = load_ex_db()
            exdb.setdefault("기타", [])
            # 중복 방지
            for nm in new_moves:
                if nm not in exdb["기타"]:
                    exdb["기타"].append(nm)
            save_ex_db(exdb)

        # 페이 계산
        gross, net = calc_pay(site, session_type, int(headcount), visit_pay)

        # 세션 저장
        row = pd.DataFrame([{
            "id": str(len(sessions)+1),
            "날짜": when,
            "지점": site,
            "구분": session_type,
            "이름": mname if session_type=="개인" else "",
            "인원": int(headcount) if session_type=="그룹" else 1,
            "레벨": level,
            "기구": equip,
            "동작(리스트)": "; ".join(chosen),
            "추가동작": add_free,
            "메모": memo,
            "취소": bool(cancel),
            "사유": reason,
            "분": int(minutes),
            "페이(총)": float(gross),
            "페이(실수령)": float(net)
        }])
        sessions = pd.concat([sessions, row], ignore_index=True)
        save_sessions(sessions)

        # 개인 세션 차감
        if session_type=="개인" and mname and not cancel and (mname in members["이름"].values):
            idx = members.index[members["이름"]==mname][0]
            remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
            members.loc[idx,"남은횟수"] = str(remain)
            save_members(members)

        st.success("세션 저장 완료!")

    st.subheader("최근 세션 목록")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        view = sessions.sort_values("날짜", ascending=False).copy()
        # 표에서 페이 컬럼은 숨기고 프라이버시 보호
        hide_cols = ["페이(총)","페이(실수령)"]
        show_cols = [c for c in view.columns if c not in hide_cols]
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ==========================================================
# 📅 스케줄 (일/주/월 전환)
# ==========================================================
elif nav == "📅 스케줄":
    st.header("스케줄 (일/주/월 전환)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        mode = st.segmented_control("보기", options=["일","주","월"], horizontal=True, index=1)
        base = st.date_input("기준 날짜", value=date.today())
        base_dt = datetime.combine(base, datetime.min.time())

        if mode=="일":
            start = base_dt
            end = base_dt + timedelta(days=1)
        elif mode=="주":
            start = base_dt - timedelta(days=base_dt.weekday())  # 월
            end = start + timedelta(days=7)
        else:
            start = base_dt.replace(day=1)
            end = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

        view = sessions[(sessions["날짜"]>=start) & (sessions["날짜"]<end)].copy()
        if view.empty:
            big_info("해당 기간에 일정이 없습니다.")
        else:
            view = view.sort_values("날짜")
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%m/%d %a %H:%M")
            # 지점 칩 + 멤버명 강조
            def row_style(r):
                name_html = f'<span style="font-size:16px; font-weight:800;">{r["이름"] if r["이름"] else "(그룹)"}</span>'
                site_chip = tag(r["지점"], SITE_COLOR.get(r["지점"], "#eee"))
                title = f'{r["날짜"]} · {site_chip} · {name_html}'
                body = f'{r["구분"]} · {r["레벨"]} · {r["기구"]}'
                if r["동작(리스트)"] or r["추가동작"]:
                    body += " · 동작: " + ", ".join([r["동작(리스트)"], r["추가동작"]]).strip(" ,")
                if bool(r["취소"]):
                    title = f'<s>{title}</s>'
                return title, body

            rows = []
            for _, r in view.iterrows():
                t, b = row_style(r)
                rows.append(f"<div style='padding:10px; border-bottom:1px solid #333'>{t}<br><span style='color:#bbb'>{b}</span></div>")
            st.markdown("<div>"+ "".join(rows) +"</div>", unsafe_allow_html=True)

# ==========================================================
# 🍒 수입 (PIN 잠금)
# ==========================================================
elif nav == "🍒 수입":
    st.header("🍒 수입")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****")
        if st.button("열기"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        if sessions.empty:
            big_info("세션 데이터가 없습니다.")
        else:
            df = sessions.copy()
            df["Y"] = pd.to_datetime(df["날짜"]).dt.year
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            month_sum = df.groupby("YM")["페이(실수령)"].sum().astype(int).reset_index()
            year_sum  = df.groupby("Y")["페이(실수령)"].sum().astype(int).reset_index()
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("월별 합계")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with col2:
                st.subheader("연도 합계")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.subheader("상세(개별 세션)")
            view = df.sort_values("날짜", ascending=False)
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view, use_container_width=True, hide_index=True)

