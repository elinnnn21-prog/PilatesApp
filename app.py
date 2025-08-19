# app.py
import os
from pathlib import Path
from datetime import datetime, date, time as dtime, timedelta
from typing import List, Dict

import pandas as pd
import streamlit as st

# =========================
# 기본 설정 (브라우저 탭 아이콘/제목)
# =========================
st.set_page_config(page_title="✨ Pilates Manager", page_icon="✨", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV   = DATA_DIR / "members.csv"
SESSIONS_CSV  = DATA_DIR / "sessions.csv"
SCHEDULE_CSV  = DATA_DIR / "schedule.csv"
EX_JSON       = DATA_DIR / "pilates_exercises.json"

# 🍒 PIN (secrets.toml에 CHERRY_PW 있으면 그 값, 없으면 기본)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

# 지점 코드/라벨/색상
SITES = ["F", "R", "V"]  # F: 플로우, R: 리유, V: 방문
SITE_LABEL = {"F":"F", "R":"R", "V":"V"}
SITE_COLOR = {"F":"#d9f0ff", "R":"#eeeeee", "V":"#e9fbe9"}

# 상태 뱃지 색상
BADGE_COLOR = {
    "예약됨": "#3b82f6",  # 파랑
    "완료":   "#22c55e",  # 초록
    "취소됨": "#9ca3af",  # 회색
    "No Show":"#ef4444",  # 빨강
}

def badge_html(text: str) -> str:
    color = BADGE_COLOR.get(text, "#999")
    return f'<span style="display:inline-block; padding:2px 8px; border-radius:8px; font-size:12px; color:white; background:{color}">{text}</span>'

# -------- iCal(ICS) 내보내기 헬퍼 --------
from datetime import timezone

def _fmt_ics_dt(dt):
    # Asia/Seoul 기준 '떠있는 로컬시간' 문자열 (대부분 캘린더에서 정상 인식)
    return dt.strftime("%Y%m%dT%H%M%S")

def build_ics_from_df(df: pd.DataFrame, default_minutes: int = 50) -> bytes:
    """
    현재 화면에 보이는 스케줄 DataFrame(df) -> .ics 바이너리 생성
    - '취소'/취소됨 건은 df에서 미리 제외해서 넘겨줘.
    - 종료시간은 '분' 컬럼이 있으면 반영, 없으면 default_minutes 사용.
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

        title_bits = []
        # 이름(개인이면) / 그룹이면 (그룹)
        title_bits.append(r["이름"] if str(r.get("이름","")).strip() else "(그룹)")
        # 지점 표기(F/R/V)나 한글지점 중 하나가 있을 수 있음
        if "지점" in r and str(r["지점"]).strip():
            title_bits.append(str(r["지점"]))
        # 구분(개인/그룹)
        if "구분" in r and str(r["구분"]).strip():
            title_bits.append(str(r["구분"]))

        summary = " · ".join([x for x in title_bits if x])
        description_bits = []
        for col in ["레벨","기구","특이사항","숙제","메모"]:
            if col in df.columns and str(r.get(col,"")).strip():
                description_bits.append(f"{col}: {r[col]}")
        description = "\\n".join(description_bits)

        lines += [
            "BEGIN:VEVENT",
            f"UID:{r.get('id','')}-{_fmt_ics_dt(start)}@pilatesapp",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{_fmt_ics_dt(start)}",
            f"DTEND:{_fmt_ics_dt(end)}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode("utf-8")

# -----------------------------
# 동작 DB(JSON) 로딩/저장 유틸
# -----------------------------
EQUIP_ALIASES = {
    "Reformer": "Reformer",
    "Cadillac": "Cadillac",
    "Wunda chair": "Wunda Chair",
    "Wunda Chair": "Wunda Chair",
    "Barrel/Spine": None,  # 묶음 처리 (Ladder/Spine/Small)
    "Ladder Barrel": "Ladder Barrel",
    "Spine Corrector": "Spine Corrector",
    "Small Barrel": "Small Barrel",
    "Mat": "Mat",
    "Magic Circle": "Magic Circle",
    "Arm Chair": "Arm Chair",
    "High/Electric Chair": "High/Electric Chair",
    "Ped-O-Pul": "Ped-O-Pul",
    "Foot Corrector": "Foot Corrector",
    "Toe Corrector": "Toe Corrector",
    "Neck Stretcher": "Neck Stretcher",
    "기타": "기타",
}

def load_ex_db() -> Dict[str, List[str]]:
    if EX_JSON.exists():
        import json
        with open(EX_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 값 보정
        for k, v in list(data.items()):
            if not isinstance(v, list):
                data[k] = []
            else:
                data[k] = [str(x) for x in v]
        # 최소 키 보장
        for k in [
            "Mat","Reformer","Cadillac","Wunda Chair","Ladder Barrel","Spine Corrector","Small Barrel",
            "Magic Circle","Arm Chair","High/Electric Chair","Ped-O-Pul","Foot Corrector",
            "Toe Corrector","Neck Stretcher","기타"
        ]:
            data.setdefault(k, [])
        return data
    # 없으면 최소 구조 생성
    base = {
        "Mat": [],
        "Reformer": [],
        "Cadillac": [],
        "Wunda Chair": [],
        "Ladder Barrel": [],
        "Spine Corrector": [],
        "Small Barrel": [],
        "Magic Circle": [],
        "Arm Chair": [],
        "High/Electric Chair": [],
        "Ped-O-Pul": [],
        "Foot Corrector": [],
        "Toe Corrector": [],
        "Neck Stretcher": [],
        "기타": [],
    }
    save_ex_db(base)
    return base

def save_ex_db(db: Dict[str, List[str]]):
    import json
    with open(EX_JSON, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def moves_for_equipment(ex_db: Dict[str, List[str]], equip_label: str) -> List[str]:
    # Barrel/Spine 묶음
    if equip_label == "Barrel/Spine":
        a = ex_db.get("Ladder Barrel", [])
        b = ex_db.get("Spine Corrector", [])
        c = ex_db.get("Small Barrel", [])
        return sorted(list(dict.fromkeys(a + b + c)))
    key = EQUIP_ALIASES.get(equip_label)
    if key is None:
        return []
    return sorted(ex_db.get(key, []))

# -----------------------------
# 파일/데이터 유틸
# -----------------------------
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)

    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형","메모",
            "재등록횟수","최근재등록일"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","메모","취소","사유","분","온더하우스",
            "페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    if not SCHEDULE_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","메모","온더하우스","상태"
        ]).to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

    if not EX_JSON.exists():
        load_ex_db()  # 최소 구조 생성

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
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["온더하우스"] = df["온더하우스"].astype(str).str.lower().isin(["true","1","y","yes"])
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
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
    return df

def save_schedule(df: pd.DataFrame):
    out = df.copy()
    if not out.empty:
        out["날짜"] = pd.to_datetime(out["날짜"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(SCHEDULE_CSV, index=False, encoding="utf-8-sig")

def ensure_id(df: pd.DataFrame) -> str:
    return str(1 if df.empty else (df["id"].astype(int).max() + 1))

ensure_files()

# -----------------------------
# 공용 UI
# -----------------------------
def big_info(msg, kind="info"):
    if kind=="warn":
        st.warning(msg)
    elif kind=="error":
        st.error(msg)
    else:
        st.info(msg)

def chip(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def calc_pay(site: str, session_type: str, headcount: int) -> tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 35,000, 3.3% 공제
    R(리유): 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣(=2명) 35,000
    V(방문): 여기선 페이 정책이 없으니 0 처리 (원하면 멤버별 커스텀 로직 추가 가능)
    """
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            gross = net = 30000.0
        else:
            if headcount == 2:
                gross = net = 35000.0  # 듀엣
            else:
                mapping = {3:40000.0, 2:30000.0, 1:25000.0}
                gross = net = mapping.get(headcount, 30000.0)
    else:  # V
        gross = net = 0.0
    return gross, net

# -----------------------------
# 데이터 로드
# -----------------------------
members  = load_members()
sessions = load_sessions()
schedule = load_schedule()
ex_db    = load_ex_db()

# -----------------------------
# ----------------- 사이드바: 깔끔한 단일 메뉴 -----------------
# CSS (불릿 X, 버튼 스타일 깔끔)
st.markdown("""
<style>
.sidebar-menu-item { display:block; padding:6px 8px; font-size:19px; }
.sidebar-menu-active { font-weight:800; color:#ff4b4b; }
.sidebar-spacer { height:6px; }
</style>
""", unsafe_allow_html=True)

# 첫 페이지 기본값
if "page" not in st.session_state:
    st.session_state.page = "schedule"  # 처음엔 스케줄

st.sidebar.markdown("## 메뉴")

def menu_item(label: str, key: str, emoji_only: bool=False):
    """활성일 땐 텍스트(굵게/빨강)만, 비활성일 땐 버튼 1개만."""
    show = label if not emoji_only else label.split()[0]
    active = (st.session_state.page == key)
    if active:
        st.sidebar.markdown(
            f"<div class='sidebar-menu-item sidebar-menu-active'>{show}</div>",
            unsafe_allow_html=True
        )
    else:
        if st.sidebar.button(show, key=f"menu_{key}"):
            st.session_state.page = key
    st.sidebar.markdown("<div class='sidebar-spacer'></div>", unsafe_allow_html=True)

# 실제 메뉴(🍒만 이모지 단독)
menu_item("📅 스케줄", "schedule")
menu_item("✍️ 세션",   "session")
menu_item("👥 멤버",    "member")
menu_item("📋 리포트",  "report")
menu_item("🍒",        "cherry", emoji_only=True)
# ------------------------------------------------------------

# =========================================================
# 📅 스케줄 (간소화 + 자동 지점)
# =========================================================
if st.session_state.page == "schedule":
    st.subheader("📅 스케줄")

    # 보기 전환/기간 선택
    vcols = st.columns([1,1,2,1])
    with vcols[0]:
        view_mode = st.radio("보기", ["일","주","월"], horizontal=True, index=1, label_visibility="collapsed")
    with vcols[1]:
        base = st.date_input("기준", value=date.today(), label_visibility="collapsed")

    base_dt = datetime.combine(base, dtime.min)
    if view_mode=="일":
        start, end = base_dt, base_dt + timedelta(days=1)
    elif view_mode=="주":
        start = base_dt - timedelta(days=base_dt.weekday())
        end   = start + timedelta(days=7)
    else:
        start = base_dt.replace(day=1)
        end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

    st.markdown("#### ✨ 예약 등록")
    c = st.columns([1,1,1,2,1])
    with c[0]:
        sdate = st.date_input("날짜", value=base)
    with c[1]:
        stime = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0))
    with c[2]:
        stype = st.radio("구분", ["개인","그룹"], horizontal=True)
    with c[3]:
        if stype=="개인":
            mname = st.selectbox("이름(개인)", members["이름"].tolist() if not members.empty else [])
            # 지점 자동
            auto_site = "F"
            if mname and (mname in members["이름"].values):
                try:
                    auto_site = members.loc[members["이름"]==mname, "기본지점"].iloc[0] or "F"
                except Exception:
                    auto_site = "F"
            st.text_input("지점(자동)", value=SITE_LABEL[auto_site], disabled=True)
            site = auto_site
        else:
            mname = ""
            site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES], index=0)
            site = site.split()[0]
    with c[4]:
        headcount = st.number_input("인원(그룹)", 1, 10, 1 if stype=="개인" else 2, 1, disabled=(stype=="개인"))

    memo = st.text_input("메모", value="")  # 숙제/레벨/기구 제거

    if st.button("예약 추가", use_container_width=True):
        when = datetime.combine(sdate, stime)
        row = pd.DataFrame([{
            "id": ensure_id(schedule),
            "날짜": when,
            "지점": site,
            "구분": stype,
            "이름": mname if stype=="개인" else "",
            "인원": int(headcount) if stype=="그룹" else 1,
            "메모": memo,
            "온더하우스": False,
            "상태": "예약됨"
        }])
        schedule = pd.concat([schedule, row], ignore_index=True)
        save_schedule(schedule)
        st.success("예약을 추가했습니다.")

    st.markdown("#### 📋 일정")
    v = schedule[(schedule["날짜"]>=start) & (schedule["날짜"]<end)].copy().sort_values("날짜")
    if v.empty:
        big_info("해당 기간에 일정이 없습니다.")
    else:
        for _, r in v.iterrows():
            name_html = f'<b style="font-size:16px">{r["이름"] if r["이름"] else "(그룹)"}</b>'
            site_chip = chip(r["지점"], SITE_COLOR.get(r["지점"], "#eee"))
            title = f'{pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")} · {site_chip} · {name_html}'
            sub = f'구분: {r["구분"]}'
            if r["메모"]:
                sub += f' · 메모: {r["메모"]}'
            if r["상태"]=="취소됨":
                title = f"<s>{title}</s>"

            colA, colB, colC, colD = st.columns([3,1,1,1])
            with colA:
                st.markdown(f"{title}<br><span style='color:#bbb'>{sub}</span><br><span>상태: <b>{r['상태']}</b></span>", unsafe_allow_html=True)
            with colB:
                if st.button("출석", key=f"att_{r['id']}"):
                    # 세션 자동 생성 (출석=완료)
                    gross, net = calc_pay(r["지점"], r["구분"], int(r["인원"]))
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
                        "메모": r["메모"],
                        "취소": False,
                        "사유": "",
                        "분": 50,
                        "온더하우스": False,
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)
                    # 횟수 차감(개인)
                    if (r["구분"]=="개인") and (r["이름"] in members["이름"].values):
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
                        "특이사항": "No Show",
                        "메모": r["메모"],
                        "취소": False,
                        "사유": "No Show",
                        "분": 50,
                        "온더하우스": False,
                        "페이(총)": float(gross),
                        "페이(실수령)": float(net)
                    }])
                    sessions = pd.concat([sessions, sess], ignore_index=True)
                    save_sessions(sessions)
                    # 횟수 차감(개인)
                    if (r["구분"]=="개인") and (r["이름"] in members["이름"].values):
                        idx = members.index[members["이름"]==r["이름"]][0]
                        remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                        members.loc[idx,"남은횟수"] = str(remain)
                        save_members(members)
                    schedule.loc[schedule["id"]==r["id"], "상태"] = "No Show"
                    save_schedule(schedule)
                    st.experimental_rerun()

# =========================================================
# ✍️ 세션 (여러 기구 동시 + 기구별 동작 유지)
# =========================================================
elif st.session_state.page == "session":
    st.subheader("✍️ 세션 기록")

    if "equip_multi" not in st.session_state:
        st.session_state.equip_multi = []           # 선택된 기구들
    if "equip_moves_map" not in st.session_state:
        st.session_state.equip_moves_map = {}       # {equip: [moves...]}

    cols = st.columns(4)
    with cols[0]:
        day = st.date_input("날짜", value=date.today())
        tval = st.time_input("시간", value=datetime.now().time().replace(second=0, microsecond=0))
    with cols[1]:
        s_type = st.radio("구분", ["개인","그룹"], horizontal=True)
    with cols[2]:
        if s_type=="개인":
            mname = st.selectbox("멤버", members["이름"].tolist() if not members.empty else [])
            auto_site = "F"
            if mname and (mname in members["이름"].values):
                try:
                    auto_site = members.loc[members["이름"]==mname, "기본지점"].iloc[0] or "F"
                except Exception:
                    auto_site = "F"
            st.text_input("지점(자동)", value=SITE_LABEL[auto_site], disabled=True)
            site = auto_site
        else:
            mname = ""
            site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES], index=0)
            site = site.split()[0]
    with cols[3]:
        minutes = st.number_input("분", 10, 180, 50, 5)

    c2 = st.columns([2,2])
    with c2[0]:
        level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"])
    with c2[1]:
        headcount = st.number_input("인원(그룹)", 1, 10, 1 if s_type=="개인" else 2, 1, disabled=(s_type=="개인"))

    # --- 여러 기구 선택 + 기구별 동작 유지 ---
    all_equip_options = ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat",
                         "Magic Circle","Arm Chair","High/Electric Chair","Ped-O-Pul",
                         "Foot Corrector","Toe Corrector","Neck Stretcher","기타"]
    st.session_state.equip_multi = st.multiselect("기구(복수 선택)", all_equip_options, default=st.session_state.equip_multi)

    # 기구별 동작 선택 위젯들
    ex_db = load_ex_db()
    for eq in st.session_state.equip_multi:
        moves = moves_for_equipment(ex_db, eq)
        # 기 저장값 불러오기
        prev = st.session_state.equip_moves_map.get(eq, [])
        chosen = st.multiselect(f"동작 - {eq}", options=moves, default=prev, key=f"mv_{eq}")
        st.session_state.equip_moves_map[eq] = chosen

    # 선택된 모든 동작 합치기
    chosen_all = []
    for eq in st.session_state.equip_multi:
        chosen_all.extend(st.session_state.equip_moves_map.get(eq, []))
    chosen_all = list(dict.fromkeys(chosen_all))  # 중복 제거

    add_free = st.text_input("추가 동작(콤마 , 로 구분)", placeholder="예: Mermaid, Side bends")
    spec = st.text_input("특이사항(선택)", value="")
    memo = st.text_area("메모(선택)", height=80)

    # 저장
    if st.button("세션 저장", use_container_width=True):
        when = datetime.combine(day, tval)

        # 사용자가 텍스트로 추가한 동작 → JSON DB에 누적
        if add_free.strip():
            new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
            exdb = load_ex_db()
            exdb.setdefault("기타", [])
            for nm in new_moves:
                if nm not in exdb["기타"]:
                    exdb["기타"].append(nm)
            save_ex_db(exdb)

        gross, net = calc_pay(site, s_type, int(headcount))
        row = pd.DataFrame([{
            "id": ensure_id(sessions),
            "날짜": when,
            "지점": site,
            "구분": s_type,
            "이름": mname if s_type=="개인" else "",
            "인원": int(headcount) if s_type=="그룹" else 1,
            "레벨": level,
            "기구": ", ".join(st.session_state.equip_multi),
            "동작(리스트)": "; ".join(chosen_all),
            "추가동작": add_free,
            "특이사항": spec,
            "메모": memo,
            "취소": False,
            "사유": "",
            "분": int(minutes),
            "온더하우스": False,
            "페이(총)": float(gross),
            "페이(실수령)": float(net)
        }])
        sessions = pd.concat([sessions, row], ignore_index=True)
        save_sessions(sessions)

        # 개인 세션이면 남은횟수 차감
        if s_type=="개인" and mname and (mname in members["이름"].values):
            idx = members.index[members["이름"]==mname][0]
            remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
            members.loc[idx,"남은횟수"] = str(remain)
            save_members(members)

        st.success("세션이 저장되었습니다.")

    st.markdown("#### 최근 세션")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        view = sessions.sort_values("날짜", ascending=False).copy()
        hide_cols = ["페이(총)","페이(실수령)"]
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(view[[c for c in view.columns if c not in hide_cols]], use_container_width=True, hide_index=True)

# =========================================================
# 👥 멤버
# =========================================================
elif st.session_state.page == "member":
    st.subheader("👥 멤버 관리")

    with st.expander("➕ 등록/수정/재등록/삭제", expanded=True):
        left, right = st.columns([1,1])
        with left:
            names = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", names)
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel)
            # 전화 중복 경고
            default_phone = ""
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_phone = members.loc[members["이름"]==sel, "연락처"].iloc[0]
            phone = st.text_input("연락처", value=default_phone, placeholder="010-0000-0000")
            if phone and (members[(members["연락처"]==phone) & (members["이름"]!=name)].shape[0] > 0):
                st.error("⚠️ 동일한 전화번호가 이미 존재합니다.")

        with right:
            default_site = "F"
            if sel!="(새 회원)" and sel in members["이름"].values:
                default_site = members.loc[members["이름"]==sel, "기본지점"].iloc[0] or "F"
            site = st.selectbox("기본 지점", [SITE_LABEL[s] for s in SITES], index=SITES.index(default_site))
            site = site.split()[0]
            reg_default = date.today()
            if sel!="(새 회원)" and sel in members["이름"].values:
                try:
                    reg_default = pd.to_datetime(members.loc[members["이름"]==sel, "등록일"].iloc[0]).date()
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
                            "id": ensure_id(members if not members.empty else pd.DataFrame(columns=["id"])),
                            "이름": name.strip(), "연락처": phone.strip(),
                            "기본지점": site, "등록일": reg_date.isoformat(),
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

# =========================================================
# 📋 리포트 (회원 동작 위주 간단 표)
# =========================================================
elif st.session_state.page == "report":
    st.subheader("📋 리포트 (회원 동작)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        who = st.selectbox("회원 선택", sorted([x for x in sessions["이름"].unique() if x]))
        if who:
            df = sessions[(sessions["이름"]==who) & (~sessions["취소"])].copy()
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            # 동작 컬럼 분해
            rows = []
            for _, r in df.iterrows():
                base = [x.strip() for x in (r["동작(리스트)"] or "").split(";") if x.strip()]
                for b in base:
                    rows.append({"YM":r["YM"], "동작":b})
            if rows:
                tmp = pd.DataFrame(rows)
                top = tmp.groupby(["YM","동작"]).size().reset_index(name="횟수")
                st.dataframe(top.sort_values(["YM","횟수"], ascending=[True,False]), use_container_width=True, hide_index=True)
            else:
                big_info("기록된 동작이 없습니다.")

# =========================================================
# 🍒 (PIN 잠금)
# =========================================================
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
            df["Y"]  = pd.to_datetime(df["날짜"]).dt.year
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            month_sum = df.groupby("YM")["페이(실수령)"].sum().astype(int).reset_index()
            year_sum  = df.groupby("Y")["페이(실수령)"].sum().astype(int).reset_index()
            col1, col2 = st.columns(2)
            with col1:
                st.caption("월별 합계")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with col2:
                st.caption("연도 합계")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.caption("상세")
            detail = df.sort_values("날짜", ascending=False).copy()
            detail["날짜"] = pd.to_datetime(detail["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(detail, use_container_width=True, hide_index=True)



