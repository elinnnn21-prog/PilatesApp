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
# ======================================
if st.session_state["page"] == "schedule":
    st.subheader("📅 스케줄")

    # 보기 전환 / 기준일
    cc = st.columns([1,1,2,1])
    with cc[0]:
        view_mode = st.radio("보기", ["일","주","월"], horizontal=True, index=1, label_visibility="collapsed")
    with cc[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed")

    base_dt = datetime.combine(base, time.min)
    if view_mode=="일":
        start, end = base_dt, base_dt + timedelta(days=1)
    elif view_mode=="주":
        start = base_dt - timedelta(days=base_dt.weekday())
        end   = start + timedelta(days=7)
    else:
        start = base_dt.replace(day=1)
        end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

    # 예약 추가
    st.markdown("#### ✨ 예약 추가")
    cols = st.columns([1,1,1,1,1,1])
    with cols[0]:
        sdate = st.date_input("날짜", value=base)
    with cols[1]:
        stime = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0))
    with cols[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True)
    with cols[3]:
        if stype=="개인":
            mname = st.selectbox("회원(개인)", members["이름"].tolist() if not members.empty else [])
            default_site = members.loc[members["이름"]==mname, "기본지점"].iloc[0] if mname and (mname in members["이름"].values) else "F"
        else:
            mname = ""
            default_site = "F"
        site = st.selectbox("지점", SITES, index=SITES.index(default_site))
    with cols[4]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"])
    with cols[5]:
        equip = st.selectbox("기구", list(ex_db.keys()))

    cols2 = st.columns([1,1,2,1])
    with cols2[0]:
        headcount = st.number_input("인원(그룹)", 1, 20, 1 if stype=="개인" else 2, disabled=(stype=="개인"))
    with cols2[1]:
        onth = st.checkbox("On the house(✨)")
    with cols2[2]:
        spec_note = st.text_input("메모(선택)", value="")
    with cols2[3]:
        pass

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
            "온더하우스": bool(onth),
            "상태": "예약됨"
        }])
        schedule = pd.concat([schedule, row], ignore_index=True)
        save_schedule(schedule)
        st.success("예약이 추가되었습니다.")

    # 기간 표시
    st.markdown("#### 📋 일정")
    v = schedule[(schedule["날짜"]>=start) & (schedule["날짜"]<end)].copy().sort_values("날짜")
    if v.empty:
        st.info("해당 기간에 일정이 없습니다.")
    else:
        for _, r in v.iterrows():
            time_html = pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")
            name_html = f'<b style="font-size:16px">{r["이름"] if r["이름"] else "(그룹)"}</b>'
            chip = tag(r["지점"], SITE_COLOR.get(r["지점"], "#eee"))
            free = " · ✨" if r["온더하우스"] else ""
            title = f'{time_html} · {chip} · {name_html}{free}'
            sub   = f'{r["구분"]} · {r.get("레벨","")} · {r.get("기구","")}'
            if r.get("특이사항",""):
                sub += f' · 메모: {r["특이사항"]}'
            if r["상태"]=="취소됨":
                title = f"<s>{title}</s>"

            colA,colB,colC,colD = st.columns([3,1,1,1])
            with colA:
                st.markdown(f"{title}<br><span style='color:#bbb'>{sub}</span><br><span>상태: <b>{r['상태']}</b></span>", unsafe_allow_html=True)

                # 개인: 지난 운동 요약(직전 세션 확인) — 직전 세션이 No Show면 🫥
                if (r["구분"]=="개인") and r["이름"]:
                    prev = sessions[
                        (sessions["이름"]==r["이름"]) &
                        (pd.to_datetime(sessions["날짜"]) < pd.to_datetime(r["날짜"]))
                    ].sort_values("날짜", ascending=False).head(1)
                    if not prev.empty:
                        pr = prev.iloc[0]
                        noshow_prev = (str(pr.get("사유","")).strip().lower()=="no show" or
                                       str(pr.get("특이사항","")).strip().lower()=="no show")
                        if noshow_prev:
                            st.caption("지난 운동: 🫥")
                        else:
                            moves = str(pr.get("동작(리스트)","")).strip()
                            extra = str(pr.get("추가동작","")).strip()
                            summary = moves or extra or f'{pr.get("레벨","")} · {pr.get("기구","")}'.strip(" ·")
                            st.caption(f"지난 운동: {summary}")
                    else:
                        st.caption("지난 운동: (기록 없음)")

                # 그룹: 레벨·기구·인원 요약
                if r["구분"]=="그룹":
                    st.caption(f'그룹 정보: {r.get("레벨","")} · {r.get("기구","")} · {int(r.get("인원",1))}명')

            with colB:
                if st.button("출석", key=f"att_{r['id']}"):
                    # 출석 → 세션 자동 생성(임시), 규칙 반영
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"]), r.get("이름",""), members)
                    if bool(r["온더하우스"]):
                        gross = net = 0.0  # 0원
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
                        "특이사항": r.get("특이사항",""),
                        "숙제": "",
                        "메모": "",
                        "취소": False,
                        "사유": "",
                        "분": 50,
                        "온더하우스": bool(r["온더하우스"]),
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)

                    # 횟수 차감 (개인 + ✨아닐 때)
                    if (r["구분"]=="개인") and r["이름"] and (not r["온더하우스"]) and (r["이름"] in members["이름"].values):
                        mi = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[mi,"남은횟수"] or 0)) - 1)
                        members.loc[mi,"남은횟수"] = str(remain)
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
                    # 규칙: 세션 생성 안 함, 차감O & 페이O (단 ✨면 0원 & 차감X)
                    if (r["구분"]=="개인") and r["이름"] and (not r["온더하우스"]) and (r["이름"] in members["이름"].values):
                        mi = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[mi,"남은횟수"] or 0)) - 1)
                        members.loc[mi,"남은횟수"] = str(remain)
                        save_members(members)

                    # 스케줄의 상태만 No Show로
                    schedule.loc[schedule["id"]==r["id"], "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

    # ---- iCal 내보내기 ----
    st.divider()
    st.subheader("📤 iCal(.ics) 내보내기")
    exclude_cancel = st.checkbox("취소 제외", value=True)
    export_df = v.copy()
    if not export_df.empty and exclude_cancel:
        export_df = export_df[export_df["상태"]!="취소됨"]
    if export_df.empty:
        st.caption("내보낼 일정이 없습니다.")
    else:
        # iCal에 종료시간이 필요하므로 분 컬럼 보강
        export_df = export_df.copy()
        export_df["분"] = 50
        ics_bytes = build_ics_from_df(export_df)
        fname = f"schedule_{view_mode}_{base.strftime('%Y%m%d')}.ics"
        st.download_button("⬇️ iCal 파일 다운로드", data=ics_bytes, file_name=fname, mime="text/calendar", use_container_width=True)

# ======================================
# 페이지: 세션
# ======================================
elif st.session_state["page"] == "session":
    st.subheader("✍️ 세션 기록")

    # 선택 유지 저장소(기구별 동작 멀티선택 유지)
    if "move_choices" not in st.session_state:
        st.session_state["move_choices"] = {}  # {equip: [moves,…]}
    if "equip_selected" not in st.session_state:
        st.session_state["equip_selected"] = []

    # 최근 자동 생성(출석) 세션 중 내용 비어있는 것 빠르게 편집
    st.markdown("##### 🔧 최근 자동 생성 세션 편집")
    pending = sessions[
        (sessions["동작(리스트)"]=="") & (sessions["취소"]==False)
    ].sort_values("날짜", ascending=False).head(10)
    pick = None
    if not pending.empty:
        pick = st.selectbox(
            "편집할 세션 선택",
            options=[f'{row["id"]} · {row["이름"] or "(그룹)"} · {SITE_KR.get(row["지점"],row["지점"])} · {pd.to_datetime(row["날짜"]).strftime("%m/%d %H:%M")}'
                     for _,row in pending.iterrows()]
        )
    else:
        st.caption("편집할 자동 생성 세션이 없습니다.")

    # 자유 생성/편집(필요시)
    st.markdown("##### 🧾 새 세션 추가 또는 선택한 세션 편집")
    c = st.columns([1,1,1,1])
    with c[0]:
        day = st.date_input("날짜", value=date.today())
    with c[1]:
        tme = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0))
    with c[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True)
    with c[3]:
        minutes = st.number_input("수업 분", 10, 180, 50, 5)

    c2 = st.columns([1,1,1])
    with c2[0]:
        if stype=="개인":
            mname = st.selectbox("회원", members["이름"].tolist() if not members.empty else [])
            auto_site = members.loc[members["이름"]==mname, "기본지점"].iloc[0] if mname and (mname in members["이름"].values) else "F"
            site = st.selectbox("지점", SITES, index=SITES.index(auto_site))
        else:
            mname = ""
            site = st.selectbox("지점", SITES)
    with c2[1]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"])
    with c2[2]:
        headcount = st.number_input("인원(그룹)", 1, 20, 1 if stype=="개인" else 2, disabled=(stype=="개인"))

    # 다중 기구 선택
    st.markdown("###### 기구 선택(복수)")
    equip_multi = st.multiselect("기구", options=list(ex_db.keys()), default=st.session_state["equip_selected"])
    st.session_state["equip_selected"] = equip_multi

    # 기구별 동작 멀티선택(선택 유지)
    selected_moves_total: List[str] = []
    for eq in equip_multi:
        prev_sel = st.session_state["move_choices"].get(eq, [])
        options = ex_db.get(eq, [])
        chosen = st.multiselect(f"동작 - {eq}", options=options, default=prev_sel, key=f"mv_{eq}")
        st.session_state["move_choices"][eq] = chosen
        selected_moves_total.extend([f"{eq} · {m}" for m in chosen])

    add_free = st.text_input("추가 동작(콤마로 구분)", value="")
    special   = st.text_input("특이사항(선택)", value="")
    homework  = st.text_input("숙제(선택)", value="")
    memo      = st.text_area("메모(선택)", height=60)

    col_btn = st.columns(2)
    with col_btn[0]:
        if st.button("세션 저장/추가", use_container_width=True):
            when = datetime.combine(day, tme)
            # 새 세션 저장
            gross, net = calc_pay(site, stype, int(headcount), mname, members)
            row = pd.DataFrame([{
                "id": ensure_id(sessions),
                "날짜": when,
                "지점": site,
                "구분": stype,
                "이름": mname if stype=="개인" else "",
                "인원": int(headcount) if stype=="그룹" else 1,
                "레벨": level,
                "기구": ", ".join(equip_multi),
                "동작(리스트)": "; ".join(selected_moves_total),
                "추가동작": add_free,
                "특이사항": special,
                "숙제": homework,
                "메모": memo,
                "취소": False,
                "사유": "",
                "분": int(minutes),
                "온더하우스": False,
                "페이(총)": float(gross),
                "페이(실수령)": float(net)
            }])
            sessions[:] = pd.concat([sessions, row], ignore_index=True)
            save_sessions(sessions)
            st.success("세션이 저장되었습니다.")

    with col_btn[1]:
        if pick and st.button("선택한 자동 생성 세션에 반영", use_container_width=True):
            sel_id = pick.split("·")[0].strip()  # "id · ..."
            idx = sessions.index[sessions["id"].astype(str)==sel_id]
            if len(idx)>0:
                i = idx[0]
                sessions.loc[i,"레벨"]         = level
                sessions.loc[i,"기구"]          = ", ".join(equip_multi)
                sessions.loc[i,"동작(리스트)"]   = "; ".join(selected_moves_total)
                sessions.loc[i,"추가동작"]       = add_free
                sessions.loc[i,"특이사항"]       = special
                sessions.loc[i,"숙제"]           = homework
                sessions.loc[i,"메모"]           = memo
                sessions.loc[i,"분"]             = int(minutes)
                save_sessions(sessions)
                st.success("자동 생성 세션이 업데이트되었습니다.")

    st.markdown("##### 🔎 최근 세션")
    if sessions.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        view = sessions.sort_values("날짜", ascending=False).copy()
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        hide_cols = ["페이(총)","페이(실수령)"]
        show_cols = [c for c in view.columns if c not in hide_cols]
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

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


