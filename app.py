# app.py
import os, json, io, zipfile
from pathlib import Path
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, List

import pandas as pd
import streamlit as st

# ==========================
# Google Sheets 연결
# ==========================
import gspread
from google.oauth2.service_account import Credentials

# 서비스 계정 키 파일 경로
SERVICE_ACCOUNT_FILE = "pilatesmanager-gcp.json"

# 접근 권한 (Google Sheets)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 인증
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# 네 구글시트 ID (URL에서 따오기)
# 예: https://docs.google.com/spreadsheets/d/📌이부분📌/edit#gid=0
SHEET_ID = "1GgGZOhUqBn_atzguVljj0svt2pxBWYVCmAGG4ib9Roc"

# 시트 열기
sheet = client.open_by_key(SHEET_ID).sheet1

# ==========================
# Page config & favicon
# ==========================
DATA_DIR = Path(".")
FAVICON = DATA_DIR / "favicon.png"
if FAVICON.exists():
    st.set_page_config(page_title="Pilates Manager", page_icon=str(FAVICON), layout="wide")
else:
    st.set_page_config(page_title="Pilates Manager", page_icon="✨", layout="wide")

# ==========================
# Constants & paths
# ==========================
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
SCHEDULE_CSV = DATA_DIR / "schedule.csv"
EX_DB_JSON   = DATA_DIR / "exercise_db.json"
SETTINGS_JSON= DATA_DIR / "settings.json"   # 방문 기본 실수령 등

CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES      = ["F", "R", "V"]  # Flow / Ryu / Visit
SITE_KR    = {"F": "플로우", "R": "리유", "V": "방문"}
SITE_COLOR = {"F": "#d9f0ff", "R": "#eeeeee", "V": "#e9fbe9"}
SITE_LABEL = {"F":"F", "R":"R", "V":"V"}

# ==========================
# Defaults
# ==========================
EX_DB_DEFAULT: Dict[str, List[str]] = {
    # 최소 예시(원하는 대로 exercise_db.json로 교체 가능)
    "Mat": ["The Hundred","Roll Up","Roll Over"],
    "Reformer": ["Footwork - Toes","Hundred","Overhead"],
    "Cadillac": ["Breathing","Spread Eagle","Pull Ups"],
    "Wunda chair": ["Footwork - Toes","Push Down","Pull Up"],
    "Ladder Barrel": ["Swan","Horseback","Side Stretch"],
    "Spine Corrector": ["Teaser","Hip Circles","Swan"],
    "Pedi-pull": ["Chest Expansion","Arm Circles"],
    "Magic Circle": ["Mat - Hundred","Chin Press"],
    "Arm Chair": ["Basics","Boxing","Hug"],
    "Electric chair": ["Pumping","Going Up - Front"],
    "Small Barrel": ["Arm Series - Circles","Leg Series - Circles"],
    "Foot Corrector": ["Press Down - Toes on Top","Massage"],
    "Toe Corrector": ["Seated - External Rotation"],
    "Neck Stretcher": ["Seated - Flat Back"],
    "기타": []
}

DEFAULT_SETTINGS = {
    "visit_default_net": 0,   # 방문 기본 실수령(원) - 🍒에서 설정
    "visit_memo": ""          # 메모(선택)
}

# ==========================
# Helpers
# ==========================
def _site_coerce(v:str)->str:
    s=str(v).strip()
    if s in SITES: return s
    if s in ["플로우","Flow","flow"]: return "F"
    if s in ["리유","Ryu","ryu"]:     return "R"
    if s in ["방문","Visit","visit"]: return "V"
    return "F"

def ensure_df_columns(df: pd.DataFrame, cols: List[str], num_cols: List[str]|None=None, bool_cols: List[str]|None=None) -> pd.DataFrame:
    num_cols = num_cols or []
    bool_cols= bool_cols or []
    for c in cols:
        if c not in df.columns:
            if c in num_cols:
                df[c] = 0
            elif c in bool_cols:
                df[c] = False
            else:
                df[c] = ""
    return df

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)

    # Settings
    if not SETTINGS_JSON.exists():
        SETTINGS_JSON.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=2), encoding="utf-8")

    # Members
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
            "메모","재등록횟수","최근재등록일","듀엣","듀엣상대"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # Sessions
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제","메모",
            "취소","사유","분","온더하우스","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    # Schedule
    if not SCHEDULE_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","메모","온더하우스","상태"  # 상태: 예약됨/완료/취소됨/No Show
        ]).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

    # EX DB
    if not EX_DB_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)

    # Upgrade existing
    # members
    mem = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    mem = ensure_df_columns(mem,
        ["id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형","메모","재등록횟수","최근재등록일","듀엣","듀엣상대"]
    )
    mem["기본지점"] = mem["기본지점"].apply(_site_coerce)
    mem.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # sessions
    ses = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    ses = ensure_df_columns(ses,
        ["id","날짜","지점","구분","이름","인원","레벨","기구","동작(리스트)","추가동작","특이사항","숙제","메모",
         "취소","사유","분","온더하우스","페이(총)","페이(실수령)"]
    )
    ses["지점"] = ses["지점"].apply(_site_coerce)
    ses.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    # schedule
    sch = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    sch = ensure_df_columns(sch,
        ["id","날짜","지점","구분","이름","인원","메모","온더하우스","상태"]
    )
    sch["지점"] = sch["지점"].apply(_site_coerce)
    sch.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(d: dict):
    SETTINGS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

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
        df["인원"] = pd.to_numeric(df["인원"], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_schedule(df: pd.DataFrame):
    x = df.copy()
    if not x.empty:
        x["날짜"] = pd.to_datetime(x["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    x.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_DB_JSON, typ="series")
        return {k:list(v) for k,v in raw.items()}
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_DB_JSON, force_ascii=False)

def ensure_id(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "1"
    try:
        return str(int(df["id"].astype(str).astype(int).max()) + 1)
    except Exception:
        return str(len(df) + 1)

def big_info(msg: str):
    st.info(msg)

# -------------------
# Pay rules
# -------------------
def calc_pay(site: str, session_type: str, headcount: int, settings: dict, is_duet: bool=False) -> tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 35,000, 3.3% 공제
    R(리유): 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣 35,000 (공제없음)
    V(방문): 🍒 설정의 'visit_default_net'
    """
    site = _site_coerce(site)
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net   = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            if is_duet:
                gross = net = 35000.0
            else:
                gross = net = 30000.0
        else:
            if headcount == 2:   # 그룹 2명 (듀엣과 다름)
                gross = net = 30000.0
            elif headcount == 3:
                gross = net = 40000.0
            elif headcount == 1:
                gross = net = 25000.0
            else:
                gross = net = 30000.0
    else:  # V
        net = float(settings.get("visit_default_net", 0) or 0)
        gross = net
    return gross, net

# -------------------
# ICS Export
# -------------------
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
        loc   = SITE_KR.get(_site_coerce(str(r.get("지점",""))), "")
        memo  = str(r.get("메모","") or "")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{r.get('id','')}@pilatesapp",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"LOCATION:{loc}",
            f"DESCRIPTION:{memo.replace('\\n','\\\\n')}",
            "END:VEVENT"
        ]

    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines)).encode("utf-8")

# ==========================
# Init
# ==========================
ensure_files()
settings = load_settings()
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
ex_db    = load_ex_db()

# ==========================
# Sidebar Navigation (no bullets, button style, active text only)
# ==========================
if "page" not in st.session_state:
    st.session_state["page"] = "schedule"

st.markdown("""
<style>
div[data-testid="stSidebar"] button {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  text-align: left !important;
  padding: 6px 4px !important;
  font-size: 18px !important;
}
.nav-active { font-weight: 800; color: #ff4b4b; padding: 6px 4px; }
</style>
""", unsafe_allow_html=True)

def nav_item(label: str, key: str, emoji_only=False):
    show = label if not emoji_only else label.split()[0]
    if st.session_state["page"] == key:
        st.sidebar.markdown(f"<div class='nav-active'>{show}</div>", unsafe_allow_html=True)
    else:
        if st.sidebar.button(show, key=f"nav_{key}"):
            st.session_state["page"] = key

st.sidebar.markdown("### 메뉴")
nav_item("📅 스케줄", "schedule")
nav_item("✍️ 세션",   "session")
nav_item("👥 멤버",    "member")
nav_item("📋 리포트", "report")
nav_item("🍒",       "cherry", emoji_only=True)
st.sidebar.markdown("---")

# Manual backup/restore in sidebar bottom
st.sidebar.markdown("#### 🗄️ 백업/복원")
def make_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in [MEMBERS_CSV, SESSIONS_CSV, SCHEDULE_CSV, EX_DB_JSON, SETTINGS_JSON]:
            if p.exists():
                z.writestr(p.name, p.read_bytes())
    buf.seek(0)
    return buf.read()

st.sidebar.download_button("⬇️ ZIP 백업", data=make_zip_bytes(),
                           file_name="pilates_backup.zip", mime="application/zip",
                           use_container_width=True, key="dl_backup")

up = st.sidebar.file_uploader("⬆️ ZIP 복원", type=["zip"], key="ul_restore", accept_multiple_files=False)
if up is not None:
    try:
        with zipfile.ZipFile(up, "r") as z:
            for name in z.namelist():
                if name in {MEMBERS_CSV.name, SESSIONS_CSV.name, EX_DB_JSON.name, SETTINGS_JSON.name, SCHEDULE_CSV.name}:
                    (DATA_DIR / name).write_bytes(z.read(name))
        st.sidebar.success("복원 완료! 페이지를 다시 실행하면 적용됩니다.")
    except Exception as e:
        st.sidebar.error(f"복원 실패: {e}")

# ==========================
# Schedule Page
# ==========================
if st.session_state["page"] == "schedule":
    st.subheader("📅 스케줄")

    # Range controls
    cols = st.columns([1,1,2,1])
    with cols[0]:
        view_mode = st.radio("보기", ["일","주","월"], horizontal=True, index=1, label_visibility="collapsed", key="sch_view")
    with cols[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed", key="sch_base")
    base_dt = datetime.combine(base, time.min)
    if view_mode=="일":
        start, end = base_dt, base_dt + timedelta(days=1)
    elif view_mode=="주":
        start = base_dt - timedelta(days=base_dt.weekday())
        end   = start + timedelta(days=7)
    else:
        start = base_dt.replace(day=1)
        end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

    # 빠른 잔여횟수 뱃지
    def remain_badge(name: str) -> str:
        if not name or name not in set(members["이름"]): return ""
        try:
            left = int(float(members.loc[members["이름"]==name,"남은횟수"].iloc[0] or 0))
        except Exception:
            left = 0
        if left <= 0:  return " <span style='color:#d00;font-weight:700'>(0회)</span>"
        if left == 1:  return " <span style='color:#d00;font-weight:700'>(❗1회)</span>"
        if left == 2:  return " <span style='color:#d98200;font-weight:700'>(⚠️2회)</span>"
        return ""

    # 예약 추가
    st.markdown("#### ✨ 예약 추가")
    c = st.columns([1,1,1,1,2])
    with c[0]:
        sdate = st.date_input("날짜", value=base, key="s_new_date")
    with c[1]:
        stime = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="s_new_time")
    with c[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True, key="s_new_type")
    with c[3]:
        onth = st.checkbox("✨ On the house", key="s_new_onth")
    with c[4]:
        memo = st.text_input("메모(선택)", key="s_new_memo")

    if stype=="개인":
        cc = st.columns([2,1])
        with cc[0]:
            mname = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [], key="s_new_member")
        if mname and (mname in members["이름"].values):
            default_site = members.loc[members["이름"]==mname,"기본지점"].iloc[0] or "F"
        else:
            default_site = "F"
        with cc[1]:
            site = st.selectbox("지점(F/R/V)", SITES, index=SITES.index(default_site), key="s_new_site_personal")
        headcount = 1
    else:
        mname = ""
        site = st.selectbox("지점(F/R/V)", SITES, index=0, key="s_new_site_group")
        headcount = st.number_input("인원(그룹)", 1, 20, 2, 1, key="s_new_headcount")

    if st.button("예약 추가", use_container_width=True, key="s_new_add_btn"):
        when = datetime.combine(sdate, stime)
        row = pd.DataFrame([{
            "id": ensure_id(schedule),
            "날짜": when,
            "지점": site,
            "구분": stype,
            "이름": mname if stype=="개인" else "",
            "인원": int(headcount),
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

    def last_personal_summary(member_name: str):
        past = sessions[(sessions["이름"]==member_name)].copy()
        if past.empty:
            return "—"
        past = past.sort_values("날짜", ascending=False)
        last = past.iloc[0]
        if str(last.get("사유","")).strip().lower()=="no show" or str(last.get("특이사항","")).strip().lower()=="no show":
            return "🫥"
        if last.get("동작(리스트)",""):
            return last["동작(리스트)"]
        if last.get("추가동작",""):
            return last["추가동작"]
        lvl = str(last.get("레벨","") or "")
        eqp = str(last.get("기구","") or "")
        if lvl or eqp:
            return " · ".join([x for x in [lvl, eqp] if x])
        return "—"

    if view.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
        for _, r in view.iterrows():
            dt = pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")
            chip = f"<span style='background:{SITE_COLOR.get(r['지점'],'#eee')};padding:2px 8px;border-radius:8px;font-size:12px'>{SITE_LABEL.get(r['지점'],r['지점'])}</span>"
            name_html = f"<b style='font-size:16px'>{r['이름'] if r['이름'] else '(그룹)'}</b>"
            free = " · ✨" if r.get("온더하우스", False) else ""
            rm = remain_badge(r["이름"]) if r["구분"]=="개인" else ""
            title = f"{dt} · {chip} · {name_html}{free}{rm}"

            status = str(r.get("상태","예약됨"))
            if status == "취소됨":
                badge = '<span style="background:#ccc;color:#666;padding:2px 6px;border-radius:6px;">취소됨</span>'
                title = f"<s>{title}</s>"
            elif status == "No Show":
                badge = '<span style="background:#ffe3e3;color:#d00;padding:2px 6px;border-radius:6px;">No Show</span>'
            elif status == "완료":
                badge = '<span style="background:#e0ffe7;color:#11772a;padding:2px 6px;border-radius:6px;">완료</span>'
            else:
                badge = '<span style="background:#e8f0ff;color:#1849a9;padding:2px 6px;border-radius:6px;">예약됨</span>'

            if r["구분"]=="개인" and r["이름"]:
                sub = f"지난 운동: {last_personal_summary(r['이름'])}"
            else:
                sub = f"그룹 정보: 인원 {int(r.get('인원',0) or 0)}명"
            if r.get("메모"):
                sub += f" · 메모: {r['메모']}"

            colA,colB,colC,colD = st.columns([3,1,1,1])
            with colA:
                st.markdown(f"{title} {badge}<br><span style='color:#888'>{sub}</span>", unsafe_allow_html=True)

            rid = r["id"]
            # 출석
            with colB:
                if st.button("출석", key=f"sch_att_{rid}"):
                    # 듀엣 여부 (개인만)
                    is_duet = False
                    if r["구분"]=="개인" and r["이름"] in set(members["이름"]):
                        try:
                            is_duet = str(members.loc[members["이름"]==r["이름"], "듀엣"].iloc[0]).lower() in ["true","1","y","yes"]
                        except Exception:
                            pass
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"] or 1), settings, is_duet=is_duet)
                    if r.get("온더하우스", False):
                        gross = net = 0.0
                    sess = pd.DataFrame([{
                        "id": ensure_id(sessions),
                        "날짜": r["날짜"],
                        "지점": r["지점"],
                        "구분": r["구분"],
                        "이름": r["이름"],
                        "인원": int(r["인원"] or 1),
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
                    # 차감 (개인 + 무료 아님)
                    if (r["구분"]=="개인") and r["이름"] and (r["이름"] in set(members["이름"])) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        left = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(left)
                        save_members(members)
                    schedule.loc[schedule["id"]==rid, "상태"] = "완료"
                    save_schedule(schedule)
                    st.experimental_rerun()
            # 취소
            with colC:
                if st.button("취소", key=f"sch_can_{rid}"):
                    schedule.loc[schedule["id"]==rid, "상태"] = "취소됨"
                    save_schedule(schedule)
                    st.experimental_rerun()
            # No Show
            with colD:
                if st.button("No Show", key=f"sch_ns_{rid}"):
                    # 세션은 만들지 않음. 차감/페이는 🍒에서 합산(스케줄 NoShow 반영)
                    if (r["구분"]=="개인") and r["이름"] and (r["이름"] in set(members["이름"])) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        left = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(left)
                        save_members(members)
                    schedule.loc[schedule["id"]==rid, "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

    # ICS export
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
        st.download_button("⬇️ iCal 파일 다운로드", data=ics_bytes, file_name=filename, mime="text/calendar", use_container_width=True, key="ics_btn")

# ==========================
# Session Page
# ==========================
# app.py
import os, json, io, zipfile
from pathlib import Path
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, List

import pandas as pd
import streamlit as st

# ==========================
# Page config & favicon
# ==========================
DATA_DIR = Path(".")
FAVICON = DATA_DIR / "favicon.png"
if FAVICON.exists():
    st.set_page_config(page_title="Pilates Manager", page_icon=str(FAVICON), layout="wide")
else:
    st.set_page_config(page_title="Pilates Manager", page_icon="✨", layout="wide")

# ==========================
# Constants & paths
# ==========================
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
SCHEDULE_CSV = DATA_DIR / "schedule.csv"
EX_DB_JSON   = DATA_DIR / "exercise_db.json"
SETTINGS_JSON= DATA_DIR / "settings.json"   # 방문 기본 실수령 등

CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES      = ["F", "R", "V"]  # Flow / Ryu / Visit
SITE_KR    = {"F": "플로우", "R": "리유", "V": "방문"}
SITE_COLOR = {"F": "#d9f0ff", "R": "#eeeeee", "V": "#e9fbe9"}
SITE_LABEL = {"F":"F", "R":"R", "V":"V"}

# ==========================
# Defaults
# ==========================
EX_DB_DEFAULT: Dict[str, List[str]] = {
    # 최소 예시(원하는 대로 exercise_db.json로 교체 가능)
    "Mat": ["The Hundred","Roll Up","Roll Over"],
    "Reformer": ["Footwork - Toes","Hundred","Overhead"],
    "Cadillac": ["Breathing","Spread Eagle","Pull Ups"],
    "Wunda chair": ["Footwork - Toes","Push Down","Pull Up"],
    "Ladder Barrel": ["Swan","Horseback","Side Stretch"],
    "Spine Corrector": ["Teaser","Hip Circles","Swan"],
    "Pedi-pull": ["Chest Expansion","Arm Circles"],
    "Magic Circle": ["Mat - Hundred","Chin Press"],
    "Arm Chair": ["Basics","Boxing","Hug"],
    "Electric chair": ["Pumping","Going Up - Front"],
    "Small Barrel": ["Arm Series - Circles","Leg Series - Circles"],
    "Foot Corrector": ["Press Down - Toes on Top","Massage"],
    "Toe Corrector": ["Seated - External Rotation"],
    "Neck Stretcher": ["Seated - Flat Back"],
    "기타": []
}

DEFAULT_SETTINGS = {
    "visit_default_net": 0,   # 방문 기본 실수령(원) - 🍒에서 설정
    "visit_memo": ""          # 메모(선택)
}

# ==========================
# Helpers
# ==========================
def _site_coerce(v:str)->str:
    s=str(v).strip()
    if s in SITES: return s
    if s in ["플로우","Flow","flow"]: return "F"
    if s in ["리유","Ryu","ryu"]:     return "R"
    if s in ["방문","Visit","visit"]: return "V"
    return "F"

def ensure_df_columns(df: pd.DataFrame, cols: List[str], num_cols: List[str]|None=None, bool_cols: List[str]|None=None) -> pd.DataFrame:
    num_cols = num_cols or []
    bool_cols= bool_cols or []
    for c in cols:
        if c not in df.columns:
            if c in num_cols:
                df[c] = 0
            elif c in bool_cols:
                df[c] = False
            else:
                df[c] = ""
    return df

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)

    # Settings
    if not SETTINGS_JSON.exists():
        SETTINGS_JSON.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=2), encoding="utf-8")

    # Members
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
            "메모","재등록횟수","최근재등록일","듀엣","듀엣상대"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # Sessions
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제","메모",
            "취소","사유","분","온더하우스","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    # Schedule
    if not SCHEDULE_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","메모","온더하우스","상태"  # 상태: 예약됨/완료/취소됨/No Show
        ]).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

    # EX DB
    if not EX_DB_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)

    # Upgrade existing
    # members
    mem = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    mem = ensure_df_columns(mem,
        ["id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형","메모","재등록횟수","최근재등록일","듀엣","듀엣상대"]
    )
    mem["기본지점"] = mem["기본지점"].apply(_site_coerce)
    mem.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # sessions
    ses = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    ses = ensure_df_columns(ses,
        ["id","날짜","지점","구분","이름","인원","레벨","기구","동작(리스트)","추가동작","특이사항","숙제","메모",
         "취소","사유","분","온더하우스","페이(총)","페이(실수령)"]
    )
    ses["지점"] = ses["지점"].apply(_site_coerce)
    ses.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    # schedule
    sch = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    sch = ensure_df_columns(sch,
        ["id","날짜","지점","구분","이름","인원","메모","온더하우스","상태"]
    )
    sch["지점"] = sch["지점"].apply(_site_coerce)
    sch.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(d: dict):
    SETTINGS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

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
        df["인원"] = pd.to_numeric(df["인원"], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_schedule(df: pd.DataFrame):
    x = df.copy()
    if not x.empty:
        x["날짜"] = pd.to_datetime(x["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    x.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_DB_JSON, typ="series")
        return {k:list(v) for k,v in raw.items()}
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_DB_JSON, force_ascii=False)

def ensure_id(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "1"
    try:
        return str(int(df["id"].astype(str).astype(int).max()) + 1)
    except Exception:
        return str(len(df) + 1)

def big_info(msg: str):
    st.info(msg)

# -------------------
# Pay rules
# -------------------
def calc_pay(site: str, session_type: str, headcount: int, settings: dict, is_duet: bool=False) -> tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 35,000, 3.3% 공제
    R(리유): 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣 35,000 (공제없음)
    V(방문): 🍒 설정의 'visit_default_net'
    """
    site = _site_coerce(site)
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net   = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            if is_duet:
                gross = net = 35000.0
            else:
                gross = net = 30000.0
        else:
            if headcount == 2:   # 그룹 2명 (듀엣과 다름)
                gross = net = 30000.0
            elif headcount == 3:
                gross = net = 40000.0
            elif headcount == 1:
                gross = net = 25000.0
            else:
                gross = net = 30000.0
    else:  # V
        net = float(settings.get("visit_default_net", 0) or 0)
        gross = net
    return gross, net

# -------------------
# ICS Export
# -------------------
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
        loc   = SITE_KR.get(_site_coerce(str(r.get("지점",""))), "")
        memo  = str(r.get("메모","") or "")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{r.get('id','')}@pilatesapp",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"LOCATION:{loc}",
            f"DESCRIPTION:{memo.replace('\\n','\\\\n')}",
            "END:VEVENT"
        ]

    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines)).encode("utf-8")

# ==========================
# Init
# ==========================
ensure_files()
settings = load_settings()
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
ex_db    = load_ex_db()

# ==========================
# Sidebar Navigation (no bullets, button style, active text only)
# ==========================
if "page" not in st.session_state:
    st.session_state["page"] = "schedule"

st.markdown("""
<style>
div[data-testid="stSidebar"] button {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  text-align: left !important;
  padding: 6px 4px !important;
  font-size: 18px !important;
}
.nav-active { font-weight: 800; color: #ff4b4b; padding: 6px 4px; }
</style>
""", unsafe_allow_html=True)

def nav_item(label: str, key: str, emoji_only=False):
    show = label if not emoji_only else label.split()[0]
    if st.session_state["page"] == key:
        st.sidebar.markdown(f"<div class='nav-active'>{show}</div>", unsafe_allow_html=True)
    else:
        if st.sidebar.button(show, key=f"nav_{key}"):
            st.session_state["page"] = key

st.sidebar.markdown("### 메뉴")
nav_item("📅 스케줄", "schedule")
nav_item("✍️ 세션",   "session")
nav_item("👥 멤버",    "member")
nav_item("📋 리포트", "report")
nav_item("🍒",       "cherry", emoji_only=True)
st.sidebar.markdown("---")

# Manual backup/restore in sidebar bottom
st.sidebar.markdown("#### 🗄️ 백업/복원")
def make_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in [MEMBERS_CSV, SESSIONS_CSV, SCHEDULE_CSV, EX_DB_JSON, SETTINGS_JSON]:
            if p.exists():
                z.writestr(p.name, p.read_bytes())
    buf.seek(0)
    return buf.read()

st.sidebar.download_button("⬇️ ZIP 백업", data=make_zip_bytes(),
                           file_name="pilates_backup.zip", mime="application/zip",
                           use_container_width=True, key="dl_backup")

up = st.sidebar.file_uploader("⬆️ ZIP 복원", type=["zip"], key="ul_restore", accept_multiple_files=False)
if up is not None:
    try:
        with zipfile.ZipFile(up, "r") as z:
            for name in z.namelist():
                if name in {MEMBERS_CSV.name, SESSIONS_CSV.name, EX_DB_JSON.name, SETTINGS_JSON.name, SCHEDULE_CSV.name}:
                    (DATA_DIR / name).write_bytes(z.read(name))
        st.sidebar.success("복원 완료! 페이지를 다시 실행하면 적용됩니다.")
    except Exception as e:
        st.sidebar.error(f"복원 실패: {e}")

# ==========================
# Schedule Page
# ==========================
if st.session_state["page"] == "schedule":
    st.subheader("📅 스케줄")

    # Range controls
    cols = st.columns([1,1,2,1])
    with cols[0]:
        view_mode = st.radio("보기", ["일","주","월"], horizontal=True, index=1, label_visibility="collapsed", key="sch_view")
    with cols[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed", key="sch_base")
    base_dt = datetime.combine(base, time.min)
    if view_mode=="일":
        start, end = base_dt, base_dt + timedelta(days=1)
    elif view_mode=="주":
        start = base_dt - timedelta(days=base_dt.weekday())
        end   = start + timedelta(days=7)
    else:
        start = base_dt.replace(day=1)
        end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

    # 빠른 잔여횟수 뱃지
    def remain_badge(name: str) -> str:
        if not name or name not in set(members["이름"]): return ""
        try:
            left = int(float(members.loc[members["이름"]==name,"남은횟수"].iloc[0] or 0))
        except Exception:
            left = 0
        if left <= 0:  return " <span style='color:#d00;font-weight:700'>(0회)</span>"
        if left == 1:  return " <span style='color:#d00;font-weight:700'>(❗1회)</span>"
        if left == 2:  return " <span style='color:#d98200;font-weight:700'>(⚠️2회)</span>"
        return ""

    # 예약 추가
    st.markdown("#### ✨ 예약 추가")
    c = st.columns([1,1,1,1,2])
    with c[0]:
        sdate = st.date_input("날짜", value=base, key="s_new_date")
    with c[1]:
        stime = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="s_new_time")
    with c[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True, key="s_new_type")
    with c[3]:
        onth = st.checkbox("✨ On the house", key="s_new_onth")
    with c[4]:
        memo = st.text_input("메모(선택)", key="s_new_memo")

    if stype=="개인":
        cc = st.columns([2,1])
        with cc[0]:
            mname = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [], key="s_new_member")
        if mname and (mname in members["이름"].values):
            default_site = members.loc[members["이름"]==mname,"기본지점"].iloc[0] or "F"
        else:
            default_site = "F"
        with cc[1]:
            site = st.selectbox("지점(F/R/V)", SITES, index=SITES.index(default_site), key="s_new_site_personal")
        headcount = 1
    else:
        mname = ""
        site = st.selectbox("지점(F/R/V)", SITES, index=0, key="s_new_site_group")
        headcount = st.number_input("인원(그룹)", 1, 20, 2, 1, key="s_new_headcount")

    if st.button("예약 추가", use_container_width=True, key="s_new_add_btn"):
        when = datetime.combine(sdate, stime)
        row = pd.DataFrame([{
            "id": ensure_id(schedule),
            "날짜": when,
            "지점": site,
            "구분": stype,
            "이름": mname if stype=="개인" else "",
            "인원": int(headcount),
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

    def last_personal_summary(member_name: str):
        past = sessions[(sessions["이름"]==member_name)].copy()
        if past.empty:
            return "—"
        past = past.sort_values("날짜", ascending=False)
        last = past.iloc[0]
        if str(last.get("사유","")).strip().lower()=="no show" or str(last.get("특이사항","")).strip().lower()=="no show":
            return "🫥"
        if last.get("동작(리스트)",""):
            return last["동작(리스트)"]
        if last.get("추가동작",""):
            return last["추가동작"]
        lvl = str(last.get("레벨","") or "")
        eqp = str(last.get("기구","") or "")
        if lvl or eqp:
            return " · ".join([x for x in [lvl, eqp] if x])
        return "—"

    if view.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
        for _, r in view.iterrows():
            dt = pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")
            chip = f"<span style='background:{SITE_COLOR.get(r['지점'],'#eee')};padding:2px 8px;border-radius:8px;font-size:12px'>{SITE_LABEL.get(r['지점'],r['지점'])}</span>"
            name_html = f"<b style='font-size:16px'>{r['이름'] if r['이름'] else '(그룹)'}</b>"
            free = " · ✨" if r.get("온더하우스", False) else ""
            rm = remain_badge(r["이름"]) if r["구분"]=="개인" else ""
            title = f"{dt} · {chip} · {name_html}{free}{rm}"

            status = str(r.get("상태","예약됨"))
            if status == "취소됨":
                badge = '<span style="background:#ccc;color:#666;padding:2px 6px;border-radius:6px;">취소됨</span>'
                title = f"<s>{title}</s>"
            elif status == "No Show":
                badge = '<span style="background:#ffe3e3;color:#d00;padding:2px 6px;border-radius:6px;">No Show</span>'
            elif status == "완료":
                badge = '<span style="background:#e0ffe7;color:#11772a;padding:2px 6px;border-radius:6px;">완료</span>'
            else:
                badge = '<span style="background:#e8f0ff;color:#1849a9;padding:2px 6px;border-radius:6px;">예약됨</span>'

            if r["구분"]=="개인" and r["이름"]:
                sub = f"지난 운동: {last_personal_summary(r['이름'])}"
            else:
                sub = f"그룹 정보: 인원 {int(r.get('인원',0) or 0)}명"
            if r.get("메모"):
                sub += f" · 메모: {r['메모']}"

            colA,colB,colC,colD = st.columns([3,1,1,1])
            with colA:
                st.markdown(f"{title} {badge}<br><span style='color:#888'>{sub}</span>", unsafe_allow_html=True)

            rid = r["id"]
            # 출석
            with colB:
                if st.button("출석", key=f"sch_att_{rid}"):
                    # 듀엣 여부 (개인만)
                    is_duet = False
                    if r["구분"]=="개인" and r["이름"] in set(members["이름"]):
                        try:
                            is_duet = str(members.loc[members["이름"]==r["이름"], "듀엣"].iloc[0]).lower() in ["true","1","y","yes"]
                        except Exception:
                            pass
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"] or 1), settings, is_duet=is_duet)
                    if r.get("온더하우스", False):
                        gross = net = 0.0
                    sess = pd.DataFrame([{
                        "id": ensure_id(sessions),
                        "날짜": r["날짜"],
                        "지점": r["지점"],
                        "구분": r["구분"],
                        "이름": r["이름"],
                        "인원": int(r["인원"] or 1),
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
                    # 차감 (개인 + 무료 아님)
                    if (r["구분"]=="개인") and r["이름"] and (r["이름"] in set(members["이름"])) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        left = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(left)
                        save_members(members)
                    schedule.loc[schedule["id"]==rid, "상태"] = "완료"
                    save_schedule(schedule)
                    st.experimental_rerun()
            # 취소
            with colC:
                if st.button("취소", key=f"sch_can_{rid}"):
                    schedule.loc[schedule["id"]==rid, "상태"] = "취소됨"
                    save_schedule(schedule)
                    st.experimental_rerun()
            # No Show
            with colD:
                if st.button("No Show", key=f"sch_ns_{rid}"):
                    # 세션은 만들지 않음. 차감/페이는 🍒에서 합산(스케줄 NoShow 반영)
                    if (r["구분"]=="개인") and r["이름"] and (r["이름"] in set(members["이름"])) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        left = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(left)
                        save_members(members)
                    schedule.loc[schedule["id"]==rid, "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

    # ICS export
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
        st.download_button("⬇️ iCal 파일 다운로드", data=ics_bytes, file_name=filename, mime="text/calendar", use_container_width=True, key="ics_btn")

# ==========================
# Session Page
# ==========================
elif st.session_state["page"] == "session":
    st.subheader("✍️ 세션 기록")

    tabs = st.tabs(["개인", "그룹"])

    # ---- 개인 세션 기록 ----
    with tabs[0]:
        mcols = st.columns([2,1,1,1])
        with mcols[0]:
            member = st.selectbox("멤버 선택", members["이름"].tolist(), key="sess_p_name")
        with mcols[1]:
            day = st.date_input("날짜", value=date.today(), key="sess_p_date")
        with mcols[2]:
            tme = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="sess_p_time")
        with mcols[3]:
            default_site = members.loc[members["이름"]==member,"기본지점"].iloc[0] if (member in set(members["이름"])) else "F"
            site = st.selectbox("지점(F/R/V)", SITES, index=SITES.index(default_site), key="sess_p_site")

        equip_sel = st.multiselect("기구 선택(복수)", list(ex_db.keys()), key="sess_p_equips")
        if "moves_by_equip" not in st.session_state:
            st.session_state["moves_by_equip"] = {}
        all_chosen = []
        for eq in equip_sel:
            prev = st.session_state["moves_by_equip"].get(eq, [])
            picked = st.multiselect(f"{eq} 동작", options=sorted(ex_db.get(eq, [])), default=prev, key=f"s_p_moves_{eq}")
            st.session_state["moves_by_equip"][eq] = picked
            all_chosen.extend(picked)

        add_free  = st.text_input("추가 동작(콤마 , 로 구분)", key="sess_p_addfree")
        spec_note = st.text_input("특이사항", key="sess_p_spec")
        homework  = st.text_input("숙제", key="sess_p_home")
        memo      = st.text_area("메모", height=60, key="sess_p_memo")

        if st.button("저장", key="sess_p_save"):
            when = datetime.combine(day, tme)
            is_duet = False
            if member in set(members["이름"]):
                try:
                    is_duet = str(members.loc[members["이름"]==member, "듀엣"].iloc[0]).lower() in ["true","1","y","yes"]
                except Exception:
                    pass
            gross, net = calc_pay(site, "개인", 1, settings, is_duet=is_duet)
            row = pd.DataFrame([{
                "id": ensure_id(sessions),
                "날짜": when,
                "지점": site,
                "구분": "개인",
                "이름": member,
                "인원": 1,
                "레벨": "",
                "기구": ", ".join(equip_sel),
                "동작(리스트)": "; ".join(all_chosen),
                "추가동작": add_free,
                "특이사항": spec_note,
                "숙제": homework,
                "메모": memo,
                "취소": False,
                "사유": "",
                "분": 50,
                "온더하우스": False,
                "페이(총)": float(gross),
                "페이(실수령)": float(net)
            }])
            sessions = pd.concat([sessions, row], ignore_index=True)
            save_sessions(sessions)
            if (member in set(members["이름"])):
                idx = members.index[members["이름"]==member][0]
                left = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                members.loc[idx,"남은횟수"] = str(left)
                save_members(members)
            st.success("개인 세션 저장 완료")

    # ---- 그룹 세션 기록 ----
    with tabs[1]:
        gcols = st.columns([1,1,1,1,1])
        with gcols[0]:
            day = st.date_input("날짜", value=date.today(), key="sess_g_date")
        with gcols[1]:
            tme = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="sess_g_time")
        with gcols[2]:
            site = st.selectbox("지점(F/R/V)", SITES, index=0, key="sess_g_site")
        with gcols[3]:
            headcount = st.number_input("인원", 1, 20, 2, 1, key="sess_g_head")
        with gcols[4]:
            level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"], key="sess_g_level")

        equip = st.selectbox("기구", list(ex_db.keys()), key="sess_g_equip")
        memo  = st.text_area("메모", height=60, key="sess_g_memo")

        if st.button("저장", key="sess_g_save"):
            when = datetime.combine(day, tme)
            gross, net = calc_pay(site, "그룹", int(headcount), settings, is_duet=False)
            row = pd.DataFrame([{
                "id": ensure_id(sessions),
                "날짜": when,
                "지점": site,
                "구분": "그룹",
                "이름": "",
                "인원": int(headcount),
                "레벨": level,
                "기구": equip,
                "동작(리스트)": "",
                "추가동작": "",
                "특이사항": "",
                "숙제": "",
                "메모": memo,
                "취소": False,
                "사유": "",
                "분": 50,
                "온더하우스": False,
                "페이(총)": float(gross),
                "페이(실수령)": float(net)
            }])
            sessions = pd.concat([sessions, row], ignore_index=True)
            save_sessions(sessions)
            st.success("그룹 세션 저장 완료")

    # 최근 세션 (페이 숨김)
    st.markdown("#### 📑 최근 세션")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        view = sessions.sort_values("날짜", ascending=False).copy()
        hide_cols = ["페이(총)","페이(실수령)"]
        show_cols = [c for c in view.columns if c not in hide_cols]
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ==========================
# Member Page
# ==========================
elif st.session_state["page"] == "member":
    st.subheader("👥 멤버 관리")

    tab_new, tab_edit, tab_re = st.tabs(["신규 등록", "수정", "재등록"])

    # 신규 등록
    with tab_new:
        c1,c2 = st.columns([1,1])
        with c1:
            name = st.text_input("이름", key="m_new_name")
            phone= st.text_input("연락처", placeholder="010-0000-0000", key="m_new_phone")
            duet = st.checkbox("👭🏻 듀엣", key="m_new_duet")
            duet_with = st.text_input("듀엣 상대 이름(선택)", key="m_new_duet_with")
        with c2:
            site = st.selectbox("기본지점(F/R/V)", SITES, index=0, key="m_new_site")
            reg_date = st.date_input("등록일", value=date.today(), key="m_new_reg")
            init_cnt = st.number_input("등록 횟수(초기)", 0, 200, 0, 1, key="m_new_init")
        note = st.text_input("메모(선택)", key="m_new_note")

        if st.button("등록", key="m_new_btn"):
            if not name.strip():
                st.error("이름을 입력하세요.")
            elif phone and (members[(members["연락처"]==phone)].shape[0] > 0):
                st.error("동일한 전화번호가 이미 존재합니다.")
            else:
                row = pd.DataFrame([{
                    "id": ensure_id(members), "이름": name.strip(), "연락처": phone.strip(),
                    "기본지점": site, "등록일": reg_date.isoformat(),
                    "총등록": str(int(init_cnt)), "남은횟수": str(int(init_cnt)),
                    "회원유형": "일반", "메모": note,
                    "재등록횟수": "0", "최근재등록일": "",
                    "듀엣": bool(duet), "듀엣상대": duet_with.strip()
                }])
                members = pd.concat([members, row], ignore_index=True)
                save_members(members)
                st.success("신규 등록 완료")

    # 수정
    with tab_edit:
        sel = st.selectbox("회원 선택", members["이름"].tolist() if not members.empty else [], key="m_edit_sel")
        if sel:
            i = members.index[members["이름"]==sel][0]
            c1,c2 = st.columns([1,1])
            with c1:
                name = st.text_input("이름", value=members.loc[i,"이름"], key="m_edit_name")
                phone= st.text_input("연락처", value=members.loc[i,"연락처"], key="m_edit_phone")
                duet = st.checkbox("👭🏻 듀엣", value=str(members.loc[i,"듀엣"]).lower() in ["true","1","y","yes"], key="m_edit_duet")
                duet_with = st.text_input("듀엣 상대 이름", value=members.loc[i,"듀엣상대"], key="m_edit_duet_with")
            with c2:
                site = st.selectbox("기본지점(F/R/V)", SITES, index=SITES.index(members.loc[i,"기본지점"]), key="m_edit_site")
                reg_date = st.date_input("등록일", value=pd.to_datetime(members.loc[i,"등록일"], errors="coerce").date() if members.loc[i]["등록일"] else date.today(), key="m_edit_reg")
            note = st.text_input("메모(선택)", value=members.loc[i,"메모"], key="m_edit_note")

            if st.button("수정 저장", key="m_edit_btn"):
                if phone and (members[(members["연락처"]==phone) & (members["이름"]!=sel)].shape[0] > 0):
                    st.error("동일한 전화번호가 이미 존재합니다.")
                else:
                    members.loc[i, ["이름","연락처","기본지점","등록일","메모","듀엣","듀엣상대"]] = \
                        [name.strip(), phone.strip(), site, reg_date.isoformat(), note, bool(duet), duet_with.strip()]
                    save_members(members)
                    st.success("수정 완료")

    # 재등록
    with tab_re:
        sel = st.selectbox("회원 선택", members["이름"].tolist() if not members.empty else [], key="m_re_sel")
        add_cnt = st.number_input("재등록(+횟수)", 0, 200, 0, 1, key="m_re_cnt")
        if st.button("재등록 반영", key="m_re_btn"):
            if not sel:
                st.error("회원을 선택하세요.")
            else:
                i = members.index[members["이름"]==sel][0]
                members.loc[i,"총등록"]   = str(int(float(members.loc[i,"총등록"] or 0)) + int(add_cnt))
                members.loc[i,"남은횟수"] = str(int(float(members.loc[i,"남은횟수"] or 0)) + int(add_cnt))
                members.loc[i,"재등록횟수"] = str(int(float(members.loc[i,"재등록횟수"] or 0)) + 1)
                members.loc[i,"최근재등록일"] = date.today().isoformat()
                save_members(members)
                st.success("재등록 반영 완료")

    with st.expander("📋 현재 멤버 보기", expanded=False):
        if members.empty:
            big_info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            for c in ["등록일","최근재등록일"]:
                show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)

# ==========================
# Report Page
# ==========================
elif st.session_state["page"] == "report":
    st.subheader("📋 리포트 (회원 동작 Top5 & 추이)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        df = sessions.copy()
        df = df[df["구분"]=="개인"]
        df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
        months = sorted(df["YM"].unique(), reverse=True)
        who = st.selectbox("회원 선택", sorted(set(df["이름"]) - set([""])), key="r_name")
        month = st.selectbox("월 선택", months, key="r_month") if months else None

        if who and month:
            dfm = df[(df["이름"]==who) & (df["YM"]==month)]
            moves = []
            for x in dfm["동작(리스트)"].dropna():
                for part in str(x).split(";"):
                    p = part.strip()
                    if p:
                        moves.append(p)
            st.markdown("**Top5 동작**")
            if moves:
                top = pd.Series(moves).value_counts().head(5).reset_index()
                top.columns = ["동작","횟수"]
                st.dataframe(top, use_container_width=True, hide_index=True)
            else:
                st.caption("해당 월 동작 기록이 없습니다.")

            # 6개월 추이 (상위 3개 동작)
            if moves:
                top_moves = set(pd.Series(moves).value_counts().head(3).index.tolist())
                last6 = (pd.to_datetime(df["날짜"]).dt.to_period("M").astype(str).sort_values().unique())[-6:]
                trend = []
                for ym in last6:
                    sub = df[(df["이름"]==who) & (pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")==ym)]
                    ms = []
                    for x in sub["동작(리스트)"].dropna():
                        ms += [p.strip() for p in str(x).split(";") if p.strip()]
                    row = {"YM": ym}
                    for m in top_moves:
                        row[m] = sum([1 for k in ms if k==m])
                    trend.append(row)
                if trend:
                    tdf = pd.DataFrame(trend).fillna(0)
                    st.markdown("**최근 6개월 추이(상위 3개 동작)**")
                    st.dataframe(tdf, use_container_width=True, hide_index=True)

# ==========================
# Cherry Page
# ==========================
elif st.session_state["page"] == "cherry":
    st.subheader("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****", key="ch_pin")
        if st.button("열기", key="ch_open"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        # 방문 기본 실수령 설정
        st.markdown("#### 방문 기본 실수령(원) 설정")
        vcols = st.columns([1,3])
        with vcols[0]:
            visit_pay = st.number_input("방문 실수령(원)", 0, 2_000_000, int(settings.get("visit_default_net", 0)), 1000, key="ch_visit_pay")
        with vcols[1]:
            visit_memo = st.text_input("메모(선택)", value=settings.get("visit_memo",""), key="ch_visit_memo")
        if st.button("저장", key="ch_save"):
            settings["visit_default_net"] = int(visit_pay)
            settings["visit_memo"] = visit_memo
            save_settings(settings)
            st.success("저장되었습니다.")

        st.markdown("#### 수입 요약")
        if sessions.empty and schedule.empty:
            big_info("데이터가 없습니다.")
        else:
            ses = sessions.copy()
            ses["Y"]  = pd.to_datetime(ses["날짜"]).dt.year
            ses["YM"] = pd.to_datetime(ses["날짜"]).dt.strftime("%Y-%m")

            # No Show 수입(스케줄에서 계산)
            sch_ns = schedule[schedule["상태"]=="No Show"].copy()
            ns_net = []
            for _, r in sch_ns.iterrows():
                gross, net = calc_pay(r["지점"], r["구분"], int(r.get("인원",1) or 1), settings, is_duet=False)
                if r.get("온더하우스", False):
                    net = 0.0
                ns_net.append(net)
            sch_ns["net"] = ns_net
            sch_ns["Y"]   = pd.to_datetime(sch_ns["날짜"]).dt.year
            sch_ns["YM"]  = pd.to_datetime(sch_ns["날짜"]).dt.strftime("%Y-%m")

            month_s = ses.groupby("YM")["페이(실수령)"].sum().astype(float).rename("세션")
            ns_m    = sch_ns.groupby("YM")["net"].sum().rename("NoShow") if not sch_ns.empty else pd.Series(dtype=float)
            month_sum = month_s.to_frame()
            if not ns_m.empty:
                month_sum = month_sum.join(ns_m, how="outer").fillna(0.0)
            else:
                month_sum["NoShow"] = 0.0
            month_sum["합계"] = (month_sum["세션"] + month_sum["NoShow"]).astype(int)
            month_sum = month_sum.reset_index().sort_values("YM", ascending=False)

            year_s = ses.groupby("Y")["페이(실수령)"].sum().astype(float).rename("세션")
            ns_y   = sch_ns.groupby("Y")["net"].sum().rename("NoShow") if not sch_ns.empty else pd.Series(dtype=float)
            year_sum = year_s.to_frame()
            if not ns_y.empty:
                year_sum = year_sum.join(ns_y, how="outer").fillna(0.0)
            else:
                year_sum["NoShow"] = 0.0
            year_sum["합계"] = (year_sum["세션"] + year_sum["NoShow"]).astype(int)
            year_sum = year_sum.reset_index().sort_values("Y", ascending=False)

            c1,c2 = st.columns(2)
            with c1:
                st.markdown("**월별 실수령(세션+NoShow)**")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
                if len(month_sum) >= 2:
                    cur, prev = month_sum.iloc[0]["합계"], month_sum.iloc[1]["합계"]
                    diff = int(cur - prev)
                    st.metric("전월 대비", f"{diff:+,} 원")
            with c2:
                st.markdown("**연도별 실수령(세션+NoShow)**")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            # 지점별 월간 건수(개인/그룹)
            st.markdown("**지점별 월간 건수(개인/그룹)**")
            def piv_counts(df):
                if df.empty:
                    return pd.DataFrame(columns=["YM","구분","F","R","V"])
                tmp = df.groupby(["YM","구분","지점"]).size().reset_index(name="cnt")
                pv = tmp.pivot_table(index=["YM","구분"], columns="지점", values="cnt", fill_value=0).reset_index()
                for s in SITES:
                    if s not in pv.columns: pv[s]=0
                return pv[["YM","구분","F","R","V"]]

            ss = sessions.copy(); ss["YM"] = pd.to_datetime(ss["날짜"]).dt.strftime("%Y-%m")
            sch = schedule.copy(); sch["YM"] = pd.to_datetime(sch["날짜"]).dt.strftime("%Y-%m")
            out = pd.concat([piv_counts(ss), piv_counts(sch)], ignore_index=True).sort_values(["YM","구분"], ascending=[False,True])
            st.dataframe(out, use_container_width=True, hide_index=True)
# ==========================
# Member Page
# ==========================
elif st.session_state["page"] == "member":
    st.subheader("👥 멤버 관리")

    tab_new, tab_edit, tab_re = st.tabs(["신규 등록", "수정", "재등록"])

    # 신규 등록
    with tab_new:
        c1,c2 = st.columns([1,1])
        with c1:
            name = st.text_input("이름", key="m_new_name")
            phone= st.text_input("연락처", placeholder="010-0000-0000", key="m_new_phone")
            duet = st.checkbox("👭🏻 듀엣", key="m_new_duet")
            duet_with = st.text_input("듀엣 상대 이름(선택)", key="m_new_duet_with")
        with c2:
            site = st.selectbox("기본지점(F/R/V)", SITES, index=0, key="m_new_site")
            reg_date = st.date_input("등록일", value=date.today(), key="m_new_reg")
            init_cnt = st.number_input("등록 횟수(초기)", 0, 200, 0, 1, key="m_new_init")
        note = st.text_input("메모(선택)", key="m_new_note")

        if st.button("등록", key="m_new_btn"):
            if not name.strip():
                st.error("이름을 입력하세요.")
            elif phone and (members[(members["연락처"]==phone)].shape[0] > 0):
                st.error("동일한 전화번호가 이미 존재합니다.")
            else:
                row = pd.DataFrame([{
                    "id": ensure_id(members), "이름": name.strip(), "연락처": phone.strip(),
                    "기본지점": site, "등록일": reg_date.isoformat(),
                    "총등록": str(int(init_cnt)), "남은횟수": str(int(init_cnt)),
                    "회원유형": "일반", "메모": note,
                    "재등록횟수": "0", "최근재등록일": "",
                    "듀엣": bool(duet), "듀엣상대": duet_with.strip()
                }])
                members = pd.concat([members, row], ignore_index=True)
                save_members(members)
                st.success("신규 등록 완료")

    # 수정
    with tab_edit:
        sel = st.selectbox("회원 선택", members["이름"].tolist() if not members.empty else [], key="m_edit_sel")
        if sel:
            i = members.index[members["이름"]==sel][0]
            c1,c2 = st.columns([1,1])
            with c1:
                name = st.text_input("이름", value=members.loc[i,"이름"], key="m_edit_name")
                phone= st.text_input("연락처", value=members.loc[i,"연락처"], key="m_edit_phone")
                duet = st.checkbox("👭🏻 듀엣", value=str(members.loc[i,"듀엣"]).lower() in ["true","1","y","yes"], key="m_edit_duet")
                duet_with = st.text_input("듀엣 상대 이름", value=members.loc[i,"듀엣상대"], key="m_edit_duet_with")
            with c2:
                site = st.selectbox("기본지점(F/R/V)", SITES, index=SITES.index(members.loc[i,"기본지점"]), key="m_edit_site")
                reg_date = st.date_input("등록일", value=pd.to_datetime(members.loc[i,"등록일"], errors="coerce").date() if members.loc[i]["등록일"] else date.today(), key="m_edit_reg")
            note = st.text_input("메모(선택)", value=members.loc[i,"메모"], key="m_edit_note")

            if st.button("수정 저장", key="m_edit_btn"):
                if phone and (members[(members["연락처"]==phone) & (members["이름"]!=sel)].shape[0] > 0):
                    st.error("동일한 전화번호가 이미 존재합니다.")
                else:
                    members.loc[i, ["이름","연락처","기본지점","등록일","메모","듀엣","듀엣상대"]] = \
                        [name.strip(), phone.strip(), site, reg_date.isoformat(), note, bool(duet), duet_with.strip()]
                    save_members(members)
                    st.success("수정 완료")

    # 재등록
    with tab_re:
        sel = st.selectbox("회원 선택", members["이름"].tolist() if not members.empty else [], key="m_re_sel")
        add_cnt = st.number_input("재등록(+횟수)", 0, 200, 0, 1, key="m_re_cnt")
        if st.button("재등록 반영", key="m_re_btn"):
            if not sel:
                st.error("회원을 선택하세요.")
            else:
                i = members.index[members["이름"]==sel][0]
                members.loc[i,"총등록"]   = str(int(float(members.loc[i,"총등록"] or 0)) + int(add_cnt))
                members.loc[i,"남은횟수"] = str(int(float(members.loc[i,"남은횟수"] or 0)) + int(add_cnt))
                members.loc[i,"재등록횟수"] = str(int(float(members.loc[i,"재등록횟수"] or 0)) + 1)
                members.loc[i,"최근재등록일"] = date.today().isoformat()
                save_members(members)
                st.success("재등록 반영 완료")

    with st.expander("📋 현재 멤버 보기", expanded=False):
        if members.empty:
            big_info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            for c in ["등록일","최근재등록일"]:
                show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)

# ==========================
# Report Page
# ==========================
elif st.session_state["page"] == "report":
    st.subheader("📋 리포트 (회원 동작 Top5 & 추이)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        df = sessions.copy()
        df = df[df["구분"]=="개인"]
        df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
        months = sorted(df["YM"].unique(), reverse=True)
        who = st.selectbox("회원 선택", sorted(set(df["이름"]) - set([""])), key="r_name")
        month = st.selectbox("월 선택", months, key="r_month") if months else None

        if who and month:
            dfm = df[(df["이름"]==who) & (df["YM"]==month)]
            moves = []
            for x in dfm["동작(리스트)"].dropna():
                for part in str(x).split(";"):
                    p = part.strip()
                    if p:
                        moves.append(p)
            st.markdown("**Top5 동작**")
            if moves:
                top = pd.Series(moves).value_counts().head(5).reset_index()
                top.columns = ["동작","횟수"]
                st.dataframe(top, use_container_width=True, hide_index=True)
            else:
                st.caption("해당 월 동작 기록이 없습니다.")

            # 6개월 추이 (상위 3개 동작)
            if moves:
                top_moves = set(pd.Series(moves).value_counts().head(3).index.tolist())
                last6 = (pd.to_datetime(df["날짜"]).dt.to_period("M").astype(str).sort_values().unique())[-6:]
                trend = []
                for ym in last6:
                    sub = df[(df["이름"]==who) & (pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")==ym)]
                    ms = []
                    for x in sub["동작(리스트)"].dropna():
                        ms += [p.strip() for p in str(x).split(";") if p.strip()]
                    row = {"YM": ym}
                    for m in top_moves:
                        row[m] = sum([1 for k in ms if k==m])
                    trend.append(row)
                if trend:
                    tdf = pd.DataFrame(trend).fillna(0)
                    st.markdown("**최근 6개월 추이(상위 3개 동작)**")
                    st.dataframe(tdf, use_container_width=True, hide_index=True)

# ==========================
# Cherry Page
# ==========================
elif st.session_state["page"] == "cherry":
    st.subheader("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****", key="ch_pin")
        if st.button("열기", key="ch_open"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        # 방문 기본 실수령 설정
        st.markdown("#### 방문 기본 실수령(원) 설정")
        vcols = st.columns([1,3])
        with vcols[0]:
            visit_pay = st.number_input("방문 실수령(원)", 0, 2_000_000, int(settings.get("visit_default_net", 0)), 1000, key="ch_visit_pay")
        with vcols[1]:
            visit_memo = st.text_input("메모(선택)", value=settings.get("visit_memo",""), key="ch_visit_memo")
        if st.button("저장", key="ch_save"):
            settings["visit_default_net"] = int(visit_pay)
            settings["visit_memo"] = visit_memo
            save_settings(settings)
            st.success("저장되었습니다.")

        st.markdown("#### 수입 요약")
        if sessions.empty and schedule.empty:
            big_info("데이터가 없습니다.")
        else:
            ses = sessions.copy()
            ses["Y"]  = pd.to_datetime(ses["날짜"]).dt.year
            ses["YM"] = pd.to_datetime(ses["날짜"]).dt.strftime("%Y-%m")

            # No Show 수입(스케줄에서 계산)
            sch_ns = schedule[schedule["상태"]=="No Show"].copy()
            ns_net = []
            for _, r in sch_ns.iterrows():
                gross, net = calc_pay(r["지점"], r["구분"], int(r.get("인원",1) or 1), settings, is_duet=False)
                if r.get("온더하우스", False):
                    net = 0.0
                ns_net.append(net)
            sch_ns["net"] = ns_net
            sch_ns["Y"]   = pd.to_datetime(sch_ns["날짜"]).dt.year
            sch_ns["YM"]  = pd.to_datetime(sch_ns["날짜"]).dt.strftime("%Y-%m")

            month_s = ses.groupby("YM")["페이(실수령)"].sum().astype(float).rename("세션")
            ns_m    = sch_ns.groupby("YM")["net"].sum().rename("NoShow") if not sch_ns.empty else pd.Series(dtype=float)
            month_sum = month_s.to_frame()
            if not ns_m.empty:
                month_sum = month_sum.join(ns_m, how="outer").fillna(0.0)
            else:
                month_sum["NoShow"] = 0.0
            month_sum["합계"] = (month_sum["세션"] + month_sum["NoShow"]).astype(int)
            month_sum = month_sum.reset_index().sort_values("YM", ascending=False)

            year_s = ses.groupby("Y")["페이(실수령)"].sum().astype(float).rename("세션")
            ns_y   = sch_ns.groupby("Y")["net"].sum().rename("NoShow") if not sch_ns.empty else pd.Series(dtype=float)
            year_sum = year_s.to_frame()
            if not ns_y.empty:
                year_sum = year_sum.join(ns_y, how="outer").fillna(0.0)
            else:
                year_sum["NoShow"] = 0.0
            year_sum["합계"] = (year_sum["세션"] + year_sum["NoShow"]).astype(int)
            year_sum = year_sum.reset_index().sort_values("Y", ascending=False)

            c1,c2 = st.columns(2)
            with c1:
                st.markdown("**월별 실수령(세션+NoShow)**")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
                if len(month_sum) >= 2:
                    cur, prev = month_sum.iloc[0]["합계"], month_sum.iloc[1]["합계"]
                    diff = int(cur - prev)
                    st.metric("전월 대비", f"{diff:+,} 원")
            with c2:
                st.markdown("**연도별 실수령(세션+NoShow)**")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            # 지점별 월간 건수(개인/그룹)
            st.markdown("**지점별 월간 건수(개인/그룹)**")
            def piv_counts(df):
                if df.empty:
                    return pd.DataFrame(columns=["YM","구분","F","R","V"])
                tmp = df.groupby(["YM","구분","지점"]).size().reset_index(name="cnt")
                pv = tmp.pivot_table(index=["YM","구분"], columns="지점", values="cnt", fill_value=0).reset_index()
                for s in SITES:
                    if s not in pv.columns: pv[s]=0
                return pv[["YM","구분","F","R","V"]]

            ss = sessions.copy(); ss["YM"] = pd.to_datetime(ss["날짜"]).dt.strftime("%Y-%m")
            sch = schedule.copy(); sch["YM"] = pd.to_datetime(sch["날짜"]).dt.strftime("%Y-%m")
            out = pd.concat([piv_counts(ss), piv_counts(sch)], ignore_index=True).sort_values(["YM","구분"], ascending=[False,True])
            st.dataframe(out, use_container_width=True, hide_index=True)


