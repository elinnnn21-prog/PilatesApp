# app.py
import os
from pathlib import Path
from datetime import datetime, date, time as dtime, timedelta, timezone
from typing import Dict, List

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(page_title="✨ Pilates Manager", page_icon="✨", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV   = DATA_DIR / "members.csv"
SESSIONS_CSV  = DATA_DIR / "sessions.csv"
SCHEDULE_CSV  = DATA_DIR / "schedule.csv"
EX_JSON       = DATA_DIR / "exercise_db.json"

CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

# 지점: F/R/V (기존 한글 표기도 자동 매핑)
SITES = ["F", "R", "V"]
SITE_LABEL = {"F": "F (플로우)", "R": "R (리유)", "V": "V (방문)"}
SITE_COLOR = {"F": "#d9f0ff", "R": "#f0f0f0", "V": "#e9fbe9"}
SITE_FROM_KR = {"플로우": "F", "리유": "R", "방문": "V"}

# -----------------------------------------------------------------------------
# 동작 DB (장비별)
# -----------------------------------------------------------------------------
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat": [
        "Roll down","The hundred","Roll up","Single leg circles",
        "Rolling like a ball","Single leg stretch","Double leg stretch",
        "Spine stretch forward","Criss cross","Teaser","Swimming",
        "Scissors","Bicycle","Jack knife"
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

# -----------------------------------------------------------------------------
# 파일 유틸 + 스키마 업그레이드
# -----------------------------------------------------------------------------
def _ensure_dir():
    DATA_DIR.mkdir(exist_ok=True)

def _upgrade_members(df: pd.DataFrame) -> pd.DataFrame:
    need_cols = ["id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
                 "메모","재등록횟수","최근재등록일"]
    for c in need_cols:
        if c not in df.columns:
            df[c] = ""
    # 예전 한글 지점명 -> F/R/V
    if "지점" in df.columns and "기본지점" not in df.columns:
        df["기본지점"] = df["지점"].map(SITE_FROM_KR).fillna(df.get("기본지점","F"))
    if "기본지점" in df.columns:
        df["기본지점"] = df["기본지점"].replace(SITE_FROM_KR)
        df["기본지점"] = df["기본지점"].where(df["기본지점"].isin(SITES), "F")
    # 숫자 컬럼 정리
    for ncol in ["총등록","남은횟수","재등록횟수"]:
        df[ncol] = pd.to_numeric(df[ncol], errors="coerce").fillna(0).astype(int).astype(str)
    return df[need_cols]

def _upgrade_sessions(df: pd.DataFrame) -> pd.DataFrame:
    need = ["id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제","메모",
            "취소","사유","분","온더하우스","페이(총)","페이(실수령)"]
    for c in need:
        if c not in df.columns:
            df[c] = ""
    # 타입
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes","✨"])
    return df[need]

def _upgrade_schedule(df: pd.DataFrame) -> pd.DataFrame:
    need = ["id","날짜","지점","구분","이름","인원","레벨","기구",
            "특이사항","숙제","온더하우스","상태"]
    for c in need:
        if c not in df.columns:
            df[c] = ""
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        df["인원"] = pd.to_numeric(df["인원"], errors="coerce").fillna(1).astype(int)
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes","✨"])
        # 한글 지점명 -> F/R/V
        df["지점"] = df["지점"].replace(SITE_FROM_KR)
        df["지점"] = df["지점"].where(df["지점"].isin(SITES), "F")
        df["상태"] = df["상태"].replace({"예약": "예약됨"})
        df["상태"] = df["상태"].fillna("예약됨")
    return df[need]

def ensure_files():
    _ensure_dir()
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=["id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",
                              "메모","재등록횟수","최근재등록일"]
                    ).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=["id","날짜","지점","구분","이름","인원","레벨","기구",
                              "동작(리스트)","추가동작","특이사항","숙제","메모",
                              "취소","사유","분","온더하우스","페이(총)","페이(실수령)"]
                    ).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    if not SCHEDULE_CSV.exists():
        pd.DataFrame(columns=["id","날짜","지점","구분","이름","인원","레벨","기구",
                              "특이사항","숙제","온더하우스","상태"]
                    ).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

def load_members() -> pd.DataFrame:
    df = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return _upgrade_members(df)

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return _upgrade_sessions(df)

def save_sessions(df: pd.DataFrame):
    df2 = df.copy()
    if not df2.empty:
        df2["날짜"] = pd.to_datetime(df2["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df2.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_schedule() -> pd.DataFrame:
    df = pd.read_csv(SCHEDULE_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return _upgrade_schedule(df)

def save_schedule(df: pd.DataFrame):
    df2 = df.copy()
    if not df2.empty:
        df2["날짜"] = pd.to_datetime(df2["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df2.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

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

ensure_files()
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
ex_db    = load_ex_db()

# -----------------------------------------------------------------------------
# 유틸
# -----------------------------------------------------------------------------
def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def big_info(msg: str):
    st.info(msg)

def ensure_id(df: pd.DataFrame) -> str:
    if df.empty: return "1"
    try:
        return str(max(pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)) + 1)
    except Exception:
        return str(len(df)+1)

def calc_pay(site: str, session_type: str, headcount: int) -> tuple[float,float]:
    """
    F: 회당 35,000원, 3.3% 공제
    R: 개인 30,000 / 3명 40,000 / 2명 35,000(듀엣) / 1명 25,000 (공제 없음)
    V: 사용자 입력 없으므로 0 처리(수기로 보정 가능)
    """
    site = SITE_FROM_KR.get(site, site)  # 혹시 한글 들어오면 변환
    if site == "F":
        gross = 35000.0
        net = round(gross * 0.967, 0)
        return gross, net
    if site == "R":
        if session_type == "개인":
            return 30000.0, 30000.0
        # 그룹
        if headcount == 2:
            return 35000.0, 35000.0
        mapping = {3:40000.0, 1:25000.0}
        val = mapping.get(headcount, 30000.0)
        return val, val
    # 방문(V) — 별도 금액이 없다면 0 처리
    return 0.0, 0.0

# -----------------------------------------------------------------------------
# iCal(.ics) 내보내기
# -----------------------------------------------------------------------------
def _fmt_ics_dt(dt):
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
        title = f'{r.get("구분","")} {r.get("이름","")}'.strip()
        if not title:
            title = "Pilates Session"
        desc = f"{r.get('레벨','')} / {r.get('기구','')}"
        if r.get("특이사항"):
            desc += f" / 특이:{r['특이사항']}"
        if r.get("숙제"):
            desc += f" / 숙제:{r['숙제']}"
        uid = f"{r.get('id','')}-{_fmt_ics_dt(start)}@pilatesapp"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT"
        ]
    lines.append("END:VCALENDAR")
    ics = "\r\n".join(lines)
    return ics.encode("utf-8")

# -----------------------------------------------------------------------------
# 사이드바: 커스텀 메뉴 (버튼만, 현재 페이지만 굵은 붉은색)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
.sidebar-menu a { display:block; font-size:20px; text-decoration:none; padding:6px 2px; }
.sidebar-menu a:hover { font-weight:700; color:#FF4B4B; }
.sidebar-menu .active { font-weight:800; color:#FF4B4B; }
.stButton > button { background:transparent; border:0; padding:0; box-shadow:none; }
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "schedule"  # 첫 페이지: 스케줄

st.sidebar.markdown("## 메뉴")
def menu_link(label: str, key: str, emoji_only: bool = False):
    show = label if not emoji_only else label.split()[0]
    cls = "active" if st.session_state.page == key else ""
    clicked = st.sidebar.button(show, key=f"_menu_{key}")
    # 현재 페이지만 굵은 텍스트로 표시
    st.sidebar.markdown(f'<div class="sidebar-menu"><a class="{cls}">{show}</a></div>', unsafe_allow_html=True)
    if clicked:
        st.session_state.page = key

menu_link("📅 스케줄", "schedule")
menu_link("✍️ 세션",   "session")
menu_link("👥 멤버",    "member")
menu_link("📋 리포트", "report")
menu_link("🍒",       "cherry", emoji_only=True)
st.write("")

# -----------------------------------------------------------------------------
# 📅 스케줄
# -----------------------------------------------------------------------------
if st.session_state.page == "schedule":
    st.subheader("📅 스케줄")

    vcols = st.columns([1,1,2,1])
    with vcols[0]:
        view_mode = st.radio("보기", ["일","주","월"], index=1, horizontal=True, label_visibility="collapsed", key="view_mode_radio")
    with vcols[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed", key="base_date_input")
    base_dt = datetime.combine(base, dtime.min)
    if view_mode=="일":
        start, end = base_dt, base_dt + timedelta(days=1)
    elif view_mode=="주":
        start = base_dt - timedelta(days=base_dt.weekday())
        end   = start + timedelta(days=7)
    else:
        start = base_dt.replace(day=1)
        end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

    # ---- 예약 등록
    st.markdown("#### ✨ 예약 등록")
    c = st.columns([1,1,1,1,1,1])
    with c[0]:
        sdate = st.date_input("날짜", value=base, key="sched_add_date")
    with c[1]:
        default_time = datetime.now().time().replace(second=0, microsecond=0)
        stime = st.time_input("시간", value=default_time, key="sched_add_time")
    with c[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True, key="sched_add_type")
    with c[3]:
        if stype=="개인":
            mname = st.selectbox("이름(개인)", members["이름"].tolist() if not members.empty else [], key="sched_add_member")
            default_site = members.loc[members["이름"]==mname,"기본지점"].iloc[0] if mname and (mname in members["이름"].values) else "F"
        else:
            mname = ""
            default_site = "F"
        site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES],
                            index=SITES.index(default_site), key="sched_add_site")
        site = site.split()[0]
    with c[4]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"], key="sched_add_level")
    with c[5]:
        equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat","기타"], key="sched_add_equip")

    cc = st.columns([1,1,1,2])
    with cc[0]:
        headcount = st.number_input("인원(그룹)", 1, 10, 1 if stype=="개인" else 2, 1, disabled=(stype=="개인"), key="sched_add_head")
    with cc[1]:
        onth = st.checkbox("✨ On the house", key="sched_add_onth")
    with cc[2]:
        spec_note = st.text_input("특이사항", value="", key="sched_add_spec")
    with cc[3]:
        homework = st.text_input("숙제", value="", key="sched_add_home")

    if st.button("예약 추가", use_container_width=True, key="sched_add_btn"):
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
            "온더하우스": bool(onth),
            "상태": "예약됨"
        }])
        schedule = pd.concat([schedule, row], ignore_index=True)
        save_schedule(schedule)
        st.success("예약이 추가되었습니다.")

    # ---- 일정 리스트
    st.markdown("#### 📋 일정")
    v = schedule[(schedule["날짜"]>=start) & (schedule["날짜"]<end)].copy().sort_values("날짜")
    if v.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
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

        for _, r in v.iterrows():
            t, b, badge = line_of(r)
            colA, colB, colC, colD = st.columns([3,1,1,1])
            with colA:
                st.markdown(f"{t}<br><span style='color:#bbb'>{b}</span><br><span>상태: <b>{badge}</b></span>", unsafe_allow_html=True)
            with colB:
                if st.button("출석", key=f"att_{r['id']}"):
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
                    # 횟수 차감 (개인 & 무료 아님)
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
                    if (r["구분"]=="개인") and (r["이름"] in members["이름"].values) and (not free):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(remain)
                        save_members(members)
                    schedule.loc[schedule["id"]==r["id"], "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

    # ---- iCal 내보내기
    st.divider()
    st.subheader("📤 iCal(.ics) 내보내기")
    export_df = schedule[(schedule["날짜"]>=start) & (schedule["날짜"]<end)].copy().sort_values("날짜")
    exclude_cancel = st.checkbox("취소된 일정 제외", value=True, key="ics_exclude_cancel")
    if "상태" in export_df.columns and exclude_cancel:
        export_df = export_df[export_df["상태"]!="취소됨"]
    if export_df.empty:
        st.caption("내보낼 일정이 없습니다.")
    else:
        # 세션 구간 길이가 없으므로 기본 50분으로 내보내기
        export_df["분"] = 50
        ics_bytes = build_ics_from_df(export_df)
        filename = f"schedule_{view_mode}_{base.strftime('%Y%m%d')}.ics"
        st.download_button("⬇️ iCal 파일 다운로드", data=ics_bytes,
                           file_name=filename, mime="text/calendar",
                           use_container_width=True, key="ics_download_btn")
        st.caption("다운로드한 .ics 파일을 아이폰/구글 캘린더에 추가하세요.")

# -----------------------------------------------------------------------------
# ✍️ 세션 기록
# -----------------------------------------------------------------------------
elif st.session_state.page == "session":
    st.subheader("✍️ 세션 기록")

    cols = st.columns([1,1,1,1])
    with cols[0]:
        s_day = st.date_input("날짜", value=date.today(), key="sess_day")
        s_time = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0), key="sess_time")
    with cols[1]:
        s_type = st.radio("구분", ["개인","그룹"], horizontal=True, key="sess_type")
    with cols[2]:
        if s_type=="개인":
            s_mname = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [], key="sess_member")
        else:
            s_mname = ""
        s_site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES], key="sess_site")
        s_site = s_site.split()[0]
    with cols[3]:
        minutes = st.number_input("수업 분", 10, 180, 50, 5, key="sess_minutes")

    c2 = st.columns([1,1,1,1])
    with c2[0]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"], key="sess_level")
    with c2[1]:
        equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat","기타"], key="sess_equip")
    with c2[2]:
        headcount = st.number_input("인원(그룹)", 1, 10, 2 if s_type=="그룹" else 1, 1, disabled=(s_type=="개인"), key="sess_head")
    with c2[3]:
        onth = st.checkbox("✨ On the house", key="sess_onth")

    # 장비별 동작 목록
    all_options = []
    equip_map = {
        "Mat": "Mat",
        "Reformer": "Reformer",
        "Cadillac": "Cadillac",
        "Wunda chair": "Wunda chair",
        "Barrel/Spine": "Barrel/Spine"
    }
    chosen_equip_key = equip_map.get(equip, "기타")
    per_moves = [f"{chosen_equip_key} · {m}" for m in load_ex_db().get(chosen_equip_key, [])]
    chosen = st.multiselect("운동 동작(복수)", sorted(per_moves), key="per_moves")
    add_free = st.text_input("추가 동작(콤마 ,)", placeholder="예: Side bends, Mermaid", key="sess_addfree")

    spec_note = st.text_input("특이사항", value="", key="session_spec")
    homework  = st.text_input("숙제", value="", key="session_homework")
    memo      = st.text_area("메모(선택)", value="", height=60, key="session_memo")

    cancel = st.checkbox("취소", key="sess_cancel")
    reason = st.text_input("사유(선택)", value="", key="sess_reason")

    if st.button("세션 저장", use_container_width=True, key="sess_save_btn"):
        when = datetime.combine(s_day, s_time)
        # 사용자 정의 동작, DB에 누적
        if add_free.strip():
            new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
            exdb = load_ex_db()
            exdb.setdefault("기타", [])
            for nm in new_moves:
                if nm not in exdb["기타"]:
                    exdb["기타"].append(nm)
            save_ex_db(exdb)

        gross, net = calc_pay(s_site, s_type, int(headcount))
        if onth:
            gross = net = 0.0

        row = pd.DataFrame([{
            "id": ensure_id(sessions),
            "날짜": when,
            "지점": s_site,
            "구분": s_type,
            "이름": s_mname if s_type=="개인" else "",
            "인원": int(headcount) if s_type=="그룹" else 1,
            "레벨": level,
            "기구": equip,
            "동작(리스트)": "; ".join(chosen),
            "추가동작": add_free,
            "특이사항": spec_note,
            "숙제": homework,
            "메모": memo,
            "취소": bool(cancel),
            "사유": reason,
            "분": int(minutes),
            "온더하우스": bool(onth),
            "페이(총)": float(gross),
            "페이(실수령)": float(net)
        }])
        sessions = pd.concat([sessions, row], ignore_index=True)
        save_sessions(sessions)

        # 개인 차감(취소 아니고, 무료 아니고, 개인)
        if (s_type=="개인") and s_mname and (not cancel) and (not onth) and (s_mname in members["이름"].values):
            idx = members.index[members["이름"]==s_mname][0]
            remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
            members.loc[idx,"남은횟수"] = str(remain)
            save_members(members)

        st.success("세션 저장 완료!")

    st.subheader("최근 세션")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        view = sessions.sort_values("날짜", ascending=False).copy()
        # 수입 컬럼 숨김
        hide_cols = ["페이(총)","페이(실수령)"]
        show_cols = [c for c in view.columns if c not in hide_cols]
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 👥 멤버
# -----------------------------------------------------------------------------
elif st.session_state.page == "member":
    st.subheader("👥 멤버 관리")

    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])
        with left:
            names = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", names, key="mem_sel")
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel, key="mem_name")
            # 전화번호(비워도 저장 가능)
            default_phone = ""
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_phone = members.loc[members["이름"]==sel,"연락처"].iloc[0]
            phone = st.text_input("연락처(선택)", value=default_phone, placeholder="010-0000-0000", key="mem_phone")
            # 중복 체크 (비어있으면 생략)
            if phone.strip() and (members[(members["연락처"]==phone.strip()) & (members["이름"]!=name)].shape[0] > 0):
                st.error("⚠️ 동일한 전화번호가 이미 존재합니다.")
        with right:
            default_site = "F"
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_site = members.loc[members["이름"]==sel,"기본지점"].iloc[0] or "F"
            site = st.selectbox("기본 지점", [SITE_LABEL[s] for s in SITES],
                                index=SITES.index(default_site), key="mem_site")
            site = site.split()[0]
            reg_default = date.today()
            if sel!="(새 회원)" and sel in members["이름"].values:
                try:
                    reg_default = pd.to_datetime(members.loc[members["이름"]==sel,"등록일"].iloc[0]).date()
                except Exception:
                    pass
            reg_date = st.date_input("등록일", reg_default, key="mem_regdate")
            add_cnt = st.number_input("재등록(+횟수)", 0, 100, 0, 1, key="mem_addcnt")

        # 신규 등록 시 초기 횟수 입력
        init_cnt = 0
        if sel=="(새 회원)":
            init_cnt = st.number_input("처음 등록 횟수", 0, 100, 0, 1, key="mem_initcnt")

        note = st.text_input("메모(선택)",
                             value="" if sel=="(새 회원)" else members.loc[members["이름"]==sel,"메모"].iloc[0]
                             if (sel in members["이름"].values) else "", key="member_note")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True, key="mem_save"):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                else:
                    if sel=="(새 회원)":
                        row = pd.DataFrame([{
                            "id": ensure_id(members),
                            "이름":name.strip(),"연락처":phone.strip(),
                            "기본지점":site,"등록일":reg_date.isoformat(),
                            "총등록": str(int(init_cnt)),
                            "남은횟수": str(int(init_cnt)),
                            "회원유형":"일반",
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
            if st.button("재등록(+횟수 반영)", use_container_width=True, disabled=(sel=="(새 회원)"), key="mem_redo"):
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
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [], key="mem_del_sel")
            if st.button("멤버 삭제", use_container_width=True, disabled=members.empty, key="mem_del_btn"):
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

# -----------------------------------------------------------------------------
# 📋 리포트 (회원 동작만)
# -----------------------------------------------------------------------------
elif st.session_state.page == "report":
    st.subheader("📋 리포트 (회원 동작)")

    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        col = st.columns([1,1,2])
        with col[0]:
            pick_name = st.selectbox("회원 선택", sorted([n for n in sessions["이름"].unique() if str(n).strip()]), key="rep_pick_name")
        with col[1]:
            pick_month = st.date_input("월 선택", value=date.today().replace(day=1), key="rep_month")

        if pick_name:
            month_start = datetime.combine(pick_month.replace(day=1), dtime.min)
            month_end = (month_start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

            dfm = sessions[(sessions["이름"]==pick_name) &
                           (sessions["날짜"]>=month_start) & (sessions["날짜"]<month_end)]
            # 동작 분해
            def explode_moves(s):
                out = []
                for v in s.dropna():
                    parts = [p.strip() for p in str(v).split(";") if p.strip()]
                    out += parts
                return out
            moves = explode_moves(dfm["동작(리스트)"])
            # 카테고리 제거 "Mat · X"
            clean = [m.split("·")[-1].strip() for m in moves]
            top = pd.Series(clean).value_counts().head(5) if len(clean)>0 else pd.Series(dtype=int)

            st.markdown(f"#### {pick_name} · {pick_month.strftime('%Y-%m')} Top5")
            if top.empty:
                st.caption("기록된 동작이 없습니다.")
            else:
                st.bar_chart(top)

            # 6개월 추이
            st.markdown("#### 최근 6개월 추이(Top5 묶음)")
            last6_start = (month_start - pd.DateOffset(months=5)).to_pydatetime()
            df6 = sessions[(sessions["이름"]==pick_name) &
                           (sessions["날짜"]>=last6_start) & (sessions["날짜"]<month_end)].copy()
            df6["YM"] = pd.to_datetime(df6["날짜"]).dt.strftime("%Y-%m")

            def to_rows(row):
                items = [p.strip() for p in str(row["동작(리스트)"]).split(";") if p.strip()]
                items = [i.split("·")[-1].strip() for i in items]
                return [(row["YM"], i) for i in items]

            records = []
            for _, r in df6.iterrows():
                records += to_rows(r)
            if records:
                dff = pd.DataFrame(records, columns=["YM","move"])
                pivot = dff.value_counts(["YM","move"]).reset_index(name="cnt")
                pivot = pivot.pivot(index="YM", columns="move", values="cnt").fillna(0).astype(int)
                st.line_chart(pivot)
            else:
                st.caption("동작 기록이 부족합니다.")

            # 세부표
            st.markdown("#### 세부표")
            view = dfm.copy()
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view[["날짜","레벨","기구","동작(리스트)","추가동작","특이사항","숙제","메모"]],
                         use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 🍒 수입
# -----------------------------------------------------------------------------
elif st.session_state.page == "cherry":
    st.header("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****", key="ch_pin")
        if st.button("열기", key="ch_open"):
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
