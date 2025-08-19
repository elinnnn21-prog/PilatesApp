# app.py
import os
from pathlib import Path
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, List

import pandas as pd
import streamlit as st

# ======================================
# 기본 설정
# ======================================
st.set_page_config(page_title="Pilates Manager", page_icon="✨", layout="wide")

DATA_DIR     = Path(".")
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
SCHEDULE_CSV = DATA_DIR / "schedule.csv"
EX_DB_JSON   = DATA_DIR / "exercise_db.json"

CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES      = ["F", "R", "V"]  # Flow / Ryu / Visit
SITE_KR    = {"F": "플로우", "R": "리유", "V": "방문"}
SITE_COLOR = {"F": "#d9f0ff", "R": "#eeeeee", "V": "#e9fbe9"}

# ---- NAV 기본값 (버튼 네비 사용 시) ----
if "page" not in st.session_state:
    st.session_state.page = "schedule"   # 첫 페이지는 스케줄

# ---- menu 호환(옛 코드용) ----
# st.session_state.page 값 -> 한국어 라벨로 매핑해서 menu 변수에 넣어줌
_key2label = {
    "schedule": "스케줄",
    "session":  "세션",
    "member":   "멤버",
    "report":   "리포트",
    "cherry":   "🍒",
}
# 혹시 버튼 콜백에서 page_label을 직접 저장하는 버전도 대비
menu = st.session_state.get("page_label")
if not menu:
    menu = _key2label.get(st.session_state.get("page", "schedule"), "스케줄")
    st.session_state["page_label"] = menu
    
# ---------------- 기본 동작 DB(초기) ----------------
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat": [
        "The Hundred","Roll Up","Roll Over","Single Leg Circles","Rolling Like a Ball",
        "Single Leg Stretch","Double Leg Stretch","Single Straight Leg Stretch",
        "Double Straight Leg Stretch","Criss Cross","Spine Stretch Forward",
        "Open Leg Rocker","Corkscrew","Saw","Swan","Single Leg Kicks","Double Leg Kicks",
        "Thigh Stretch Mat","Neck Pull","High Scissors","High Bicycle","Shoulder Bridge",
        "Spine Twist","Jackknife","Side Kick Series -Front/Back -Up/Down -Small Circles -Big Circles",
        "Teaser 1","Teaser 2","Teaser 3","Hip Circles","Swimming","Leg Pull Front (Down)",
        "Leg Pull Back (Up)","Kneeling Side Kicks","Side Bend","Boomerang","Seal","Crab",
        "Rocking","Balance Control - Roll Over","Push Ups"
    ],
    "Reformer":[
        "Footwork -Toes -Arches -Heels -Tendon Stretch","Hundred","Overhead","Coordination",
        "Rowing -Into the Sternum -90 Degrees -From the Chest -From the Hips -Shaving -Hug",
        "Long Box -Pull Straps -T Straps -Backstroke -Teaser -Breaststroke -Horseback",
        "Long Stretch -Long Stretch -Down Stretch -Up Stretch -Elephant -Elephant One Leg Back -Long Back Stretch",
        "Stomach Massage -Round -Hands Back -Reach Up -Twist","Short Box -Round Back -Flat Back -Side to Side -Twist -Around the World -Tree",
        "Short Spine Massage","Semi Circle","Chest Expansion","Thigh Stretch","Arm Circles",
        "Snake","Twist","Corkscrew","Tick Tock","Balance Control Step Off","Long Spine Massage",
        "Feet in Straps -Frogs -Leg Circles","Knee Stretch -Round -Arched -Knees Off","Running",
        "Pelvic Lift","Push Up Front","Push Up Back","Side Splits","Front Splits","Russian Splits"
    ],
    "Cadillac":[
        "Breathing","Spread Eagle","Pull Ups","Hanging Pull Ups","Twist Pull Ups",
        "Half Hanging / Full Hanging / Hanging Twists","Squirrel / Flying Squirrel",
        "Rollback Bar - Roll Down - One Arm Roll Down - Breathing - Chest Expansion - Thigh Stretch - Long Back Stretch - Rolling In and Out - Rolling Stomach Massage",
        "Rollback Bar(Standing) - Squats - Side Arm - Shaving - Bicep Curls - Zip Up",
        "Leg Springs - Circles - Walking - Beats - Bicycle - Small Circles - Frogs - In the Air(Circles / Walking / Beats / Bicycle / Airplane)",
        "Side Leg Springs - Front/Back - Up/Down - Small Circles - Big Circles - Bicycle",
        "Arm Springs - Flying Eagle - Press Down - Circles - Triceps - Press Down Side",
        "Arm Springs Standing - Squats - Hug - Boxing - Shaving - Butterfly - Side Arm - Fencing",
        "Push Thru Bar - Tower - Monkey - Teaser - Reverse Push Thru - Mermaid Sitting - Swan - Shoulder Roll Down - Push Thru",
        "Monkey on a Stick","Semi Circle","Ballet/Leg Stretches - Front - Back - Side"
    ],
    "Wunda chair":[
        "Footwork - Toes - Arches - Heels - Tendon Stretch","Push Down","Push Down One Arm",
        "Pull Up","Spine Stretch Forward","Teaser - on Floor","Swan","Swan One Arm",
        "Teaser - on Top","Mermaid - Seated","Arm Frog","Mermaid - Kneeling","Twist 1",
        "Tendon Stretch","Table Top","Mountain Climb","Going Up Front","Going Up Side",
        "Push Down One Arm Side","Pumping - Standing behind / Washer Woman","Frog - Facing Chair",
        "Frog - Facing Out","Leg Press Down - Front","Backward Arms","Push Up - Top",
        "Push Up - Bottom","Flying Eagle"
    ],
    "Ladder Barrel":[
        "Ballet/Leg Stretches - Front (ladder)","Ballet/Leg Stretches - Front",
        "Ballet/Leg Stretches - Front with Bent Leg","Ballet/Leg Stretches - Side",
        "Ballet/Leg Stretches - Side with Bent Leg","Ballet/Leg Stretches - Back",
        "Ballet/Leg Stretches - Back with Bent Leg","Swan","Horseback",
        "Backbend (standing outside barrel)","Side Stretch",
        "Short Box - Round Back - Flat Back - Side to Side - Twist - Around the World - Tree",
        "Back Walkover (Ad)","Side Sit Ups","Handstand","Jumping Off the Stomach"
    ],
    "Spine Corrector":[
        "Arm Series - Stretch with Bar - Circles",
        "Leg Series - Circles - Scissors - Walking - Bicycle - Beats - Rolling In and Out",
        "Leg Circles Onto Head","Teaser","Hip Circles","Swan","Grasshopper","Rocking",
        "Swimming","Side Sit up","Shoulder Bridge"
    ],
    "Pedi-pull":[
        "Chest Expansion","Arm Circles",
        "Knee Bends - Facing Out - Arabesque(Front/Side/Back)","Centering"
    ],
    "Magic Circle":[
        "Mat - Hundred - Roll Up - Roll Over - Double Leg Stretch - Open Leg Rocker - Corkscrew - Neck Pull - Jackknife - Side Kicks - Teaser 1,2,3 - Hip Circles",
        "Sitting PrePilates - Above Knees - Between Feet",
        "Standing - Arm Series - Chest Expansion - Leg Series",
        "Chin Press","Forehead Press"
    ],
    "Arm Chair":[
        "Basics","Arm Lower & Lift","Boxing","Circles","Shaving","Hug","Sparklers","Chest Expansion"
    ],
    "Electric chair":[
        "Pumping","Pumping - One Leg","Pumping - Feet Hip Width","Going Up - Front",
        "Going Up - Side","Standing Pumping - Front","Standing Pumping - Side","Standing Pumping - Crossover",
        "Achilles Stretch","Press Up - Back","Press Up - Front"
    ],
    "Small Barrel":[
        "Arm Series - Circles - One Arm Up/Down - Hug - Stretch with Bar",
        "Leg Series - Circles - Small Circles - Walking - Beats - Scissors - Bicycle - Frog to V - Helicopter - Rolling In and Out - Swan - Rocking"
    ],
    "Foot Corrector":[
        "Press Down - Toes on Top","Press Down - Heel on Top","Toes","Arch","Heel","Massage"
    ],
    "Toe Corrector":[
        "Seated(One Leg & Both) - External Rotation from Hip - Flex/Point"
    ],
    "Neck Stretcher":[
        "Seated - Flat Back - Spine Stretch Forward"
    ],
    "기타": []
}

# ======================================
# 유틸
# ======================================
def _site_coerce(v:str)->str:
    s=str(v).strip()
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
            "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
            "메모","재등록횟수","최근재등록일","방문실수령(원)"
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
            "특이사항","온더하우스","상태"  # 상태: 예약됨/완료/취소됨/No Show
        ]).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")
    if not EX_DB_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_DB_JSON, force_ascii=False)

    # 업그레이드: 기존 CSV에 누락 컬럼/지점값 보정
    mem = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    mem = ensure_df_columns(mem, [
        "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
        "메모","재등록횟수","최근재등록일","방문실수령(원)"
    ])
    mem["기본지점"]=mem["기본지점"].apply(_site_coerce)
    mem.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    ses = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    ses = ensure_df_columns(ses, [
        "id","날짜","지점","구분","이름","인원","레벨","기구",
        "동작(리스트)","추가동작","특이사항","숙제","메모",
        "취소","사유","분","온더하우스","페이(총)","페이(실수령)"
    ])
    ses["지점"]=ses["지점"].apply(_site_coerce)
    ses.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    sch = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    sch = ensure_df_columns(sch, [
        "id","날짜","지점","구분","이름","인원","레벨","기구",
        "특이사항","온더하우스","상태"
    ])
    sch["지점"]=sch["지점"].apply(_site_coerce)
    sch.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def load_members() -> pd.DataFrame:
    df = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return df

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    x=df.copy()
    if not x.empty:
        x["날짜"]=pd.to_datetime(x["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    x.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_schedule() -> pd.DataFrame:
    df = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원"]:
            df[c]=pd.to_numeric(df[c], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_schedule(df: pd.DataFrame):
    x=df.copy()
    if not x.empty:
        x["날짜"]=pd.to_datetime(x["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
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
    return str((0 if df is None or df.empty else df["id"].astype(str).astype(int).max()) + 1)

def calc_pay(site: str, session_type: str, headcount: int, mname: str|None=None, members: pd.DataFrame|None=None) -> tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 35,000, 3.3% 공제
    R(리유): 개인 30,000 / 3명 40,000 / 2명 35,000(듀엣) / 1명 25,000 (공제없음)
    V(방문): 멤버의 '방문실수령(원)' 사용 (없으면 0)
    """
    site = _site_coerce(site)
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net   = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            gross = net = 30000.0
        else:
            if headcount == 2:  # 듀엣
                gross = net = 35000.0
            elif headcount == 3:
                gross = net = 40000.0
            elif headcount == 1:
                gross = net = 25000.0
            else:
                gross = net = 30000.0
    else:  # V
        custom = 0.0
        if mname and (members is not None) and (mname in members["이름"].values):
            try:
                custom = float(members.loc[members["이름"]==mname, "방문실수령(원)"].iloc[0] or 0)
            except Exception:
                custom = 0.0
        gross = net = custom
    return gross, net

def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

# -------- iCal(ICS) 내보내기 --------
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

        title = f'{SITE_KR.get(str(r.get("지점","")).strip(),"")}'
        if str(r.get("구분","")).strip() == "개인":
            nm = str(r.get("이름","")).strip()
            if nm: title += f' · {nm}'
        else:
            title += " · 그룹"

        desc = []
        for k in ["레벨","기구","특이사항"]:
            v = str(r.get(k,"")).strip()
            if v: desc.append(f"{k}:{v}")
        description = "\\n".join(desc)

        uid = f'{str(r.get("id","0"))}@pilates'
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines)).encode("utf-8")

# ======================================
# 초기화 & 데이터 로드
# ======================================
ensure_files()
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
ex_db    = load_ex_db()

# ======================================
# ===== 사이드바: 항상 버튼(활성도 클릭 가능) =====
st.markdown("""
<style>
/* 사이드바 버튼 공통 스타일(네모 배경 제거) */
div[data-testid="stSidebar"] button[kind="secondary"]{
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  text-align: left !important;
  padding: 6px 4px !important;
  font-size: 18px !important;
}
/* 활성 버튼은 빨간색+굵게 */
div[data-testid="stSidebar"] button[kind="secondary"].active{
  color:#ff4b4b !important; font-weight:800 !important;
}
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state["page"] = "schedule"  # 첫 페이지

def menu_btn(label: str, key: str, emoji_only: bool=False):
    show = label if not emoji_only else label.split()[0]
    # 버튼 렌더
    clicked = st.sidebar.button(show, key=f"menu_{key}")
    # 렌더 후, 방금 그 버튼을 '활성 스타일'로 토글
    # (Streamlit은 렌더 시점 클래스를 못 바꾸니 같은 위치에 한 번 더 찍어 덮어씌우기)
    import streamlit as _st
    from uuid import uuid4 as _uuid
    _ph = st.sidebar.empty()
    # 현재 활성 여부
    is_active = (st.session_state["page"] == key)
    # 동일한 버튼을 다시 그리되 active 클래스를 추가
    btn_id = f"menu_{key}"
    _ph.markdown(
        f"""
        <script>
        const btns = parent.document.querySelectorAll('button[kind="secondary"]');
        btns.forEach(b => {{
          if (b.innerText.trim() === `{show}`) {{
            b.classList.remove('active');
            {"b.classList.add('active');" if is_active else ""}
          }}
        }});
        </script>
        """,
        unsafe_allow_html=True
    )
    if clicked:
        st.session_state["page"] = key

st.sidebar.markdown("### 메뉴")
menu_btn("📅 스케줄", "schedule")
menu_btn("✍️ 세션",   "session")
menu_btn("👥 멤버",    "member")
menu_btn("📋 리포트", "report")
menu_btn("🍒",       "cherry", emoji_only=True)
st.sidebar.markdown("---")

# ======================================
# 페이지: 스케줄
# -------- iCal(ICS) 내보내기 헬퍼 --------
from datetime import timezone

def _fmt_ics_dt(dt):
    # Asia/Seoul 기준 로컬시간 문자열
    return dt.strftime("%Y%m%dT%H%M%S")

def build_ics_from_df(df: pd.DataFrame, default_minutes: int = 50) -> bytes:
    """
    보이는 스케줄 DataFrame(df) → .ics 바이너리로 변환
    - 종료시간: '분' 컬럼이 있으면 반영, 없으면 default_minutes 사용
    - title: 개인은 이름, 그룹은 '그룹'으로 표기
    - location: F/R/V를 한글 라벨로 변환
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

        try:
            minutes = int(float(r.get("분", default_minutes) or default_minutes))
        except Exception:
            minutes = default_minutes
        end = start + timedelta(minutes=minutes)

        title = r["이름"] if str(r.get("이름", "")) else "그룹"
        loc = SITE_LABEL.get(r.get("지점", ""), r.get("지점", ""))

        ev = [
            "BEGIN:VEVENT",
            f"UID:{r.get('id', '')}@pilatesapp",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"LOCATION:{loc}",
        ]
        memo = str(r.get("메모", "") or "")
        if memo:
            ev.append(f"DESCRIPTION:{memo}")
        ev.append("END:VEVENT")
        lines.extend(ev)

    lines.append("END:VCALENDAR")
    return "\n".join(lines).encode("utf-8")

    # --------------------------
    # 기간 뷰 (리스트 + 상태 버튼)
    # --------------------------
    st.markdown("#### 📋 일정")
    view = schedule[(schedule["날짜"] >= start) & (schedule["날짜"] < end)].copy().sort_values("날짜")

    def _last_personal_summary(member_name: str):
        """개인 세션의 직전 운동 기록 요약"""
        past = sessions[(sessions["이름"] == member_name)].copy()
        if past.empty:
            return "—"
        past = past.sort_values("날짜", ascending=False)
        last = past.iloc[0]
        # No Show 표기면 🫥
        if str(last.get("사유", "")).lower().strip() == "no show" or str(last.get("특이사항", "")).strip().lower() == "no show":
            return "🫥"
        # 동작 → 추가동작 → 간단요약
        if last.get("동작(리스트)", ""):
            return last["동작(리스트)"]
        if last.get("추가동작", ""):
            return last["추가동작"]
        # 없으면 레벨/기구(있을 때)로 요약
        level = str(last.get("레벨", "") or "")
        equip = str(last.get("기구", "") or "")
        if level or equip:
            return " · ".join([x for x in [level, equip] if x])
        return "—"

    if view.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
        def card_html(r):
            dt = pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")
            chip = tag(SITE_LABEL.get(r["지점"], r["지점"]), SITE_COLOR.get(r["지점"], "#eee"))
            name_html = f'<b style="font-size:16px">{r["이름"] if r["이름"] else "(그룹)"}</b>'
            free = " · ✨" if r.get("온더하우스", False) else ""
            title = f'{dt} · {chip} · {name_html}{free}'
            # 상태 뱃지
            status = str(r.get("상태", "예약됨"))
            if status == "취소됨":
                badge = '<span style="background:#ccc;color:#666;padding:2px 6px;border-radius:6px;text-decoration:line-through;">취소됨</span>'
                title = f"<s>{title}</s>"
            elif status == "No Show":
                badge = '<span style="background:#ffe3e3;color:#d00;padding:2px 6px;border-radius:6px;">No Show</span>'
            elif status == "완료":
                badge = '<span style="background:#e0ffe7;color:#11772a;padding:2px 6px;border-radius:6px;">완료</span>'
            else:
                badge = '<span style="background:#e8f0ff;color:#1849a9;padding:2px 6px;border-radius:6px;">예약됨</span>'

            # 개인: 지난 운동 표시 / 그룹: 간단 요약
            if r["구분"] == "개인" and r["이름"]:
                sub = f'지난 운동: { _last_personal_summary(r["이름"]) }'
            else:
                sub = f'그룹 정보: 인원 {r["인원"]}명'

            if r.get("메모"):
                sub += f' · 메모: {r["메모"]}'

            return f"{title} {badge}", sub

        for _, r in view.iterrows():
            t, b = card_html(r)
            colA, colB, colC, colD = st.columns([3, 1, 1, 1])
            with colA:
                st.markdown(f"{t}<br><span style='color:#888'>{b}</span>", unsafe_allow_html=True)

            # 버튼들 (key = id 기반, 충돌 방지)
            rid = r["id"]
            with colB:
                if st.button("출석", key=f"s_att_{rid}"):
                    # 출석 → 세션 자동 생성 (온더하우스면 0원 & 차감 없음)
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"]))
                    if r.get("온더하우스", False):
                        gross = net = 0.0

                    sess = pd.DataFrame([{
                        "id": ensure_id(sessions),
                        "날짜": r["날짜"],
                        "지점": r["지점"],
                        "구분": r["구분"],
                        "이름": r["이름"],
                        "인원": int(r["인원"]),
                        "레벨": "",
                        "기구": "",
                        "동작(리스트)": "",
                        "추가동작": "",
                        "특이사항": "",
                        "숙제": "",
                        "메모": r.get("메모", ""),
                        "취소": False,
                        "사유": "",
                        "분": 50,
                        "온더하우스": bool(r.get("온더하우스", False)),
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)

                    # 차감: 개인 + 온더하우스 아님
                    if (r["구분"] == "개인") and r["이름"] and (r["이름"] in members["이름"].values) and (not r.get("온더하우스", False)):
                        idx = members.index[members["이름"] == r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx, "남은횟수"] or 0)) - 1)
                        members.loc[idx, "남은횟수"] = str(remain)
                        save_members(members)

                    schedule.loc[schedule["id"] == rid, "상태"] = "완료"
                    save_schedule(schedule)
                    st.experimental_rerun()

            with colC:
                if st.button("취소", key=f"s_can_{rid}"):
                    schedule.loc[schedule["id"] == rid, "상태"] = "취소됨"
                    save_schedule(schedule)
                    st.experimental_rerun()

            with colD:
                if st.button("No Show", key=f"s_nos_{rid}"):
                    # No Show → 세션 생성 없음, 단 차감/페이 처리 원하면 여기서 생성하도록 바꿀 수 있음
                    # (요청사항: No Show는 세션 생성하지 않음)
                    # 차감/페이는 반영해야 한다면 아래 블록 주석 해제
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"]))
                    if not r.get("온더하우스", False):
                        # 개인 차감
                        if (r["구분"] == "개인") and r["이름"] and (r["이름"] in members["이름"].values):
                            idx = members.index[members["이름"] == r["이름"]][0]
                            remain = max(0, int(float(members.loc[idx, "남은횟수"] or 0)) - 1)
                            members.loc[idx, "남은횟수"] = str(remain)
                            save_members(members)
                        # 페이는 🍒 통계에서 집계할 수 있도록 세션 생성이 필요하다면
                        # 아래 주석을 해제하세요 (No Show 세션으로)
                        # sess = pd.DataFrame([{
                        #     "id": ensure_id(sessions),
                        #     "날짜": r["날짜"], "지점": r["지점"], "구분": r["구분"], "이름": r["이름"],
                        #     "인원": int(r["인원"]), "레벨": "", "기구": "",
                        #     "동작(리스트)": "", "추가동작": "",
                        #     "특이사항": "No Show", "숙제": "", "메모": r.get("메모",""),
                        #     "취소": False, "사유": "No Show", "분": 50,
                        #     "온더하우스": False,
                        #     "페이(총)": float(gross), "페이(실수령)": float(gross)
                        # }])
                        # sessions = pd.concat([sessions, sess], ignore_index=True)
                        # save_sessions(sessions)

                    schedule.loc[schedule["id"] == rid, "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

    # --------------------------
    # 📤 iCal(.ics) 내보내기
    # --------------------------
    st.divider()
    st.subheader("📤 iCal(.ics) 내보내기")

    exclude_cancel = st.checkbox("취소된 일정 제외", value=True, key="ics_excl_cancel")

    export_df = view.copy()
    if not export_df.empty:
        if "취소" in export_df.columns:
            # (예전 스키마 호환) 취소 컬럼이 있다면 반영
            if exclude_cancel:
                export_df = export_df[~export_df["취소"].astype(str).str.lower().isin(["true", "1", "y", "yes"])]
        elif "상태" in export_df.columns and exclude_cancel:
            export_df = export_df[export_df["상태"] != "취소됨"]

    if export_df.empty:
        st.caption("내보낼 일정이 없습니다.")
    else:
        ics_bytes = build_ics_from_df(export_df)
        filename = f"schedule_{view_mode}_{base.strftime('%Y%m%d')}.ics"
        st.download_button("⬇️ iCal 파일 다운로드",
                           data=ics_bytes, file_name=filename, mime="text/calendar",
                           use_container_width=True, key="ics_dl_btn")
        st.caption("받은 .ics 파일을 아이폰/구글 캘린더에 추가하면 일정이 달력에 들어가요.")

# -------- iCal(ICS) 내보내기 헬퍼 --------
from datetime import timezone

def _fmt_ics_dt(dt):
    # Asia/Seoul 기준 로컬시간 문자열
    return dt.strftime("%Y%m%dT%H%M%S")

def build_ics_from_df(df: pd.DataFrame, default_minutes: int = 50) -> bytes:
    """
    보이는 스케줄 DataFrame(df) → .ics 바이너리로 변환
    - 종료시간: '분' 컬럼이 있으면 반영, 없으면 default_minutes 사용
    - title: 개인은 이름, 그룹은 '그룹'으로 표기
    - location: F/R/V를 한글 라벨로 변환
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

        try:
            minutes = int(float(r.get("분", default_minutes) or default_minutes))
        except Exception:
            minutes = default_minutes
        end = start + timedelta(minutes=minutes)

        title = r["이름"] if str(r.get("이름", "")) else "그룹"
        loc = SITE_LABEL.get(r.get("지점", ""), r.get("지점", ""))

        ev = [
            "BEGIN:VEVENT",
            f"UID:{r.get('id', '')}@pilatesapp",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"LOCATION:{loc}",
        ]
        memo = str(r.get("메모", "") or "")
        if memo:
            ev.append(f"DESCRIPTION:{memo}")
        ev.append("END:VEVENT")
        lines.extend(ev)

    lines.append("END:VCALENDAR")
    return "\n".join(lines).encode("utf-8")


# ======================================
# 페이지: 세션
# -------------------------
# ✍️ 세션 탭
# -------------------------
elif menu == "세션":
    st.subheader("✍️ 세션 기록")

    # 멤버 선택
    member = st.selectbox("멤버 선택", members["이름"].tolist(), key="session_member")

    # 기구 선택 (다중)
    equip_sel = st.multiselect(
        "기구 선택",
        ["Mat", "Reformer", "Cadillac", "Wunda chair", "Barrel/Spine", "Small Barrel",
         "Spine corrector", "Electric chair", "Pedi-pul", "Magic circle", "Arm chair",
         "Foam/Toe/Neck", "기타"],
        key="session_equips"
    )

    # 동작 선택 (기구별 통합 목록에서 복수 선택 가능, 유지됨)
    chosen_moves = st.multiselect(
        "운동 동작(복수 선택 가능)", 
        options=sorted(per_moves), 
        key="session_moves"
    )

    # 추가 입력란
    add_free  = st.text_input("추가 동작(콤마 , 로 구분)", key="session_add_free")
    spec_note = st.text_input("특이사항", key="session_spec")
    homework  = st.text_input("숙제", key="session_homework")
    memo      = st.text_area("메모", height=60, key="session_memo")

    # 세션 저장 버튼
    if st.button("세션 기록 저장", key="session_save_btn"):
        if not member:
            st.warning("멤버를 선택하세요.")
        else:
            new_session = {
                "날짜": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "멤버": member,
                "기구": ", ".join(equip_sel),
                "동작": ", ".join(chosen_moves),
                "추가동작": add_free,
                "특이사항": spec_note,
                "숙제": homework,
                "메모": memo,
                "페이": 0   # 숨길 컬럼, 내부 기록용
            }
            sessions = pd.concat([sessions, pd.DataFrame([new_session])], ignore_index=True)
            save_csv(sessions, "sessions.csv")
            st.success("✅ 세션 기록이 저장되었습니다.")

    # 최근 세션 기록 표시 (페이 컬럼은 숨김)
    if not sessions.empty:
        st.markdown("#### 📑 최근 세션 기록")
        show_cols = [c for c in sessions.columns if c != "페이"]
        st.dataframe(sessions[show_cols].tail(10).sort_index(ascending=False), use_container_width=True)
# ======================================
# 페이지: 멤버
# ======================================
elif st.session_state["page"] == "member":
    st.subheader("👥 멤버 관리")

    with st.expander("➕ 등록/수정/재등록/삭제", expanded=True):
        L,R = st.columns([1,1])
        with L:
            names = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", names)
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel)
            default_phone = ""
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_phone = members.loc[members["이름"]==sel,"연락처"].iloc[0]
            phone = st.text_input("연락처", value=default_phone, placeholder="010-0000-0000")
            if phone and (members[(members["연락처"]==phone) & (members["이름"]!=name)].shape[0] > 0):
                st.error("⚠️ 동일한 전화번호가 이미 존재합니다.")
        with R:
            default_site = "F"
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_site = members.loc[members["이름"]==sel,"기본지점"].iloc[0] or "F"
            site = st.selectbox("기본 지점(F/R/V)", SITES, index=SITES.index(default_site))
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
        visit_pay = st.number_input("방문 실수령(원)", 0, 1_000_000,
                                    value=int(float(members.loc[members["이름"]==sel,"방문실수령(원)"].iloc[0])) if (sel!="(새 회원)" and sel in members["이름"].values and str(members.loc[members["이름"]==sel,"방문실수령(원)"].iloc[0]).strip()!="") else 0,
                                    step=1000)

        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                else:
                    if sel=="(새 회원)":
                        row = pd.DataFrame([{
                            "id": ensure_id(members),
                            "이름": name.strip(),
                            "연락처": phone.strip(),
                            "기본지점": site,
                            "등록일": reg_date.isoformat(),
                            "총등록": "0",
                            "남은횟수": "0",
                            "회원유형": "일반",
                            "메모": note,
                            "재등록횟수": "0",
                            "최근재등록일": "",
                            "방문실수령(원)": str(int(visit_pay))
                        }])
                        members = pd.concat([members, row], ignore_index=True)
                    else:
                        i = members.index[members["이름"]==sel][0]
                        members.loc[i,["이름","연락처","기본지점","등록일","메모","방문실수령(원)"]] = \
                            [name.strip(), phone.strip(), site, reg_date.isoformat(), note, str(int(visit_pay))]
                    save_members(members)
                    st.success("저장 완료")

        with c2:
            if st.button("재등록(+횟수 반영)", use_container_width=True, disabled=(sel=="(새 회원)")):
                if sel=="(새 회원)":
                    st.error("기존 회원 선택")
                else:
                    i = members.index[members["이름"]==sel][0]
                    members.loc[i,"총등록"] = str(int(float(members.loc[i,"총등록"] or 0)) + int(add_cnt))
                    members.loc[i,"남은횟수"] = str(int(float(members.loc[i,"남은횟수"] or 0)) + int(add_cnt))
                    members.loc[i,"재등록횟수"] = str(int(float(members.loc[i,"재등록횟수"] or 0)) + 1)
                    members.loc[i,"최근재등록일"] = date.today().isoformat()
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
            st.info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            for c in ["등록일","최근재등록일"]:
                show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
            st.dataframe(show, use_container_width=True, hide_index=True)

# ======================================
# 페이지: 리포트 (간략)
# ======================================
elif st.session_state["page"] == "report":
    st.subheader("📋 리포트 (회원 동작 요약)")
    if sessions.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        # 가장 최근 월 기준 멤버별 동작 상위 5개
        month = st.selectbox("월 선택(YYYY-MM)", sorted(pd.to_datetime(sessions["날짜"]).dt.strftime("%Y-%m").unique()), index=0)
        who   = st.selectbox("회원 선택", sorted(set(sessions["이름"].dropna().astype(str)) - set([""])))
        dfm = sessions.copy()
        dfm = dfm[(pd.to_datetime(dfm["날짜"]).dt.strftime("%Y-%m")==month) & (dfm["이름"]==who)]
        moves = []
        for x in dfm["동작(리스트)"].dropna():
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

# ======================================
# 페이지: 🍒 (PIN)
# ======================================
elif st.session_state["page"] == "cherry":
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
        # 수입 집계 = 세션(실수령 합계) + 스케줄 No Show의 실수령(세션 생성 안했으므로 여기서 반영)
        if sessions.empty and schedule.empty:
            st.info("데이터가 없습니다.")
        else:
            ses = sessions.copy()
            ses["Y"]  = pd.to_datetime(ses["날짜"]).dt.year
            ses["YM"] = pd.to_datetime(ses["날짜"]).dt.strftime("%Y-%m")
            ses_income = ses["페이(실수령)"].fillna(0).astype(float)

            # 스케줄 No Show의 수입(✨면 0, 아니면 pay계산)
            sch_ns = schedule[schedule["상태"]=="No Show"].copy()
            if not sch_ns.empty:
                ns_net = []
                for _, r in sch_ns.iterrows():
                    gross, net = calc_pay(r["지점"], r["구분"], int(r.get("인원",1) or 1), r.get("이름",""), members)
                    if bool(r["온더하우스"]):
                        net = 0.0
                    ns_net.append(net)
                sch_ns["net"] = ns_net
                sch_ns["Y"]   = pd.to_datetime(sch_ns["날짜"]).dt.year
                sch_ns["YM"]  = pd.to_datetime(sch_ns["날짜"]).dt.strftime("%Y-%m")
            else:
                sch_ns = pd.DataFrame(columns=["Y","YM","net"])

            # 월/연 합계(세션 + No Show)
            month_sum = ses.groupby("YM")["페이(실수령)"].sum().astype(float).reset_index().rename(columns={"페이(실수령)":"세션"})
            if not sch_ns.empty:
                ns_month = sch_ns.groupby("YM")["net"].sum().reset_index().rename(columns={"net":"NoShow"})
                month_sum = month_sum.merge(ns_month, on="YM", how="outer").fillna(0)
            else:
                month_sum["NoShow"]=0.0
            month_sum["합계"] = (month_sum["세션"] + month_sum["NoShow"]).astype(int)

            year_sum = ses.groupby("Y")["페이(실수령)"].sum().astype(float).reset_index().rename(columns={"페이(실수령)":"세션"})
            if not sch_ns.empty:
                ns_year = sch_ns.groupby("Y")["net"].sum().reset_index().rename(columns={"net":"NoShow"})
                year_sum = year_sum.merge(ns_year, on="Y", how="outer").fillna(0)
            else:
                year_sum["NoShow"]=0.0
            year_sum["합계"] = (year_sum["세션"] + year_sum["NoShow"]).astype(int)

            col1,col2 = st.columns(2)
            with col1:
                st.markdown("**월별 실수령(세션+NoShow)**")
                st.dataframe(month_sum.sort_values("YM", ascending=False), use_container_width=True, hide_index=True)
            with col2:
                st.markdown("**연도별 실수령(세션+NoShow)**")
                st.dataframe(year_sum.sort_values("Y", ascending=False), use_container_width=True, hide_index=True)

            # 지점별 월간 건수(개인/그룹 각각, F/R/V)
            st.markdown("**지점별 월간 건수(개인/그룹)**")
            # 세션 + 스케줄(No Show 포함)에서 카운트
            ss = sessions.copy()
            ss["YM"] = pd.to_datetime(ss["날짜"]).dt.strftime("%Y-%m")
            sch_all = schedule.copy()
            sch_all["YM"] = pd.to_datetime(sch_all["날짜"]).dt.strftime("%Y-%m")

            def pivot_counts(df, label):
                if df.empty:
                    return pd.DataFrame(columns=["YM","구분","F","R","V"])
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








