# app.py
import os
import io
import zipfile
import base64
from pathlib import Path
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, List

import pandas as pd
import streamlit as st

# ===============================
# 기본 설정 (favicon 자동 처리)
# ===============================
DATA_DIR = Path(".")
FAVICON = DATA_DIR / "favicon.png"   # 원하면 이 파일 넣어두면 브라우저 탭 아이콘으로 적용
if FAVICON.exists():
    st.set_page_config(page_title="Pilates Manager", page_icon=str(FAVICON), layout="wide")
else:
    st.set_page_config(page_title="Pilates Manager", page_icon="✨", layout="wide")

# 브라우저 탭 favicon 강제 주입(파일 있을 때)
if FAVICON.exists():
    b64 = base64.b64encode(FAVICON.read_bytes()).decode()
    st.markdown(
        f"""
        <link rel="icon" type="image/png" href="data:image/png;base64,{b64}">
        """,
        unsafe_allow_html=True
    )

# ===============================
# 상수/파일 경로
# ===============================
MEMBERS_CSV   = DATA_DIR / "members.csv"
SESSIONS_CSV  = DATA_DIR / "sessions.csv"
SCHEDULE_CSV  = DATA_DIR / "schedule.csv"
EX_DB_JSON    = DATA_DIR / "exercise_db.json"
VISIT_CSV     = DATA_DIR / "visit_income.csv"   # 🍒 방문 수입(개별 기록용, 멤버 탭이 아니라 여기서 관리)

CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES      = ["F", "R", "V"]  # Flow / Ryu / Visit
SITE_KR    = {"F": "플로우", "R": "리유", "V": "방문"}
SITE_COLOR = {"F": "#d9f0ff", "R": "#eeeeee", "V": "#e9fbe9"}

# ===============================
# 기본 동작 DB (JSON이 없을 때 최초 생성)
#  - 네가 보내준 대분류/동작명을 반영. (필요 시 EX_DB_JSON로 교체 가능)
# ===============================
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat": [
        "The Hundred","Roll Up","Roll Over","Single Leg Circles","Rolling Like a Ball",
        "Single Leg Stretch","Double Leg Stretch","Single Straight Leg Stretch","Double Straight Leg Stretch",
        "Criss Cross","Spine Stretch Forward","Open Leg Rocker","Corkscrew","Saw","Swan",
        "Single Leg Kicks","Double Leg Kicks","Thigh Stretch Mat","Neck Pull","High Scissors",
        "High Bicycle","Shoulder Bridge","Spine Twist","Jackknife",
        "Side Kick Series -Front/Back -Up/Down -Small Circles -Big Circles",
        "Teaser 1","Teaser 2","Teaser 3","Hip Circles","Swimming",
        "Leg Pull Front (Down)","Leg Pull Back (Up)","Kneeling Side Kicks","Side Bend",
        "Boomerang","Seal","Crab","Rocking","Balance Control - Roll Over","Push Ups"
    ],
    "Reformer": [
        "Footwork -Toes -Arches -Heels -Tendon Stretch","Hundred","Overhead","Coordination",
        "Rowing -Into the Sternum -90 Degrees -From the Chest -From the Hips -Shaving -Hug",
        "Long Box -Pull Straps -T Straps -Backstroke -Teaser -Breaststroke -Horseback",
        "Long Stretch -Long Stretch -Down Stretch -Up Stretch -Elephant -Elephant One Leg Back -Long Back Stretch",
        "Stomach Massage -Round -Hands Back -Reach Up -Twist",
        "Short Box -Round Back -Flat Back -Side to Side -Twist -Around the World -Tree",
        "Short Spine Massage","Semi Circle","Chest Expansion","Thigh Stretch","Arm Circles",
        "Snake","Twist","Corkscrew","Tick Tock","Balance Control Step Off","Long Spine Massage",
        "Feet in Straps -Frogs -Leg Circles","Knee Stretch -Round -Arched -Knees Off","Running",
        "Pelvic Lift","Push Up Front","Push Up Back","Side Splits","Front Splits","Russian Splits"
    ],
    "Cadillac": [
        "Breathing","Spread Eagle","Pull Ups","Hanging Pull Ups","Twist Pull Ups",
        "Half Hanging / Full Hanging / Hanging Twists","Squirrel / Flying Squirrel",
        "Rollback Bar - Roll Down - One Arm Roll Down - Breathing - Chest Expansion - Thigh Stretch - Long Back Stretch - Rolling In and Out - Rolling Stomach Massage",
        "Rollback Bar(Standing) - Squats - Side Arm - Shaving - Bicep Curls - Zip Up",
        "Leg Springs - Circles - Walking - Beats - Bicycle - Small Circles - Frogs - In the Air (Circles/Walking/Beats/Bicycle/Airplane)",
        "Side Leg Springs - Front/Back - Up/Down - Small Circles - Big Circles - Bicycle",
        "Arm Springs - Flying Eagle - Press Down - Circles - Triceps - Press Down Side",
        "Arm Springs Standing - Squats - Hug - Boxing - Shaving - Butterfly - Side Arm - Fencing",
        "Push Thru Bar - Tower - Monkey - Teaser - Reverse Push Thru - Mermaid Sitting - Swan - Shoulder Roll Down - Push Thru",
        "Monkey on a Stick","Semi Circle","Ballet/Leg Stretches - Front - Back - Side"
    ],
    "Wunda chair": [
        "Footwork - Toes - Arches - Heels - Tendon Stretch","Push Down","Push Down One Arm",
        "Pull Up","Spine Stretch Forward","Teaser - on Floor","Swan","Swan One Arm","Teaser - on Top",
        "Mermaid - Seated","Arm Frog","Mermaid - Kneeling","Twist 1","Tendon Stretch","Table Top",
        "Mountain Climb","Going Up Front","Going Up Side","Push Down One Arm Side",
        "Pumping - Standing behind / Washer Woman","Frog - Facing Chair","Frog - Facing Out",
        "Leg Press Down - Front","Backward Arms","Push Up - Top","Push Up - Bottom","Flying Eagle"
    ],
    "Ladder Barrel": [
        "Ballet/Leg Stretches - Front (ladder)","Ballet/Leg Stretches - Front",
        "Ballet/Leg Stretches - Front with Bent Leg","Ballet/Leg Stretches - Side",
        "Ballet/Leg Stretches - Side with Bent Leg","Ballet/Leg Stretches - Back",
        "Ballet/Leg Stretches - Back with Bent Leg","Swan","Horseback",
        "Backbend (standing outside barrel)","Side Stretch",
        "Short Box - Round Back - Flat Back - Side to Side - Twist - Around the World - Tree",
        "Back Walkover (Ad)","Side Sit Ups","Handstand","Jumping Off the Stomach"
    ],
    "Spine Corrector": [
        "Arm Series - Stretch with Bar - Circles",
        "Leg Series - Circles - Scissors - Walking - Bicycle - Beats - Rolling In and Out",
        "Leg Circles Onto Head","Teaser","Hip Circles","Swan","Grasshopper","Rocking",
        "Swimming","Side Sit up","Shoulder Bridge"
    ],
    "Small Barrel": [
        "Arm Series - Circles - One Arm Up/Down - Hug - Stretch with Bar",
        "Leg Series - Circles - Small Circles - Walking - Beats - Scissors - Bicycle - Frog to V - Helicopter - Rolling In and Out - Swan - Rocking"
    ],
    "Pedi-pull": [
        "Chest Expansion","Arm Circles","Knee Bends - Facing Out - Arabesque(Front/Side/Back)","Centering"
    ],
    "Magic Circle": [
        "Mat - Hundred - Roll Up - Roll Over - Double Leg Stretch - Open Leg Rocker - Corkscrew - Neck Pull - Jackknife - Side Kicks - Teaser 1,2,3 - Hip Circles",
        "Sitting PrePilates - Above Knees - Between Feet",
        "Standing - Arm Series - Chest Expansion - Leg Series",
        "Chin Press","Forehead Press"
    ],
    "Arm Chair": [
        "Basics","Arm Lower & Lift","Boxing","Circles","Shaving","Hug","Sparklers","Chest Expansion"
    ],
    "Electric chair": [
        "Pumping","Pumping - One Leg","Pumping - Feet Hip Width",
        "Going Up - Front","Going Up - Side",
        "Standing Pumping - Front","Standing Pumping - Side","Standing Pumping - Crossover",
        "Achilles Stretch","Press Up - Back","Press Up - Front"
    ],
    "Foot Corrector": [
        "Press Down - Toes on Top","Press Down - Heel on Top","Toes","Arch","Heel","Massage"
    ],
    "Toe Corrector": [
        "Seated(One Leg & Both) - External Rotation from Hip - Flex/Point"
    ],
    "Neck Stretcher": [
        "Seated - Flat Back - Spine Stretch Forward"
    ],
    "기타": []
}

# ===============================
# 유틸/데이터 IO
# ===============================
def _site_coerce(v: str) -> str:
    s = str(v).strip()
    if s in SITES: return s
    if s in ["플로우","Flow","flow"]: return "F"
    if s in ["리유","Ryu","ryu"]:     return "R"
    if s in ["방문","Visit","visit"]: return "V"
    return "F"

def ensure_df_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = "" if c not in ["인원","분","페이(총)","페이(실수령)"] else 0
    return df

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)

    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",  # 회원유형: 일반/듀엣
            "메모","재등록횟수","최근재등록일"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제","메모",
            "취소","사유","분","온더하우스","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    if not SCHEDULE_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "메모","온더하우스","상태"  # 상태: 예약됨/완료/취소됨/No Show
        ]).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

    if not EX_DB_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)

    if not VISIT_CSV.exists():
        pd.DataFrame(columns=["날짜","금액","메모"]).to_csv(VISIT_CSV, index=False, encoding="utf-8-sig")

    # 스키마 업그레이드/보정(덮어쓰기 아님, 누락만 추가)
    mem = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    mem = ensure_df_columns(mem, [
        "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
        "메모","재등록횟수","최근재등록일"
    ])
    mem["기본지점"] = mem["기본지점"].apply(_site_coerce)
    if "회원유형" not in mem.columns: mem["회원유형"] = "일반"
    mem.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    ses = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    ses = ensure_df_columns(ses, [
        "id","날짜","지점","구분","이름","인원","레벨","기구",
        "동작(리스트)","추가동작","특이사항","숙제","메모",
        "취소","사유","분","온더하우스","페이(총)","페이(실수령)"
    ])
    ses["지점"] = ses["지점"].apply(_site_coerce)
    ses.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    sch = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    sch = ensure_df_columns(sch, [
        "id","날짜","지점","구분","이름","인원","레벨","기구",
        "메모","온더하우스","상태"
    ])
    sch["지점"] = sch["지점"].apply(_site_coerce)
    sch.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_members() -> pd.DataFrame:
    return pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
        df["취소"]       = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    x = df.copy()
    if not x.empty:
        x["날짜"] = pd.to_datetime(x["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    x.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_schedule() -> pd.DataFrame:
    df = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_schedule(df: pd.DataFrame):
    x = df.copy()
    if not x.empty:
        x["날짜"] = pd.to_datetime(x["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    x.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_visit() -> pd.DataFrame:
    return pd.read_csv(VISIT_CSV, dtype=str, encoding="utf-8-sig").fillna("")

def save_visit(df: pd.DataFrame):
    df.to_csv(VISIT_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_DB_JSON, typ="series")
        return {k: list(v) for k, v in raw.items()}
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_DB_JSON, force_ascii=False)

def ensure_id(df: pd.DataFrame) -> str:
    if df is None or df.empty or ("id" not in df.columns):
        return "1"
    try:
        return str(df["id"].astype(str).astype(int).max() + 1)
    except Exception:
        return str(len(df) + 1)

# ===============================
# 페이 계산 (듀엣/No Show/✨ 규칙 반영)
# ===============================
def calc_pay(site: str, session_type: str, headcount: int, mname: str|None=None, members: pd.DataFrame|None=None) -> tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 35,000, 3.3% 공제
    R(리유): 공제 없음
          - 개인 기본 30,000
          - 듀엣 35,000 (멤버가 '듀엣'인 경우)
          - 그룹: 3명 40,000 / 2명 30,000 / 1명 25,000
    V(방문): 세션에서는 0 처리(수입은 🍒에서 별도로 입력/집계)
    """
    site = _site_coerce(site)
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net   = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            # 듀엣(👭🏻)이면 35,000
            is_duet = False
            if mname and (members is not None) and (mname in members["이름"].values):
                ty = str(members.loc[members["이름"]==mname, "회원유형"].iloc[0] or "")
                is_duet = ("듀엣" in ty)
            gross = net = (35000.0 if is_duet else 30000.0)
        else:
            if headcount == 2:   # 그룹 2명
                gross = net = 30000.0
            elif headcount == 3:
                gross = net = 40000.0
            elif headcount == 1:
                gross = net = 25000.0
            else:
                gross = net = 30000.0
    else:   # V (방문) → 세션단에서는 0처리. (수입은 🍒의 방문수입에서 관리)
        gross = net = 0.0
    return gross, net

# ===============================
# 작은 유틸
# ===============================
def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

# iCal(ICS) 내보내기
def _fmt_ics_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S")

def build_ics_from_df(df: pd.DataFrame, default_minutes: int = 50) -> bytes:
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
        try:
            minutes = int(float(r.get("분", default_minutes) or default_minutes))
        except Exception:
            minutes = default_minutes
        end = start + timedelta(minutes=minutes)

        title = r["이름"] if str(r.get("이름","")).strip() else "그룹"
        loc   = SITE_KR.get(str(r.get("지점","")).strip(), str(r.get("지점","")).strip())

        ev = [
            "BEGIN:VEVENT",
            f"UID:{r.get('id', '')}@pilatesapp",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"LOCATION:{loc}",
        ]
        memo = str(r.get("메모","") or "")
        if memo:
            ev.append(f"DESCRIPTION:{memo}")
        ev.append("END:VEVENT")
        lines.extend(ev)

    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines)).encode("utf-8")

# ===============================
# 초기화/로드
# ===============================
ensure_files()
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
visit    = load_visit()
ex_db    = load_ex_db()

# ===============================
# 사이드바 메뉴 (중복 방지, 버튼만)
# ===============================
st.markdown("""
<style>
div[data-testid="stSidebar"] button[kind="secondary"]{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  text-align: left !important;
  padding: 6px 4px !important;
  font-size: 18px !important;
}
div[data-testid="stSidebar"] button[kind="secondary"].active{
  color:#ff4b4b !important; font-weight:800 !important;
}
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state["page"] = "schedule"  # 첫 페이지=스케줄

def menu_btn(label: str, key: str, emoji_only: bool=False):
    show = label if not emoji_only else label.split()[0]
    clicked = st.sidebar.button(show, key=f"menu_{key}")
    if clicked:
        st.session_state["page"] = key
    # 활성 표시(텍스트만 빨간/굵게)
    if st.session_state["page"] == key:
        st.sidebar.markdown(f"<div style='font-weight:800;color:#ff4b4b'>{show}</div>", unsafe_allow_html=True)

st.sidebar.markdown("### 메뉴")
menu_btn("📅 스케줄", "schedule")
menu_btn("✍️ 세션",   "session")
menu_btn("👥 멤버",    "member")
menu_btn("📋 리포트", "report")
menu_btn("🍒",       "cherry", emoji_only=True)

# --- 사이드바: 수동 백업/복원 ---
st.sidebar.markdown("---")
st.sidebar.markdown("**📦 수동 백업/복원**")
if st.sidebar.button("ZIP 내보내기", key="zip_export"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in [MEMBERS_CSV, SESSIONS_CSV, SCHEDULE_CSV, EX_DB_JSON, VISIT_CSV]:
            if p.exists():
                z.writestr(p.name, p.read_bytes())
    st.sidebar.download_button("⬇️ 다운로드", data=buf.getvalue(), file_name="pilates_backup.zip", mime="application/zip", use_container_width=True)
up = st.sidebar.file_uploader("ZIP 복원", type=["zip"], key="zip_restore")
if up is not None:
    with zipfile.ZipFile(up, "r") as z:
        z.extractall(DATA_DIR)
    # 다시 로드
    members  = load_members()
    sessions = load_sessions()
    schedule = load_schedule()
    visit    = load_visit()
    st.sidebar.success("복원 완료!")

# ===============================
# 공통: 작은 컴포넌트
# ===============================
def big_info(msg: str, kind="info"):
    if kind == "warn":
        st.warning(msg)
    elif kind == "error":
        st.error(msg)
    else:
        st.info(msg)

# ===============================
# 📅 스케줄
# ===============================
if st.session_state["page"] == "schedule":
    st.subheader("📅 스케줄")

    # 보기 전환 + 기준일
    top = st.columns([1,1,3])
    with top[0]:
        view_mode = st.radio("보기", ["일","주","월"], horizontal=True, index=1, label_visibility="collapsed", key="sched_view")
    with top[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed", key="sched_base")
    with top[2]:
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

    # 예약 등록 (개인/그룹) — 개인: 멤버 선택 시 지점 자동, 그룹: 지점 직접
    st.markdown("#### ✨ 예약 등록")
    c1 = st.columns([1,1,1,1,1,2])
    with c1[0]:
        sdate = st.date_input("날짜", value=base, key="s_new_date")
    with c1[1]:
        stime = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="s_new_time")
    with c1[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True, key="s_new_type")
    with c1[3]:
        if stype=="개인":
            mname = st.selectbox("이름(개인)", members["이름"].tolist() if not members.empty else [], key="s_new_name")
            # 멤버 기본 지점 자동
            default_site = "F"
            if mname and (mname in members["이름"].values):
                try:
                    default_site = members.loc[members["이름"]==mname, "기본지점"].iloc[0] or "F"
                except Exception:
                    default_site = "F"
            site = default_site
            st.text_input("지점", value=SITE_KR.get(site, site), disabled=True, key="s_new_site_disp")
        else:
            mname = ""
            site = st.selectbox("지점", ["F","R","V"], index=0, key="s_new_site")
    with c1[4]:
        if stype=="개인":
            headcount = 1
            st.number_input("인원(그룹)", 1, 10, value=1, disabled=True, key="s_new_hc_disp")
        else:
            headcount = st.number_input("인원(그룹)", 1, 10, value=2, step=1, key="s_new_hc")
    with c1[5]:
        memo = st.text_input("메모(선택)", key="s_new_memo")

    c2 = st.columns([1,1,3])
    with c2[0]:
        onth = st.checkbox("✨ On the house", key="s_new_free")
    with c2[1]:
        pass
    with c2[2]:
        if st.button("예약 추가", use_container_width=True, key="s_new_add_btn"):
            when = datetime.combine(sdate, stime)
            row = pd.DataFrame([{
                "id": ensure_id(schedule),
                "날짜": when,
                "지점": site,
                "구분": stype,
                "이름": mname if stype=="개인" else "",
                "인원": int(headcount) if stype=="그룹" else 1,
                "레벨": "",   # 스케줄에서는 간소화
                "기구": "",
                "메모": memo,
                "온더하우스": bool(onth),
                "상태": "예약됨"
            }])
            schedule = pd.concat([schedule, row], ignore_index=True)
            save_schedule(schedule)
            st.success("예약이 추가되었습니다.")

    # 기간 뷰
    st.markdown("#### 📋 일정")
    view = schedule[(schedule["날짜"]>=start) & (schedule["날짜"]<end)].copy().sort_values("날짜")
    def _last_personal_summary(member_name: str):
        past = sessions[(sessions["이름"]==member_name)].copy()
        if past.empty:
            return "—"
        past = past.sort_values("날짜", ascending=False)
        last = past.iloc[0]
        # No Show(세션 생성 없이 표시만)인 경우는 🫥
        if str(last.get("사유","")).strip().lower()=="no show" or str(last.get("특이사항","")).strip().lower()=="no show":
            return "🫥"
        # 동작 → 추가동작 → (레벨/기구)
        if last.get("동작(리스트)",""):
            return last["동작(리스트)"]
        if last.get("추가동작",""):
            return last["추가동작"]
        level = str(last.get("레벨","") or "")
        equip = str(last.get("기구","") or "")
        vv = [x for x in [level, equip] if x]
        return " · ".join(vv) if vv else "—"

    if view.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
        for _, r in view.iterrows():
            rid = r["id"]
            dt  = pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")
            chip = tag(SITE_KR.get(r["지점"], r["지점"]), SITE_COLOR.get(r["지점"], "#eee"))
            name_html = f'<b style="font-size:16px">{r["이름"] if r["이름"] else "(그룹)"}</b>'
            free_mark = " · ✨" if bool(r["온더하우스"]) else ""
            title = f'{dt} · {chip} · {name_html}{free_mark}'

            # 상태 뱃지
            st_badge = str(r.get("상태","예약됨"))
            if st_badge == "취소됨":
                badge = '<span style="background:#ccc;color:#666;padding:2px 6px;border-radius:6px;">취소됨</span>'
                title = f"<s>{title}</s>"
            elif st_badge == "No Show":
                badge = '<span style="background:#ffe3e3;color:#d00;padding:2px 6px;border-radius:6px;">No Show</span>'
            elif st_badge == "완료":
                badge = '<span style="background:#e0ffe7;color:#11772a;padding:2px 6px;border-radius:6px;">완료</span>'
            else:
                badge = '<span style="background:#e8f0ff;color:#1849a9;padding:2px 6px;border-radius:6px;">예약됨</span>'

            # 서브라인
            if r["구분"]=="개인" and r["이름"]:
                sub = f'지난 운동: {_last_personal_summary(r["이름"])}'
            else:
                sub = f'그룹 정보: 인원 {int(r.get("인원",1) or 1)}명'
            if r.get("메모"):
                sub += f' · 메모: {r["메모"]}'

            colA, colB, colC, colD = st.columns([3,1,1,1])
            with colA:
                st.markdown(f"{title} {badge}<br><span style='color:#888'>{sub}</span>", unsafe_allow_html=True)

            with colB:
                if st.button("출석", key=f"s_att_{rid}"):
                    gross, net = calc_pay(r["지점"], r["구분"], int(r.get("인원",1) or 1), r.get("이름",""), members)
                    if r.get("온더하우스", False):
                        gross = net = 0.0
                    # 세션 자동 생성
                    sess = pd.DataFrame([{
                        "id": ensure_id(sessions),
                        "날짜": r["날짜"],
                        "지점": r["지점"],
                        "구분": r["구분"],
                        "이름": r["이름"],
                        "인원": int(r.get("인원",1) or 1),
                        "레벨": "",
                        "기구": "",
                        "동작(리스트)": "",
                        "추가동작": "",
                        "특이사항": "",
                        "숙제": "",
                        "메모": r.get("메모",""),
                        "취소": False,
                        "사유": "",
                        "분": 50,
                        "온더하우스": bool(r.get("온더하우스", False)),
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)

                    # 차감(개인 & ✨아닐 때)
                    if (r["구분"]=="개인") and r["이름"] and (r["이름"] in members["이름"].values) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(remain)
                        save_members(members)

                    schedule.loc[schedule["id"]==rid, "상태"] = "완료"
                    save_schedule(schedule)
                    st.experimental_rerun()

            with colC:
                if st.button("취소", key=f"s_can_{rid}"):
                    schedule.loc[schedule["id"]==rid, "상태"] = "취소됨"
                    save_schedule(schedule)
                    st.experimental_rerun()

            with colD:
                if st.button("No Show", key=f"s_ns_{rid}"):
                    # 세션 생성하지 않음(정책). 단, 차감/페이는 🍒에서 집계(스케줄 기반)
                    if (r["구분"]=="개인") and r["이름"] and (r["이름"] in members["이름"].values) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(remain)
                        save_members(members)
                    schedule.loc[schedule["id"]==rid, "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

    # iCal 내보내기
    st.divider()
    st.subheader("📤 iCal(.ics) 내보내기")
    exclude_cancel = st.checkbox("취소된 일정 제외", value=True, key="ics_excl")
    export_df = view.copy()
    if not export_df.empty:
        if "상태" in export_df.columns and exclude_cancel:
            export_df = export_df[export_df["상태"]!="취소됨"]
    if export_df.empty:
        st.caption("내보낼 일정이 없습니다.")
    else:
        ics_bytes = build_ics_from_df(export_df)
        filename = f"schedule_{view_mode}_{base.strftime('%Y%m%d')}.ics"
        st.download_button("⬇️ iCal 파일 다운로드", data=ics_bytes, file_name=filename, mime="text/calendar", use_container_width=True, key="ics_dl")

# ===============================
# ✍️ 세션
# - 개인: 다중 기구 + 기구별 동작 멀티선택(선택 유지)
# - 그룹: 동작/추가동작/특이사항 X, 메모만
# ===============================
elif st.session_state["page"] == "session":
    st.subheader("✍️ 세션 기록")

    # 날짜/시간(과거 포함 가능)
    c0 = st.columns([1,1,1])
    with c0[0]:
        s_day = st.date_input("날짜", value=date.today(), key="sess_day")
    with c0[1]:
        s_time = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="sess_time")
    with c0[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True, key="sess_type")

    # 공통 입력
    c1 = st.columns([1,1,1,1])
    with c1[0]:
        if stype=="개인":
            member_name = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [], key="sess_member")
        else:
            member_name = ""
    with c1[1]:
        # 개인: 멤버 기본지점 자동 / 그룹: 직접 선택
        if stype=="개인":
            default_site = "F"
            if member_name and (member_name in members["이름"].values):
                default_site = members.loc[members["이름"]==member_name, "기본지점"].iloc[0] or "F"
            site = default_site
            st.text_input("지점", value=SITE_KR.get(site, site), disabled=True, key="sess_site_disp")
        else:
            site = st.selectbox("지점(F/R/V)", SITES, index=0, key="sess_site")
    with c1[2]:
        if stype=="개인":
            headcount = 1
            st.number_input("인원(그룹)", 1, 10, value=1, disabled=True, key="sess_hc_disp")
        else:
            headcount = st.number_input("인원(그룹)", 1, 10, value=2, step=1, key="sess_hc")
    with c1[3]:
        minutes = st.number_input("수업 분", 10, 180, 50, 5, key="sess_min")

    # 개인 — 다중 기구 + 기구별 동작 선택(상태 유지)
    if "per_equip_moves" not in st.session_state:
        st.session_state["per_equip_moves"] = {}  # {equip: [moves]}
    if stype=="개인":
        # 기구 선택(다중): ex_db 키 사용
        all_equips = [k for k in ex_db.keys()]
        equip_sel = st.multiselect("기구 선택(복수)", options=sorted(all_equips), key="sess_equips")
        # 기구별 동작 선택 멀티박스
        for eq in equip_sel:
            if eq not in st.session_state["per_equip_moves"]:
                st.session_state["per_equip_moves"][eq] = []
            sel = st.multiselect(
                f"{eq} 동작 선택",
                options=ex_db.get(eq, []),
                default=st.session_state["per_equip_moves"][eq],
                key=f"s_moves_{eq}"
            )
            st.session_state["per_equip_moves"][eq] = sel

        # 추가 입력
        c2 = st.columns([1,1,2])
        with c2[0]:
            spec_note = st.text_input("특이사항", key="sess_spec")
        with c2[1]:
            homework  = st.text_input("숙제", key="sess_home")
        with c2[2]:
            memo      = st.text_input("메모", key="sess_memo")
    else:
        # 그룹 — 간단 입력(메모만)
        spec_note = ""
        homework  = ""
        memo      = st.text_input("메모(그룹)", key="sess_memo_group")
        equip_sel = []
        st.session_state["per_equip_moves"] = {}

    # 저장
    if st.button("세션 기록 저장", key="sess_save"):
        when = datetime.combine(s_day, s_time)

        # 동작 합치기(개인만)
        if stype=="개인":
            pieces = []
            for eq, moves in st.session_state["per_equip_moves"].items():
                for m in moves:
                    pieces.append(f"{eq} · {m}")
            move_text = "; ".join(pieces)
        else:
            move_text = ""

        # 페이 계산 (V는 0, ✨는 세션 화면에서 입력 안 하므로 항상 False로 둠)
        gross, net = calc_pay(site, stype, int(headcount), member_name, members)

        row = pd.DataFrame([{
            "id": ensure_id(sessions),
            "날짜": when,
            "지점": site,
            "구분": stype,
            "이름": member_name if stype=="개인" else "",
            "인원": int(headcount) if stype=="그룹" else 1,
            "레벨": "",                      # 세션 화면은 레벨/기구 자유
            "기구": ", ".join(equip_sel) if stype=="개인" else "",
            "동작(리스트)": move_text,
            "추가동작": "",                 # 필요 시 여기에 자유 입력칸 추가 가능
            "특이사항": spec_note,
            "숙제": homework,
            "메모": memo,
            "취소": False,
            "사유": "",
            "분": int(minutes),
            "온더하우스": False,           # 스케줄에서만 ✨사용
            "페이(총)": float(gross),
            "페이(실수령)": float(net)
        }])
        sessions = pd.concat([sessions, row], ignore_index=True)
        save_sessions(sessions)

        # 개인 & ✨아닐 때 차감(세션 화면에서는 ✨없으므로 차감 O)
        if (stype=="개인") and member_name and (member_name in members["이름"].values):
            idx = members.index[members["이름"]==member_name][0]
            remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
            members.loc[idx,"남은횟수"] = str(remain)
            save_members(members)

        st.success("세션 기록이 저장되었습니다.")

    # 최근 세션 (페이 컬럼 숨기지 않고 그대로 표출해도 무방)
    st.markdown("#### 📑 최근 세션")
    if sessions.empty:
        big_info("세션이 없습니다.")
    else:
        v = sessions.sort_values("날짜", ascending=False).copy()
        v["날짜"] = pd.to_datetime(v["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(v, use_container_width=True, hide_index=True)

# ===============================
# 👥 멤버
# - 신규/수정/재등록 분리 탭
# - 전화번호 중복 경고
# - 듀엣(👭🏻) 체크 → 회원유형=듀엣
# ===============================
elif st.session_state["page"] == "member":
    st.subheader("👥 멤버")
    tab_new, tab_edit, tab_re = st.tabs(["신규 등록","수정","재등록"])

    # --- 신규 등록 ---
    with tab_new:
        n1, n2 = st.columns([1,1])
        with n1:
            name = st.text_input("이름", key="m_new_name")
            phone = st.text_input("연락처(선택)", placeholder="010-0000-0000", key="m_new_phone")
            is_duet = st.checkbox("👭🏻 듀엣", key="m_new_duet")
        with n2:
            site = st.selectbox("기본지점(F/R)", ["F","R"], index=0, key="m_new_site")
            reg_date = st.date_input("등록일", value=date.today(), key="m_new_reg")
            init_cnt = st.number_input("초기 등록 횟수", 0, 200, 0, 1, key="m_new_init")
        note = st.text_input("메모(선택)", key="m_new_note")

        # 중복 전화번호 경고
        if phone and (members[(members["연락처"]==phone)].shape[0] > 0):
            st.error("⚠️ 동일한 전화번호가 이미 존재합니다.")

        if st.button("신규 등록", key="m_new_btn"):
            if not name.strip():
                st.error("이름을 입력하세요.")
            else:
                ty = "듀엣" if is_duet else "일반"
                row = pd.DataFrame([{
                    "id": ensure_id(members),
                    "이름": name.strip(),
                    "연락처": phone.strip(),
                    "기본지점": site,
                    "등록일": reg_date.isoformat(),
                    "총등록": str(int(init_cnt)),
                    "남은횟수": str(int(init_cnt)),
                    "회원유형": ty,
                    "메모": note.strip(),
                    "재등록횟수": "0",
                    "최근재등록일": ""
                }])
                members = pd.concat([members, row], ignore_index=True)
                save_members(members)
                st.success("신규 등록 완료!")

    # --- 수정 ---
    with tab_edit:
        if members.empty:
            big_info("멤버가 없습니다.")
        else:
            sel = st.selectbox("회원 선택", members["이름"].tolist(), key="m_edit_sel")
            i = members.index[members["이름"]==sel][0]
            e1, e2 = st.columns([1,1])
            with e1:
                name = st.text_input("이름", value=members.loc[i,"이름"], key="m_edit_name")
                phone = st.text_input("연락처(선택)", value=members.loc[i,"연락처"], key="m_edit_phone")
                duet = st.checkbox("👭🏻 듀엣", value=(members.loc[i,"회원유형"]=="듀엣"), key="m_edit_duet")
            with e2:
                site = st.selectbox("기본지점(F/R)", ["F","R"], index=["F","R"].index(members.loc[i,"기본지점"]), key="m_edit_site")
                reg_date = st.date_input("등록일", value=pd.to_datetime(members.loc[i,"등록일"], errors="coerce", utc=False).date() if members.loc[i,"등록일"] else date.today(), key="m_edit_reg")
            note = st.text_input("메모(선택)", value=members.loc[i,"메모"], key="m_edit_note")

            # 중복 전화번호 경고
            if phone and (members[(members["연락처"]==phone) & (members["이름"]!=name)].shape[0] > 0):
                st.error("⚠️ 동일한 전화번호가 이미 존재합니다.")

            if st.button("저장", key="m_edit_save"):
                members.loc[i, ["이름","연락처","기본지점","등록일","메모","회원유형"]] = [
                    name.strip(), phone.strip(), site, reg_date.isoformat(), note.strip(), ("듀엣" if duet else "일반")
                ]
                save_members(members)
                st.success("수정 완료")

            st.markdown("---")
            del_name = st.selectbox("삭제 대상", members["이름"].tolist(), key="m_del_sel")
            if st.button("멤버 삭제", key="m_del_btn"):
                members = members[members["이름"]!=del_name].reset_index(drop=True)
                save_members(members)
                st.success(f"{del_name} 삭제 완료")

    # --- 재등록 ---
    with tab_re:
        if members.empty:
            big_info("멤버가 없습니다.")
        else:
            who = st.selectbox("재등록 회원", members["이름"].tolist(), key="m_re_sel")
            add_cnt = st.number_input("추가 횟수(+)", 0, 200, 0, 1, key="m_re_cnt")
            if st.button("재등록 반영", key="m_re_do"):
                i = members.index[members["이름"]==who][0]
                members.loc[i,"총등록"]   = str(int(float(members.loc[i,"총등록"] or 0)) + int(add_cnt))
                members.loc[i,"남은횟수"] = str(int(float(members.loc[i,"남은횟수"] or 0)) + int(add_cnt))
                members.loc[i,"재등록횟수"] = str(int(float(members.loc[i,"재등록횟수"] or 0)) + 1)
                members.loc[i,"최근재등록일"] = date.today().isoformat()
                save_members(members)
                st.success(f"{who} 재등록 +{int(add_cnt)}회 반영")

    st.markdown("#### 📋 현재 멤버")
    if members.empty:
        big_info("등록된 멤버가 없습니다.")
    else:
        show = members.copy()
        for c in ["등록일","최근재등록일"]:
            show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
        st.dataframe(show, use_container_width=True, hide_index=True)

# ===============================
# 📋 리포트 — 회원 동작 Top5
# ===============================
elif st.session_state["page"] == "report":
    st.subheader("📋 리포트 (회원 동작 Top5)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        df = sessions.copy()
        df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
        months = sorted(df["YM"].unique(), reverse=True)
        msel = st.selectbox("월 선택", months, key="rep_month")
        names = sorted([x for x in df["이름"].dropna().astype(str).unique() if x.strip()])
        nsel = st.selectbox("회원 선택", names, key="rep_name")

        cur = df[(df["YM"]==msel) & (df["이름"]==nsel)].copy()
        moves = []
        for x in cur["동작(리스트)"].dropna():
            for part in str(x).split(";"):
                p = part.strip()
                if p:
                    moves.append(p)
        if not moves:
            st.caption("해당 월 동작 기록이 없습니다.")
        else:
            s = pd.Series(moves).value_counts().head(5).reset_index()
            s.columns = ["동작","횟수"]
            st.dataframe(s, use_container_width=True, hide_index=True)

# ===============================
# 🍒 — PIN 잠금 / 수입
# - 세션 실수령 + 스케줄 No Show 수입 + 방문 수입(수기)
# - 지점/개인/그룹 카운트
# ===============================
elif st.session_state["page"] == "cherry":
    st.subheader("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****", key="cherry_pin")
        if st.button("열기", key="cherry_open"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        # 방문 수입 입력 폼 (숫자 + 메모 빈칸 가능)
        st.markdown("### 🗂 방문 수입 기록(개별)")
        v1, v2, v3 = st.columns([1,1,2])
        with v1:
            v_day = st.date_input("날짜", value=date.today(), key="visit_day")
        with v2:
            v_amt = st.number_input("금액(원)", 0, 5_000_000, 0, 1000, key="visit_amt")
        with v3:
            v_memo = st.text_input("메모(선택)", key="visit_memo")
        if st.button("추가", key="visit_add"):
            row = pd.DataFrame([{
                "날짜": v_day.isoformat(),
                "금액": str(int(v_amt)),
                "메모": v_memo.strip()
            }])
            visit = pd.concat([visit, row], ignore_index=True)
            save_visit(visit)
            st.success("방문 수입이 추가되었습니다.")

        if not visit.empty:
            vshow = visit.copy()
            vshow["날짜"] = pd.to_datetime(vshow["날짜"]).dt.date.astype(str)
            vshow = vshow.sort_values("날짜", ascending=False)
            st.dataframe(vshow, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 수입 집계: 세션 + No Show(스케줄) + 방문수입
        ses = sessions.copy()
        ses["YM"] = pd.to_datetime(ses["날짜"]).dt.strftime("%Y-%m")
        ses["Y"]  = pd.to_datetime(ses["날짜"]).dt.year
        ses_net   = ses["페이(실수령)"].fillna(0).astype(float)

        # 스케줄 No Show의 수입(✨면 0, 아니면 리유/플로우 규칙으로 계산 → V는 0)
        sch_ns = schedule[schedule["상태"]=="No Show"].copy()
        if not sch_ns.empty:
            ns_net = []
            for _, r in sch_ns.iterrows():
                g, n = calc_pay(r["지점"], r["구분"], int(r.get("인원",1) or 1), r.get("이름",""), members)
                if bool(r.get("온더하우스", False)):
                    n = 0.0
                ns_net.append(n)
            sch_ns["net"] = ns_net
            sch_ns["YM"]  = pd.to_datetime(sch_ns["날짜"]).dt.strftime("%Y-%m")
            sch_ns["Y"]   = pd.to_datetime(sch_ns["날짜"]).dt.year
        else:
            sch_ns = pd.DataFrame(columns=["YM","Y","net"])

        # 방문 수입
        v_df = visit.copy()
        if not v_df.empty:
            v_df["YM"] = pd.to_datetime(v_df["날짜"]).dt.strftime("%Y-%m")
            v_df["Y"]  = pd.to_datetime(v_df["날짜"]).dt.year
            v_df["금액"] = v_df["금액"].astype(str).str.replace(",","").astype(float)
        else:
            v_df = pd.DataFrame(columns=["YM","Y","금액"])

        # 월별 합계
        month_ses = ses.groupby("YM")["페이(실수령)"].sum().reset_index().rename(columns={"페이(실수령)":"세션"})
        month_ns  = sch_ns.groupby("YM")["net"].sum().reset_index().rename(columns={"net":"NoShow"}) if not sch_ns.empty else pd.DataFrame(columns=["YM","NoShow"])
        month_v   = v_df.groupby("YM")["금액"].sum().reset_index().rename(columns={"금액":"방문"}) if not v_df.empty else pd.DataFrame(columns=["YM","방문"])

        month = month_ses.merge(month_ns, on="YM", how="outer").merge(month_v, on="YM", how="outer").fillna(0.0)
        for c in ["세션","NoShow","방문"]:
            if c in month.columns: month[c] = month[c].astype(float)
            else: month[c] = 0.0
        month["합계"] = (month["세션"] + month["NoShow"] + month["방문"]).astype(int)

        # 연도 합계
        year_ses = ses.groupby("Y")["페이(실수령)"].sum().reset_index().rename(columns={"페이(실수령)":"세션"})
        year_ns  = sch_ns.groupby("Y")["net"].sum().reset_index().rename(columns={"net":"NoShow"}) if not sch_ns.empty else pd.DataFrame(columns=["Y","NoShow"])
        year_v   = v_df.groupby("Y")["금액"].sum().reset_index().rename(columns={"금액":"방문"}) if not v_df.empty else pd.DataFrame(columns=["Y","방문"])

        year = year_ses.merge(year_ns, on="Y", how="outer").merge(year_v, on="Y", how="outer").fillna(0.0)
        for c in ["세션","NoShow","방문"]:
            if c in year.columns: year[c] = year[c].astype(float)
            else: year[c] = 0.0
        year["합계"] = (year["세션"] + year["NoShow"] + year["방문"]).astype(int)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**월별 실수령 합계(세션+NoShow+방문)**")
            st.dataframe(month.sort_values("YM", ascending=False), use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**연도별 실수령 합계(세션+NoShow+방문)**")
            st.dataframe(year.sort_values("Y", ascending=False), use_container_width=True, hide_index=True)

        # 지점별 월간 건수(개인/그룹 각각, 세션 + 스케줄 전체)
        st.markdown("**지점별 월간 건수(개인/그룹)**")
        ss = sessions.copy()
        ss["YM"] = pd.to_datetime(ss["날짜"]).dt.strftime("%Y-%m")
        sch_all = schedule.copy()
        sch_all["YM"] = pd.to_datetime(sch_all["날짜"]).dt.strftime("%Y-%m")

        def pivot_counts(df, label):
            if df.empty:
                return pd.DataFrame(columns=["YM","구분","F","R","V","출처"])
            tmp = df.groupby(["YM","구분","지점"]).size().reset_index(name="cnt")
            pivot = tmp.pivot_table(index=["YM","구분"], columns="지점", values="cnt", fill_value=0).reset_index()
            for s in SITES:
                if s not in pivot.columns: pivot[s]=0
            pivot = pivot[["YM","구분","F","R","V"]]
            pivot["출처"] = label
            return pivot

        sess_cnt = pivot_counts(ss[["YM","구분","지점"]], "세션")
        sch_cnt  = pivot_counts(sch_all[["YM","구분","지점"]], "스케줄(전체)")
        out = pd.concat([sess_cnt, sch_cnt], ignore_index=True).sort_values(["YM","구분","출처"], ascending=[False,True,True])
        st.dataframe(out, use_container_width=True, hide_index=True)
