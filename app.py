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
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"])
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    df = df.copy()
    if not df.empty:
        df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_JSON, typ="series")
        d = {k: list(v) for k, v in raw.items()}
        for k, v in EX_DB_DEFAULT.items():
            d.setdefault(k, v)
        return d
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_JSON, force_ascii=False)

# 전화번호 비교용: 숫자만 남김 (010-1111-2222 == 01011112222)
def norm_phone(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())

ensure_files()

# ========== 가격 계산 ==========
def calc_pay(site: str, session_type: str, headcount: int, custom_visit_pay: float|None) -> tuple[float,float]:
    """
    returns (gross, net)
    플로우: 회당 35,000원, 3.3% 공제
    리유: 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣 35,000
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
            mapping = {3:40000.0, 2:30000.0, 1:25000.0}
            if headcount == 2:
                gross = net = 35000.0  # 듀엣
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
# 🧑‍🤝‍🧑 멤버 (등록/수정/재등록/삭제 한 화면) + 전화번호 중복확인
# ==========================================================
if nav == "🧑‍🤝‍🧑 멤버":
    st.header("멤버 관리")
    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])
        with left:
            existing_names = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", existing_names)
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel, placeholder="예: 김지현")

            # 선택된 회원의 기존 번호 불러오기
            default_phone = ""
            if sel != "(새 회원)" and not members.empty and sel in members["이름"].values:
                default_phone = members.loc[members["이름"]==sel, "연락처"].iloc[0]
            phone = st.text_input("연락처", value=default_phone, placeholder="010-0000-0000")

            # 실시간 중복 경고 (입력만 해도 표시)
            if phone.strip() and not members.empty:
                if sel == "(새 회원)":
                    dup = any(members["연락처"].apply(norm_phone) == norm_phone(콜))
                else:
                    idx = members.index[members["이름"]==sel][0]
                    dup = any(members.drop(index=idx)["연락처"].apply(norm_phone) == norm_phone(콜))
                if dup:
                    st.warning("⚠️ 이미 등록된 번호입니다. 저장 시 거절됩니다.")
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

        note = st.text_input("메모(선택)", value="" if sel=="(새 회원)" else (
            members.loc[members["이름"]==sel,"메모"].iloc[0] if not members.empty and sel in members["이름"].values else "")
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                    st.stop()
                if not phone.strip():
                    st.error("연락처를 입력하세요.")
                    st.stop()

                if sel == "(새 회원)":
                    # 신규: 전체에서 중복 검사
                    np = norm_phone(콜)
                    if any(members["연락처"].apply(norm_phone) == np):
                        who = members[members["연락처"].apply(norm_phone) == np].iloc[0]["이름"]
                        st.error(f"이미 등록된 전화번호입니다. (소유자: {who})")
                        st.stop()

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
                    # 수정: 본인 제외 중복 검사
                    idx = members.index[members["이름"]==sel][0]
                    np = norm_phone(콜)
                    others = members.drop(index=idx)
                    if any(others["연락처"].apply(norm_phone) == np):
                        who = others[others["연락처"].apply(norm_phone) == np].iloc[0]["이름"]
                        st.error(f"이미 다른 회원이 사용 중인 번호입니다. (소유자: {who})")
                        st.stop()

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
    cols = st.columns([1,1,1,1])
    with cols[0]:
        day = st.date_input("날짜", value=date.today())
        time_str = st.time_input("시간", value=datetime.now().time())
    with cols[1]:
        session_type = st.radio("구분", ["개인","그룹"], horizontal=True)
    with cols[2]:
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

    all_options = []
    for cat, moves in load_ex_db().items():
        for m in moves:
            all_options.append(f"{cat} · {m}")
    chosen = st.multiselect("운동 동작(복수 선택)", options=sorted(all_options))
    add_free = st.text_input("추가 동작(콤마 , 로 구분)", placeholder="예: Side bends, Mermaid")

    cancel = st.checkbox("취소")
    reason = st.text_input("사유(선택)", placeholder="예: 회원 사정/강사 사정 등")
    memo = st.text_area("메모(선택)", height=80)

    if st.button("세션 저장", use_container_width=True):
        when = datetime.combine(day, time_str)
        if add_free.strip():
            new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
            exdb = load_ex_db()
            exdb.setdefault("기타", [])
            for nm in new_moves:
                if nm not in exdb["기타"]:
                    exdb["기타"].append(nm)
            save_ex_db(exdb)

        gross, net = calc_pay(site, session_type, int(headcount), visit_pay)

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
            start = base_dt - timedelta(days=base_dt.weekday())
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




# =========================
# DB 연결
# =========================
conn = sqlite3.connect("sessions.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER,
    date TEXT,
    equipment TEXT,
    exercise TEXT,
    notes TEXT,
    homework TEXT,
    status TEXT DEFAULT '예약됨',
    FOREIGN KEY(member_id) REFERENCES members(id)
)
""")
conn.commit()

# =========================
# 운동 리스트 로드
# =========================
if os.path.exists("exercises.json"):
    with open("exercises.json", "r", encoding="utf-8") as f:
        EXERCISES = json.load(f)
else:
    EXERCISES = {
        "Mat": {"Basic": [], "Intermediate": [], "Advanced": []},
        "Reformer": {"Basic": [], "Intermediate": [], "Advanced": []},
        "Cadillac": {},
        "Wunda chair": {},
        "Spine corrector": {},
        "Ladder barrel": {}
    }

# =========================
# 멤버 관리 탭
# =========================
def member_management():
    st.header("👤 멤버 관리")

    menu = ["멤버 추가", "멤버 목록"]
    choice = st.radio("선택", menu)

    if choice == "멤버 추가":
        name = st.text_input("이름")
        phone = st.text_input("전화번호")

        if st.button("저장"):
            if not name or not phone:
                st.warning("이름과 전화번호를 입력하세요.")
            else:
                try:
                    c.execute("INSERT INTO members (name, phone) VALUES (?, ?)", (name, phone))
                    conn.commit()
                    st.success(f"{name} 님이 등록되었습니다.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ 이미 등록된 전화번호입니다.")

    elif choice == "멤버 목록":
        members = c.execute("SELECT * FROM members").fetchall()
        for m in members:
            st.write(f"{m[0]} | {m[1]} | {m[2]}")

# =========================
# 세션 관리 탭
# =========================
def session_management():
    st.header("📅 세션 관리")

    members = c.execute("SELECT * FROM members").fetchall()
    member_dict = {f"{m[1]} ({m[2]})": m[0] for m in members}

    if not member_dict:
        st.warning("등록된 멤버가 없습니다. 멤버를 먼저 추가하세요.")
        return

    member = st.selectbox("멤버 선택", list(member_dict.keys()))
    member_id = member_dict[member]

    date = st.date_input("세션 날짜")
    equipment = st.selectbox("기구 선택", list(EXERCISES.keys()))

    # 기구별 동작 필터링
    exercise_options = []
    if isinstance(EXERCISES[equipment], dict):
        for level, ex_list in EXERCISES[equipment].items():
            exercise_options.extend([f"{level}: {ex}" for ex in ex_list])
    else:
        exercise_options = EXERCISES[equipment]

    exercise = st.multiselect("동작 선택", exercise_options)
    custom_exercise = st.text_input("직접 입력 (콤마로 구분)")
    if custom_exercise:
        exercise.extend([e.strip() for e in custom_exercise.split(",")])

    notes = st.text_area("특이사항")
    homework = st.text_area("숙제")

    if st.button("세션 저장"):
        c.execute("""
        INSERT INTO sessions (member_id, date, equipment, exercise, notes, homework)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (member_id, str(date), equipment, ", ".join(exercise), notes, homework))
        conn.commit()
        st.success("세션이 저장되었습니다 ✅")

    st.subheader("예약된 세션")
    sessions = c.execute("""
    SELECT s.id, m.name, s.date, s.equipment, s.exercise, s.status
    FROM sessions s
    JOIN members m ON s.member_id = m.id
    ORDER BY s.date
    """).fetchall()

    for s in sessions:
        st.write(f"{s[1]} | {s[2]} | {s[3]} | {s[4]} | 상태: {s[5]}")
        if st.button(f"세션 취소 {s[0]}", key=f"cancel_{s[0]}"):
            c.execute("UPDATE sessions SET status='취소됨' WHERE id=?", (s[0],))
            conn.commit()
            st.warning(f"세션 {s[0]}이 취소되었습니다.")

# =========================
# 메인 앱 실행
# =========================
def main():
    st.title("Pilates Manager")

    menu = ["멤버 관리", "세션 관리"]
    choice = st.sidebar.radio("메뉴 선택", menu)

    if choice == "멤버 관리":
        member_management()
    elif choice == "세션 관리":
        session_management()

if __name__ == "__main__":
    main()

