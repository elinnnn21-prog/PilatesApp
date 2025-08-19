# app.py
import os
from pathlib import Path
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Tuple

import pandas as pd
import streamlit as st

# ==============================
# 기본 설정 & 상수
# ==============================
st.set_page_config(page_title="✨", page_icon="✨", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV   = DATA_DIR / "members.csv"
SESSIONS_CSV  = DATA_DIR / "sessions.csv"
SCHEDULE_CSV  = DATA_DIR / "schedule.csv"
EX_JSON       = DATA_DIR / "exercise_db.json"

# PIN (Streamlit Cloud secrets에 CHERRY_PW가 있으면 그 값 사용)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

# 지점 표기: F/R/V
SITES = ["F","R","V"]
SITE_LABEL = {"F":"F (플로우)","R":"R (리유)","V":"V (방문)"}
SITE_COLOR = {"F":"#d9f0ff","R":"#f0f0f0","V":"#e9fbe9"}  # 칩 색상

# 동작 DB(요약) — 필요한 만큼만 시작, 사용 중 기타에 누적됨
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
    "Barrel/Spine": [
        "Swan","Horseback","Side sit up","Ballet stretch side","Thigh stretch"
    ],
    "기타": []
}

# ==============================
# 파일 유틸
# ==============================
MEMBER_COLS  = ["id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형","메모","재등록횟수","최근재등록일"]
SESSION_COLS = ["id","날짜","지점","구분","이름","인원","레벨","기구","동작(리스트)","추가동작",
                "특이사항","숙제","메모","취소","사유","분","온더하우스","페이(총)","페이(실수령)"]
SCHEDULE_COLS= ["id","날짜","지점","구분","이름","인원","레벨","기구","특이사항","숙제","메모",
                "온더하우스","상태"]  # 상태: 예약됨/완료/취소됨/No Show

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=MEMBER_COLS).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=SESSION_COLS).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    if not SCHEDULE_CSV.exists():
        pd.DataFrame(columns=SCHEDULE_COLS).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

# -------- iCal(ICS) 내보내기 헬퍼 --------
from datetime import timezone

def _fmt_ics_dt(dt):
    # Asia/Seoul 기준 '떠있는 로컬시간'으로 작성 (대부분의 캘린더에서 정상 인식)
    return dt.strftime("%Y%m%dT%H%M%S")

def build_ics_from_df(df: pd.DataFrame, default_minutes: int = 50) -> bytes:
    """
    보이는 스케줄 DataFrame(df) → .ics 바이너리로 변환
    - 취소건은 df에서 미리 제외해서 넣어 주세요.
    - 종료시간은 '분' 컬럼이 있으면 반영, 없으면 default_minutes 사용
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PilatesApp//Schedule Export//KR",
        "CALSCALE:GREGORIAN",
    ]
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for _, r in df.iterrows():
        try:
            start = pd.to_datetime(r["날짜"])
        except Exception:
            continue
        minutes = 0
        try:
            minutes = int(float(r.get("분", default_minutes) or default_minutes))
        except Exception:
            minutes = default_minutes
        end = start + timedelta(minutes=minutes)

        title_name = r.get("이름", "") or "(그룹)"
        kind = r.get("구분", "")
        site = r.get("지점", "")
        level = r.get("레벨", "")
        equip = r.get("기구", "")
        moves = (r.get("동작(리스트)", "") or "").strip()
        extra = (r.get("추가동작","") or "").strip()
        memo  = (r.get("메모","") or "").strip()

        summary = f"{title_name} ({kind}) [{site}]"
        desc_parts = []
        if level: desc_parts.append(f"레벨: {level}")
        if equip: desc_parts.append(f"기구: {equip}")
        if moves: desc_parts.append(f"동작: {moves}")
        if extra: desc_parts.append(f"추가동작: {extra}")
        if memo:  desc_parts.append(f"메모: {memo}")
        description = "\\n".join(desc_parts)  # ICS는 줄바꿈에 \n 대신 \\n

        uid = f"{int(start.timestamp())}-{title_name.replace(' ','')}-{kind}@pilatesapp"

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{summary}",
            f"LOCATION:{site}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    content = "\r\n".join(lines) + "\r\n"
    return content.encode("utf-8")
    
    # 스키마 업그레이드(누락 컬럼 자동 추가)
    def upgrade(csv_path: Path, must_cols: List[str]):
        try:
            df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig").fillna("")
        except Exception:
            df = pd.DataFrame(columns=must_cols)
        add = [c for c in must_cols if c not in df.columns]
        for c in add:
            df[c] = ""
        # 지점 한글 → F/R/V 매핑
        if "지점" in df.columns:
            df["지점"] = df["지점"].replace({"플로우":"F","리유":"R","방문":"V"})
            df.loc[~df["지점"].isin(SITES), "지점"] = df["지점"].mask(df["지점"].isin(SITES), df["지점"]).fillna("F").replace("", "F")
        df = df[must_cols]
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    upgrade(MEMBERS_CSV, MEMBER_COLS)
    upgrade(SESSIONS_CSV, SESSION_COLS)
    upgrade(SCHEDULE_CSV, SCHEDULE_COLS)

def load_members() -> pd.DataFrame:
    return pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
    else:
        # 타입 컬럼 기본값
        df["취소"] = False
        df["온더하우스"] = False
    return df

def save_sessions(df: pd.DataFrame):
    out = df.copy()
    if not out.empty:
        out["날짜"] = pd.to_datetime(out["날짜"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_schedule() -> pd.DataFrame:
    df = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
    else:
        df["온더하우스"] = False
    return df

def save_schedule(df: pd.DataFrame):
    out = df.copy()
    if not out.empty:
        out["날짜"] = pd.to_datetime(out["날짜"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_JSON, typ="series")
        d = {k: list(v) for k, v in raw.items()}
        for k,v in EX_DB_DEFAULT.items():
            d.setdefault(k, v)
        return d
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_JSON, force_ascii=False)

ensure_files()

# ==============================
# 도우미
# ==============================
def big_info(msg: str, kind="info"):
    if kind=="warn": st.warning(msg)
    elif kind=="error": st.error(msg)
    else: st.info(msg)

def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def calc_pay(site: str, session_type: str, headcount: int) -> Tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 35,000원, 3.3% 공제
    R(리유): 개인 30,000 / 3명 40,000 / 2명(듀엣) 35,000 / 1명 25,000 (공제 없음)
    V(방문): 기본 0 (필요 시 별도 정책 가능) — 여기선 0 원으로 처리
    """
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net = round(gross * 0.967, 0)  # 3.3% 공제
    elif site == "R":
        if session_type == "개인":
            gross = net = 30000.0
        else:
            if headcount == 2:
                gross = net = 35000.0
            elif headcount == 3:
                gross = net = 40000.0
            elif headcount == 1:
                gross = net = 25000.0
            else:
                gross = net = 30000.0
    else:  # V
        gross = net = 0.0
    return gross, net

def ensure_id(df: pd.DataFrame) -> str:
    return str((df["id"].astype(int).max() + 1) if (not df.empty and df["id"].str.isnumeric().any()) else (len(df)+1))

# ==============================
# 사이드바 상단 커스텀 메뉴 (버튼만)
# ==============================
st.markdown("""
<style>
/* 버튼을 메뉴처럼 보이게 (배경/테두리 제거) */
div[data-testid="stHorizontalBlock"] button[kind="secondary"]{
  background: transparent !important; border: none !important; box-shadow: none !important;
}
.menu-active{font-weight:800; color:#FF4B4B;}
.menu-item{font-size:18px; padding:6px 8px;}
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "schedule"   # 첫 화면: 스케줄

cols = st.columns([1,1,1,1,1])
with cols[0]:
    if st.button("📅 스케줄", use_container_width=True):
        st.session_state.page = "schedule"
with cols[1]:
    if st.button("✍️ 세션", use_container_width=True):
        st.session_state.page = "session"
with cols[2]:
    if st.button("👥 멤버", use_container_width=True):
        st.session_state.page = "member"
with cols[3]:
    if st.button("📋 리포트", use_container_width=True):
        st.session_state.page = "report"
with cols[4]:
    if st.button("🍒", use_container_width=True):
        st.session_state.page = "cherry"

st.markdown("<hr>", unsafe_allow_html=True)

# ==============================
# 데이터 로드
# ==============================
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
ex_db    = load_ex_db()

# ==============================
# 📅 스케줄
# ==============================
if st.session_state.page == "schedule":
    st.subheader("📅 스케줄")
    # 보기 전환
    vcols = st.columns([1,1,2,1])
    with vcols[0]:
        view_mode = st.radio("보기", ["일","주","월"], horizontal=True, index=1, label_visibility="collapsed")
    with vcols[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed")
    with vcols[2]:
        pass
    with vcols[3]:
        pass

    base_dt = datetime.combine(base, time.min)
    if view_mode=="일":
        start, end = base_dt, base_dt + timedelta(days=1)
    elif view_mode=="주":
        start = base_dt - timedelta(days=base_dt.weekday())
        end   = start + timedelta(days=7)
    else:
        start = base_dt.replace(day=1)
        end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

    # 예약 등록
    st.markdown("#### ✨ 예약 등록")
    c = st.columns([1,1,1,1,1,1])
    with c[0]:
        sdate = st.date_input("날짜", value=base)
    with c[1]:
        stime = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0))
    with c[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True)
    with c[3]:
        if stype=="개인":
            mname = st.selectbox("이름(개인)", members["이름"].tolist() if not members.empty else [])
            default_site = members.loc[members["이름"]==mname,"기본지점"].iloc[0] if mname and (mname in members["이름"].values) else "F"
        else:
            mname = ""
            default_site = "F"
        site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES], index=SITES.index(default_site))
        site = site.split()[0]
    with c[4]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"])
    with c[5]:
        equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat","기타"])
    cc = st.columns([1,1,1,2])
    with cc[0]:
        headcount = st.number_input("인원(그룹)", 1, 10, 1 if stype=="개인" else 2, 1, disabled=(stype=="개인"))
    with cc[1]:
        onth = st.checkbox("✨ On the house")  # 스케줄에도 표시/전파
    with cc[2]:
        spec_note = st.text_input("특이사항", value="")
    with cc[3]:
        homework = st.text_input("숙제", value="")

    if st.button("예약 추가", use_container_width=True):
        when = datetime.combine(sdate, stime)
        row = pd.DataFrame([{
            "id": ensure_id(schedule),
            "날짜": when,
            "지점": site,
            "구분": stype,
            "이름": mname if stype=="개인" else "",
            "인원": int(headcount) if stype=="그룹" else 1,
            "레벨": level,
            "기구": equip,
            "특이사항": spec_note,
            "숙제": homework,
            "메모": "",
            "온더하우스": bool(onth),
            "상태": "예약됨"
        }])
        schedule = pd.concat([schedule, row], ignore_index=True)
        save_schedule(schedule)
        st.success("예약이 추가되었습니다.")

    # 기간 뷰
    st.markdown("#### 📋 일정")
    v = schedule[(schedule["날짜"]>=start) & (schedule["날짜"]<end)].copy().sort_values("날짜")
    if v.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
        # 시간 경과에 따라 완료 후보 → No Show 자동 보기는 표시용(실제 상태 변경은 버튼)
        def line_of(r):
            name_html = f'<b style="font-size:16px">{r["이름"] if r["이름"] else "(그룹)"}</b>'
            chip = tag(r["지점"], SITE_COLOR.get(r["지점"],"#eee"))
            free = " · ✨" if r["온더하우스"] else ""
            title = f'{pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")} · {chip} · {name_html}{free}'
            sub = f'{r["구분"]} · {r["레벨"]} · {r["기구"]}'
            if r["특이사항"]:
                sub += f' · 특이: {r["특이사항"]}'
            badge = r["상태"]
            if badge=="취소됨":
                title = f"<s>{title}</s>"
            return title, sub, badge

        for i, r in v.iterrows():
            t, b, badge = line_of(r)
            colA, colB, colC, colD, colE = st.columns([3,1,1,1,1])
            with colA:
                st.markdown(f"{t}<br><span style='color:#bbb'>{b}</span><br><span>상태: <b>{badge}</b></span>", unsafe_allow_html=True)
            with colB:
                if st.button("출석", key=f"att_{r['id']}"):
                    # 세션 자동 생성 (출석=완료)
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"]))
                    free = bool(r["온더하우스"])
                    if free:
                        gross = net = 0.0
                    # No Show가 아니라면 운동내용은 비워둠(세션 탭에서 후기 입력 가능)
                    sess = pd.DataFrame([{
                        "id": ensure_id(sessions),
                        "날짜": r["날짜"],
                        "지점": r["지점"],
                        "구분": r["구분"],
                        "이름": r["이름"],
                        "인원": int(r["인원"]),
                        "레벨": r["레벨"],
                        "기구": r["기구"],
                        "동작(리스트)": "",
                        "추가동작": "",
                        "특이사항": r["특이사항"],
                        "숙제": r["숙제"],
                        "메모": "",
                        "취소": False,
                        "사유": "",
                        "분": 50,
                        "온더하우스": free,
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)
                    # 횟수 차감(개인 + 무료 아님)
                    if (r["구분"]=="개인") and (r["이름"] in members["이름"].values) and (not free):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(remain)
                        save_members(members)
                    schedule.loc[schedule["id"]==r["id"], "상태"] = "완료"
                    save_schedule(schedule)
                    st.experimental_rerun()
            with colC:
                if st.button("취소", key=f"can_{r['id']}"):
                    schedule.loc[schedule["id"]==r["id"], "상태"] = "취소됨"
                    save_schedule(schedule)
                    st.experimental_rerun()
            with colD:
                if st.button("No Show", key=f"nos_{r['id']}"):
                    # No Show도 세션 생성 + 차감 + 페이 반영
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"]))
                    free = bool(r["온더하우스"])
                    if free:
                        gross = net = 0.0
                    sess = pd.DataFrame([{
                        "id": ensure_id(sessions),
                        "날짜": r["날짜"],
                        "지점": r["지점"],
                        "구분": r["구분"],
                        "이름": r["이름"],
                        "인원": int(r["인원"]),
                        "레벨": r["레벨"],
                        "기구": r["기구"],
                        "동작(리스트)": "",
                        "추가동작": "",
                        "특이사항": "No Show",
                        "숙제": "",
                        "메모": "",
                        "취소": False,
                        "사유": "No Show",
                        "분": 50,
                        "온더하우스": free,
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)
                    # 횟수 차감(개인 + 무료 아님)
                    if (r["구분"]=="개인") and (r["이름"] in members["이름"].values) and (not free):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(remain)
                        save_members(members)
                    schedule.loc[schedule["id"]==r["id"], "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()
            with colE:
                st.write("")  # 여백

# ==============================
# ✍️ 세션 (수동기록/수정)
# ==============================
elif st.session_state.page == "session":
    st.subheader("✍️ 세션 기록")
    if members.empty:
        big_info("먼저 멤버를 등록하세요.")
    cols = st.columns([1,1,1,1])
    with cols[0]:
        day = st.date_input("날짜", value=date.today())
        time_str = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0))
    with cols[1]:
        session_type = st.radio("구분", ["개인","그룹"], horizontal=True)
    with cols[2]:
        if session_type=="개인":
            mname = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [])
            auto_site = members.loc[members["이름"]==mname,"기본지점"].iloc[0] if mname and (mname in members["이름"].values) else "F"
            site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES], index=SITES.index(auto_site))
            site = site.split()[0]
        else:
            site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES])
            site = site.split()[0]; mname=""
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
        free_onhouse = st.checkbox("✨ On the house")

    # 동작 멀티(개인만), 그룹은 특이만
    chosen = []
    add_free = ""
    if session_type=="개인":
        # 분류별 옵션 펼치기
        options = []
        for cat, moves in load_ex_db().items():
            for m in moves:
                options.append(f"{cat} · {m}")
        chosen = st.multiselect("운동 동작(복수 선택)", options=sorted(options))
        add_free = st.text_input("추가 동작(콤마 , 로 구분)", placeholder="예: Side bends, Mermaid")

    spec_note = st.text_area("특이사항(선택)", height=70)
    homework  = st.text_area("숙제(선택)", height=70 if session_type=="개인" else 40)
    memo      = st.text_area("메모(선택)", height=60)

    cancel = st.checkbox("취소")
    reason = st.text_input("사유(선택)", placeholder="예: 회원 사정/강사 사정 등")

    if st.button("세션 저장", use_container_width=True):
        when = datetime.combine(day, time_str)
        # 추가 동작 DB 누적
        if session_type=="개인" and add_free.strip():
            new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
            exdb = load_ex_db()
            exdb.setdefault("기타", [])
            for nm in new_moves:
                if nm not in exdb["기타"]:
                    exdb["기타"].append(nm)
            save_ex_db(exdb)
        gross, net = calc_pay(site, session_type, int(headcount))
        if free_onhouse:
            gross = net = 0.0
        row = pd.DataFrame([{
            "id": ensure_id(sessions),
            "날짜": when,
            "지점": site,
            "구분": session_type,
            "이름": mname if session_type=="개인" else "",
            "인원": int(headcount) if session_type=="그룹" else 1,
            "레벨": level,
            "기구": equip,
            "동작(리스트)": "; ".join(chosen) if session_type=="개인" else "",
            "추가동작": add_free if session_type=="개인" else "",
            "특이사항": spec_note,
            "숙제": homework if session_type=="개인" else "",
            "메모": memo,
            "취소": bool(cancel),
            "사유": reason,
            "분": int(minutes),
            "온더하우스": bool(free_onhouse),
            "페이(총)": float(gross),
            "페이(실수령)": float(net)
        }])
        sessions = pd.concat([sessions, row], ignore_index=True)
        save_sessions(sessions)
        # 차감(개인 + 취소X + 무료X)
        if (session_type=="개인") and mname and (mname in members["이름"].values) and (not cancel) and (not free_onhouse):
            idx = members.index[members["이름"]==mname][0]
            remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
            members.loc[idx,"남은횟수"] = str(remain)
            save_members(members)
        st.success("세션 저장 완료!")

    st.markdown("#### 최근 세션")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        v = sessions.sort_values("날짜", ascending=False).copy()
        v["날짜"] = pd.to_datetime(v["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(v.drop(columns=["페이(총)","페이(실수령)"]), use_container_width=True, hide_index=True)

# ==============================
# 👥 멤버
# ==============================
elif st.session_state.page == "member":
    st.subheader("👥 멤버 관리")
    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])
        with left:
            names = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", names)
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel)
            # 중복 전화번호 경고
            default_phone = ""
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_phone = members.loc[members["이름"]==sel,"연락처"].iloc[0]
            phone = st.text_input("연락처", value=default_phone, placeholder="010-0000-0000")
            if phone and (members[(members["연락처"]==phone) & (members["이름"]!=name)].shape[0] > 0):
                st.error("⚠️ 동일한 전화번호가 이미 존재합니다.")
        with right:
            default_site = "F"
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_site = members.loc[members["이름"]==sel,"기본지점"].iloc[0] or "F"
            site = st.selectbox("기본 지점", [SITE_LABEL[s] for s in SITES], index=SITES.index(default_site))
            site = site.split()[0]
            reg_default = date.today()
            if sel!="(새 회원)" and sel in members["이름"].values:
                try:
                    reg_default = pd.to_datetime(members.loc[members["이름"]==sel,"등록일"].iloc[0]).date()
                except Exception:
                    pass
            reg_date = st.date_input("등록일", reg_default)
            add_cnt = st.number_input("재등록(+횟수)", 0, 100, 0, 1)
        note = st.text_input("메모(선택)",
                             value="" if sel=="(새 회원)" else members.loc[members["이름"]==sel,"메모"].iloc[0]
                             if (sel in members["이름"].values) else "")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                else:
                    if sel=="(새 회원)":
                        row = pd.DataFrame([{
                            "id": ensure_id(members),"이름":name.strip(),"연락처":phone.strip(),
                            "기본지점":site,"등록일":reg_date.isoformat(),
                            "총등록":"0","남은횟수":"0","회원유형":"일반",
                            "메모":note,"재등록횟수":"0","최근재등록일":""
                        }])
                        members = pd.concat([members, row], ignore_index=True)
                    else:
                        idx = members.index[members["이름"]==sel][0]
                        members.loc[idx,["이름","연락처","기본지점","등록일","메모"]] = \
                            [name.strip(), phone.strip(), site, reg_date.isoformat(), note]
                    save_members(members)
                    st.success("저장 완료")
        with c2:
            if st.button("재등록(+횟수 반영)", use_container_width=True, disabled=(sel=="(새 회원)")):
                if sel=="(새 회원)":
                    st.error("기존 회원 선택")
                else:
                    idx = members.index[members["이름"]==sel][0]
                    members.loc[idx,"총등록"] = str(int(float(members.loc[idx,"총등록"] or 0)) + int(add_cnt))
                    members.loc[idx,"남은횟수"] = str(int(float(members.loc[idx,"남은횟수"] or 0)) + int(add_cnt))
                    members.loc[idx,"재등록횟수"] = str(int(float(members.loc[idx,"재등록횟수"] or 0)) + 1)
                    members.loc[idx,"최근재등록일"] = date.today().isoformat()
                    save_members(members)
                    st.success(f"{sel} 재등록 반영")
        with c3:
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [])
            if st.button("멤버 삭제", use_container_width=True, disabled=members.empty):
                members = members[members["이름"]!=del_name].reset_index(drop=True)
                save_members(members)
                st.success(f"{del_name} 삭제 완료")

    with st.expander("📋 현재 멤버 보기", expanded=False):
        if members.empty:
            big_info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            for c in ["등록일","최근재등록일"]:
                show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)

# ==============================
# 📋 리포트 (회원 동작만)
# ==============================
elif st.session_state.page == "report":
    st.subheader("📋 리포트 (회원 동작)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        # 개인 세션만 대상으로
        df = sessions[sessions["구분"]=="개인"].copy()
        if df.empty:
            big_info("개인 세션 데이터가 없습니다.")
        else:
            month = st.date_input("월 선택", value=date.today().replace(day=1))
            ym = pd.to_datetime(month).strftime("%Y-%m")
            who = st.selectbox("회원 선택", sorted(df["이름"].dropna().unique().tolist()))
            if who:
                mdf = df[(df["이름"]==who)]
                # 동작 분해
                def explode_moves(s: pd.Series) -> List[str]:
                    moves = []
                    for val in s.fillna(""):
                        for part in str(val).split(";"):
                            part = part.strip()
                            if part:
                                # "카테고리 · 동작" → 동작만
                                if "·" in part:
                                    moves.append(part.split("·",1)[1].strip())
                                else:
                                    moves.append(part)
                    return moves
                mdf["YM"] = pd.to_datetime(mdf["날짜"]).dt.strftime("%Y-%m")
                cur = mdf[mdf["YM"]==ym]
                mv = explode_moves(cur["동작(리스트)"])
                st.markdown(f"**{who} · {ym} Top5 동작**")
                if mv:
                    s = pd.Series(mv).value_counts().head(5).reset_index()
                    s.columns = ["동작","횟수"]
                    st.dataframe(s, use_container_width=True, hide_index=True)
                else:
                    big_info("해당 월에 기록된 동작이 없습니다.")
                # 최근 6개월 추이(전체 동작 집계)
                st.markdown("**최근 6개월 동작 총량 추이(건수)**")
                mdf["YM"] = pd.to_datetime(mdf["날짜"]).dt.strftime("%Y-%m")
                cnt = mdf.groupby("YM")["동작(리스트)"].apply(lambda x: sum(len([p for v in x for p in str(v).split(';') if p.strip()]) )).reset_index()
                cnt = cnt.sort_values("YM").tail(6)
                st.dataframe(cnt, use_container_width=True, hide_index=True)

# ==============================
# 🍒 수입 (PIN 잠금, 이모지 표시만)
# ==============================
elif st.session_state.page == "cherry":
    st.subheader("🍒")
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
                st.markdown("**월별 합계**")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with col2:
                st.markdown("**연도 합계**")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.markdown("**상세(개별 세션)**")
            view = df.sort_values("날짜", ascending=False)
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view, use_container_width=True, hide_index=True)


