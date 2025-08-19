# app.py
from __future__ import annotations
import os, json, base64, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

def _norm_phone(s: str) -> str:
    """하이픈/공백 제거하고 숫자만 남겨 비교용으로 사용"""
    if s is None:
        return ""
    return "".join(ch for ch in str(s) if ch.isdigit())

# ─────────────────────────────────────────────────────────────────────
# 기본 셋업
# ───────────브라우저 아이콘
st.set_page_config(page_title="Pilates Manager", page_icon="✨", layout="wide") 


DATA_DIR     = Path(".")
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
EX_JSON      = DATA_DIR / "exercise_db.json"
CHERRY_PIN   = st.secrets.get("CHERRY_PW", "2974")

# 사이트 표기: F/R/V
SITES = ["F", "R", "V"]                          # Flow / Re-YOU / Visit
SITE_LABEL = {"F":"F (플로우)", "R":"R (리유)", "V":"V (방문)"}
SITE_COLOR = {"F":"#d9f0ff", "R":"#f0f0f0", "V":"#e9fbe9"}

#(간단 기본 동작 DB – 기존 exercise_db.json 있으면 그것 사용)
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat(Basic)": ["Roll down", "The hundred", "Single leg circles"],
    "Reformer":   ["Footwork series", "The hundred", "Coordination"],
    "Cadillac":   ["Roll back", "Leg spring series"],
    "Wunda chair": ["Push down", "Pull up"],
    "Spine/Barrel": ["Swan", "Side sit up"],
    "기타": []
}

# 방문 실수령은 🍒 탭에서 설정/저장 (파일)
CHERRY_CONFIG = DATA_DIR / "cherry_config.json"


# ─────────────────────────────────────────────────────────────────────
# 파일/데이터 유틸
# ─────────────────────────────────────────────────────────────────────
MEMBER_COLS = [
    "id","이름","연락처","기본지점","등록일","총등록","남은횟수","회원유형",  # 회원유형: 일반/방문
    "메모","재등록횟수","최근재등록일"
]
SESSION_COLS = [
    "id","날짜","지점","구분","이름","인원","레벨","기구",
    "동작(리스트)","추가동작","특이사항","숙제","취소","사유","분","페이(총)","페이(실수령)"
]

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)

    # 멤버 CSV
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=MEMBER_COLS).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    else:
        df = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
        # 스키마 업그레이드(누락 컬럼 생성)
        for c in MEMBER_COLS:
            if c not in df.columns:
                df[c] = ""
        # 예전 한글 지점 → F/R/V 로 변환
        if "기본지점" in df.columns:
            df["기본지점"] = df["기본지점"].replace({"플로우":"F","리유":"R","방문":"V"})
        df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # 세션 CSV
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=SESSION_COLS).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    else:
        df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
        for c in SESSION_COLS:
            if c not in df.columns:
                df[c] = ""
        # 지점 값 정규화
        if "지점" in df.columns:
            df["지점"] = df["지점"].replace({"플로우":"F","리유":"R","방문":"V"})
        df.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    # 동작 DB
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

    # 🍒 설정 파일(방문 실수령)
    if not CHERRY_CONFIG.exists():
        json.dump({"visit_pay": 0}, CHERRY_CONFIG.open("w", encoding="utf-8"), ensure_ascii=False)

def load_members() -> pd.DataFrame:
    return pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if df.empty:
        return df
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    for c in ["인원","분","페이(총)","페이(실수령)"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["취소"] = df["취소"].astype(str).str.lower().isin(["1","true","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    df = df.copy()
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        raw = pd.read_json(EX_JSON, typ="series")
        return {k:list(v) for k,v in raw.items()}
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EX_JSON, force_ascii=False)

def load_cherry_cfg() -> Dict[str,int]:
    try:
        return json.load(CHERRY_CONFIG.open("r", encoding="utf-8"))
    except Exception:
        return {"visit_pay": 0}

def save_cherry_cfg(cfg: Dict[str,int]):
    json.dump(cfg, CHERRY_CONFIG.open("w", encoding="utf-8"), ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────
# 페이 계산
# ─────────────────────────────────────────────────────────────────────
def calc_pay(site: str, session_type: str, headcount: int, visit_pay_cfg: int) -> Tuple[float,float]:
    """
    returns (gross, net)
    F: 회당 35,000 (3.3% 공제) – 개인만 의미 있음
    R: 개인 30,000 / 그룹(3명=40,000, 2명=30,000, 1명=25,000) – 공제 없음
    V: 🍒 설정의 visit_pay 사용(개인), 그룹이면 0
    """
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            gross = net = 30000.0
        else:
            if headcount == 3:
                gross = net = 40000.0
            elif headcount == 2:
                gross = net = 30000.0
            else:
                gross = net = 25000.0
    else: # V
        if session_type == "개인":
            gross = net = float(visit_pay_cfg or 0)
        else:
            gross = net = 0.0
    return gross, net


# ─────────────────────────────────────────────────────────────────────
# iCal(ICS) 생성 & (선택) GitHub Pages 업로드
# ─────────────────────────────────────────────────────────────────────
def df_to_ics(df: pd.DataFrame) -> str:
    from uuid import uuid4
    if df.empty: 
        return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//PilatesApp//EN\r\nEND:VCALENDAR"
    lines = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//PilatesApp//EN"]
    df = df.sort_values("날짜")
    for _, r in df.iterrows():
        if bool(r.get("취소", False)):  # 취소는 제외
            continue
        start = pd.to_datetime(r["날짜"])
        end   = start + timedelta(minutes=int(r.get("분", 50) or 50))
        title = f'{r.get("지점","")} {r.get("구분","")}'
        if str(r.get("이름","")).strip():
            title += f' · {r["이름"]}'
        if str(r.get("기구","")).strip():
            title += f' · {r["기구"]}'
        desc_parts = []
        for k in ["동작(리스트)","추가동작","특이사항","숙제"]:
            v = str(r.get(k,"")).strip()
            if v: desc_parts.append(f'{k}:{v}')
        desc = " | ".join(desc_parts)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid4()}",
            f"DTSTAMP:{start.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID=Asia/Seoul:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID=Asia/Seoul:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)

def push_ics_to_github(ics_text: str) -> Tuple[bool, str]:
    """시크릿이 있으면 GitHub API로 gh-pages(또는 지정 브랜치)에 schedule.ics 업로드."""
    token  = st.secrets.get("GITHUB_TOKEN")
    repo   = st.secrets.get("ICS_REPO")      # "user/repo"
    branch = st.secrets.get("ICS_BRANCH", "gh-pages")
    path   = st.secrets.get("ICS_PATH", "schedule.ics")
    if not token or not repo:
        return False, "GitHub 시크릿이 설정되어 있지 않습니다."

    api = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
    # 기존 SHA 조회
    sha = None
    try:
        req = urllib.request.Request(api + f"?ref={branch}", headers=headers)
        with urllib.request.urlopen(req) as r:
            data = json.load(r)
            sha = data.get("sha")
    except urllib.error.HTTPError:
        sha = None

    body = {
        "message": "Auto update schedule.ics",
        "content": base64.b64encode(ics_text.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    req = urllib.request.Request(api, data=json.dumps(body).encode("utf-8"),
                                 headers=headers, method="PUT")
    try:
        urllib.request.urlopen(req).read()
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        return True, raw_url
    except Exception as e:
        return False, f"업로드 실패: {e}"


# ─────────────────────────────────────────────────────────────────────
# 공용 UI
# ─────────────────────────────────────────────────────────────────────
def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def big_info(msg: str, kind="info"):
    if kind == "warn": st.warning(msg)
    elif kind == "error": st.error(msg)
    else: st.info(msg)


# ─────────────────────────────────────────────────────────────────────
# 사이드바: “버튼만” 메뉴 (불릿/네모 제거, 활성은 텍스트만 빨간/굵게)
# ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 사이드바 버튼을 ‘링크처럼’ 보이게 */
.sidebar-plain-btn {
  display:block; width:100%; text-align:left; 
  border:none; background:transparent; 
  padding:8px 2px; margin:2px 0; 
  font-size:20px; cursor:pointer;
}
.sidebar-plain-btn:hover { color:#FF4B4B; font-weight:700; }
.sidebar-active { font-size:22px; font-weight:800; color:#FF4B4B; padding:8px 2px; }
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "schedule"  # 첫 페이지 스케줄

st.sidebar.markdown("## 메뉴")

def menu_link(label: str, key: str, emoji_only: bool=False):
    """활성일 때는 텍스트만 한 줄, 비활성일 땐 버튼 1개만."""
    show = label if not emoji_only else label.split()[0]
    if st.session_state.page == key:
        st.sidebar.markdown(f'<div class="sidebar-active">{show}</div>', unsafe_allow_html=True)
    else:
        if st.sidebar.button(show, key=f"_menu_{key}", help=label, use_container_width=True):
            st.session_state.page = key

menu_link("📅 스케줄", "schedule")
menu_link("✍️ 세션",   "session")
menu_link("👥 멤버",    "member")
menu_link("📋 리포트", "report")
menu_link("🍒",       "cherry", emoji_only=True)
st.sidebar.markdown("---")

# 데이터 로드
ensure_files()
members  = load_members()
sessions = load_sessions()
ex_db    = load_ex_db()
cherry   = load_cherry_cfg()


# ─────────────────────────────────────────────────────────────────────
# 페이지: 스케줄
# ─────────────────────────────────────────────────────────────────────
if st.session_state.page == "schedule":
    st.header("📅 스케줄")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        # 보기 모드 & 기간
        mode = st.segmented_control("보기", options=["일","주","월"], default="주")
        base = st.date_input("기준 날짜", value=date.today())
        base_dt = datetime.combine(base, datetime.min.time())
        if mode=="일":
            start, end = base_dt, base_dt + timedelta(days=1)
        elif mode=="주":
            start = base_dt - timedelta(days=base_dt.weekday())
            end   = start + timedelta(days=7)
        else:
            start = base_dt.replace(day=1)
            end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

        view = sessions[(sessions["날짜"]>=start) & (sessions["날짜"]<end)].copy()
        if view.empty:
            big_info("해당 기간에 일정이 없습니다.")
        else:
            view = view.sort_values("날짜")
            def row_html(r):
                name = r["이름"] if str(r["이름"]).strip() else "(그룹)"
                name_html = f'<span style="font-size:16px; font-weight:800;">{name}</span>'
                site_chip = tag(r["지점"], SITE_COLOR.get(r["지점"], "#eee"))
                title = f'{pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")} · {site_chip} · {name_html}'
                body  = f'{r["구분"]} · {r["레벨"]} · {r["기구"]}'
                details = []
                for k in ["동작(리스트)","추가동작","특이사항","숙제"]:
                    v = str(r.get(k,"")).strip()
                    if v: details.append(v)
                if details:
                    body += " · " + ", ".join(details)
                if bool(r["취소"]):
                    title = f'<s>{title}</s>'
                return title, body

            rows = []
            for _, r in view.iterrows():
                t, b = row_html(r)
                rows.append(f"<div style='padding:10px; border-bottom:1px solid #333'>{t}<br><span style='color:#bbb'>{b}</span></div>")
            st.markdown("<div>"+ "".join(rows) +"</div>", unsafe_allow_html=True)

    # iCal 동기화
    st.subheader("🗓️ iCal 동기화")
    colA, colB = st.columns([1,1])
    with colA:
        if st.button("🔄 iCal 파일 생성", use_container_width=True):
            ics = df_to_ics(load_sessions())  # 저장 직전의 최신값 사용
            out = DATA_DIR / "schedule.ics"
            out.write_text(ics, encoding="utf-8")
            st.success("schedule.ics 생성 완료!")
            st.download_button("📥 iCal 다운로드", ics, file_name="schedule.ics", mime="text/calendar")
    with colB:
        if st.button("☁️ GitHub Pages로 업로드(선택)", use_container_width=True):
            ics = df_to_ics(load_sessions())
            ok, msg = push_ics_to_github(ics)
            if ok:
                st.success("업로드 완료! 아래 URL을 아이폰에서 구독하세요.")
                st.code(msg, language="text")
            else:
                st.error(msg)


# ─────────────────────────────────────────────────────────────────────
# 페이지: 세션
# ==========================================================
# ==========================================================
# ✍️ 세션 기록  (과거 기록 지원 + 날짜/시간 유지 + 장비별 동작 필터)
# ==========================================================
elif st.session_state.page == "session":
    st.header("✍️ 세션 기록")

    if members.empty:
        big_info("먼저 멤버를 등록하세요.")
    else:
        # ---------- 날짜/시간: 세션 상태로 유지 (리런되어도 안 초기화) ----------
        if "sess_day" not in st.session_state:
            st.session_state.sess_day = date.today()
        if "sess_time" not in st.session_state:
            st.session_state.sess_time = datetime.now().replace(second=0, microsecond=0).time()

        cols_top = st.columns([2,1,1,1,1])
        with cols_top[0]:
            st.session_state.sess_day = st.date_input("날짜", value=st.session_state.sess_day, key="sess_day_input")
        with cols_top[1]:
            if st.button("오늘"):
                st.session_state.sess_day = date.today()
                st.rerun()
        with cols_top[2]:
            if st.button("어제"):
                st.session_state.sess_day = date.today() - timedelta(days=1)
                st.rerun()
        with cols_top[3]:
            if st.button("-7일"):
                st.session_state.sess_day = date.today() - timedelta(days=7)
                st.rerun()
        with cols_top[4]:
            if st.button("-30일"):
                st.session_state.sess_day = date.today() - timedelta(days=30)
                st.rerun()

        st.session_state.sess_time = st.time_input(
            "시간",
            value=st.session_state.sess_time,
            step=timedelta(minutes=5),
            key="sess_time_input",
        )

        when = datetime.combine(st.session_state.sess_day, st.session_state.sess_time)

        if when.date() < date.today():
            st.caption("🕒 과거 세션을 기록 중입니다.")
        elif when > datetime.now():
            st.caption("⏭ 미래 일정으로 저장됩니다.")

        # ---------- 공통 입력 ----------
        c = st.columns([1,1,1,1])
        with c[0]:
            session_type = st.radio("구분", ["개인","그룹"], horizontal=True, key="sess_type")
        with c[1]:
            if session_type == "개인":
                mname = st.selectbox("멤버", members["이름"].tolist(), key="sess_member")
                auto_site = "F"
                if mname in members["이름"].values:
                    # 기본지점 or 지점 컬럼 사용
                    if "기본지점" in members.columns and members.loc[members["이름"]==mname,"기본지점"].iloc[0]:
                        auto_site = members.loc[members["이름"]==mname,"기본지점"].iloc[0]
                    elif "지점" in members.columns and members.loc[members["이름"]==mname,"지점"].iloc[0]:
                        auto_site = members.loc[members["이름"]==mname,"지점"].iloc[0]
                site = st.selectbox("지점", ["F","R","V"], index=["F","R","V"].index(auto_site))
            else:
                mname = ""
                site = st.selectbox("지점", ["F","R","V"], key="sess_site_group")
        with c[2]:
            level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"], key="sess_level")
        with c[3]:
            equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat","기타"], key="sess_equip")

        # 그룹 인원 / 개인은 1
        headcount = st.number_input(
            "인원(그룹)",
            min_value=1, max_value=10,
            value=(1 if session_type=="개인" else 2),
            step=1,
            disabled=(session_type=="개인"),
            key="sess_headcount"
        )

        # ---------- 장비별 동작 후보 필터링(개인만) + 자유 입력 ----------
        add_free = ""
        chosen = []
        if session_type == "개인":
            per_moves = []
            exdb = load_ex_db()
            want = equip.lower()  # 장비 키워드
            for cat, moves in exdb.items():
                cat_l = cat.lower()
                ok = (
                    (want in cat_l) or
                    ("mat" in want and "mat" in cat_l) or
                    ("기타" in cat_l) or
                    (equip == "Barrel/Spine" and ("barrel" in cat_l or "spine" in cat_l))
                )
                if ok:
                    per_moves += [f"{cat} · {m}" for m in moves]

            cols_move = st.columns([2,1])
            with cols_move[0]:
                chosen = st.multiselect("운동 동작(복수 선택)", sorted(per_moves), key="sess_moves")
            with cols_move[1]:
                add_free = st.text_input("추가 동작(,로 구분)", placeholder="예: Side bends, Mermaid", key="sess_addfree")

        # ---------- 특이/숙제/취소 ----------
        memo = st.text_area("특이사항", height=80, key="sess_memo")
        homework = st.text_area("숙제(개인)", height=60, disabled=(session_type=="그룹"), key="sess_homework")
        cancel = st.checkbox("취소", key="sess_cancel")
        reason = st.text_input("취소 사유(선택)", key="sess_reason")
        minutes = st.number_input("수업 분", 10, 180, 50, 5, key="sess_minutes")

        # ---------- 저장 ----------
        if st.button("세션 저장", use_container_width=True, key="sess_save_btn"):
            # 사용자 추가 동작 DB 반영(개인일 때만)
            if session_type=="개인" and add_free.strip():
                new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
                exdb2 = load_ex_db()
                exdb2.setdefault("기타", [])
                for nm in new_moves:
                    if nm not in exdb2["기타"]:
                        exdb2["기타"].append(nm)
                save_ex_db(exdb2)

            # 페이 계산
            gross, net = calc_pay(site, session_type, int(headcount), None)

            # 저장 레코드
            row = pd.DataFrame([{
                "id": str(len(sessions)+1),
                "날짜": when,
                "지점": site,
                "구분": session_type,
                "이름": mname if session_type=="개인" else "",
                "인원": int(headcount) if session_type=="그룹" else 1,
                "레벨": level,
                "기구": equip,
                "동작(리스트)": "; ".join(chosen) if session_type=="개인" else "",
                "추가동작": add_free if session_type=="개인" else "",
                "메모": (memo if session_type=="그룹" else (memo + (f"\n[숙제] {homework}" if homework.strip() else ""))),
                "취소": bool(cancel),
                "사유": reason,
                "분": int(minutes),
                "페이(총)": float(gross),
                "페이(실수령)": float(net)
            }])

            sessions_new = pd.concat([sessions, row], ignore_index=True)
            save_sessions(sessions_new)

            # 개인 & 취소 아님 → 남은횟수 차감
            if session_type=="개인" and mname and not cancel and (mname in members["이름"].values):
                idx = members.index[members["이름"]==mname][0]
                remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                members.loc[idx,"남은횟수"] = str(remain)
                save_members(members)

            st.success("세션 저장 완료!")

        # ---------- 최근 세션 표시 ----------
        st.subheader("최근 세션")
        view = load_sessions()
        if view.empty:
            big_info("세션 데이터가 없습니다.")
        else:
            view = view.sort_values("날짜", ascending=False).copy()
            hide_cols = ["페이(총)","페이(실수령)"]
            show_cols = [c for c in view.columns if c not in hide_cols]
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────
# 페이지: 멤버
# ─────────────────────────────────────────────────────────────────────
elif st.session_state.page == "member":
    st.header("👥 멤버 관리")

    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1, 1])

        # ---------------- 좌측: 회원 선택 + 이름/연락처 ----------------
        with left:
            names = ["(새 회원)"] + (members["이름"].tolist() if not members.empty else [])
            sel = st.selectbox("회원 선택", names, index=0)
            is_new = (sel == "(새 회원)")

            name = st.text_input("이름", "" if is_new else sel)

            # 선택된 회원의 기존 연락처 불러오기
            default_phone = ""
            if not is_new and sel in members["이름"].values:
                default_phone = members.loc[members["이름"] == sel, "연락처"].iloc[0]
            phone = st.text_input("연락처", value=default_phone, placeholder="010-0000-0000")

            # 연락처 중복 경고 (빈칸이면 검사 안 함, 숫자만 비교)
if phone.strip():
    phone_norm = _norm_phone(phone)
    # members에 저장된 연락처도 숫자만 추출해서 비교
    exists = members.copy()
    exists["_p"] = exists["연락처"].fillna("").apply(_norm_phone)
    # 신규일 땐 현재 name이 없음, 기존 수정일 땐 본인(name)은 제외
    current_name = "" if sel == "(새 회원)" else name.strip()
    dup = exists[(exists["_p"] == phone_norm) & (exists["이름"] != current_name)]
    if not dup.empty and phone_norm != "":   # 숫자가 하나라도 있을 때만
        st.warning(f"⚠️ 동일한 전화번호가 이미 존재합니다: {', '.join(dup['이름'].tolist())}")

        # ---------------- 우측: 지점/등록일/횟수 ----------------
        with right:
            # 기본지점(F/R/V) 표시는 라벨로, 값은 F/R/V 로 저장
            def _site_label(x): return {"F": "F(플로우)", "R": "R(리유)", "V": "V(방문)"}[x]
            default_site = "F"
            if not is_new and sel in members["이름"].values:
                default_site = members.loc[members["이름"] == sel, "기본지점"].iloc[0] or "F"
            site_shown = st.selectbox(
                "기본 지점",
                [_site_label(s) for s in SITES],  # SITES = ["F","R","V"]
                index=SITES.index(default_site),
            )
            site = site_shown.split("(")[0]  # "F(플로우)" -> "F"

            reg_default = date.today()
            if not is_new and sel in members["이름"].values:
                try:
                    reg_default = pd.to_datetime(members.loc[members["이름"] == sel, "등록일"].iloc[0]).date()
                except Exception:
                    reg_default = date.today()
            reg_date = st.date_input("등록일", reg_default)

            # ⭐ 신규면 '등록 횟수', 기존이면 '추가 횟수'
            cnt_label = "등록 횟수" if is_new else "추가 횟수"
            cnt_default = 10 if is_new else 1
            add_cnt = st.number_input(cnt_label, min_value=0, max_value=999, value=cnt_default, step=1)

        note = st.text_input(
            "메모(선택)",
            value="" if is_new else (
                members.loc[members["이름"] == sel, "메모"].iloc[0]
                if (sel in members["이름"].values) else ""
            )
        )

        # ---------------- 버튼들 ----------------
        c1, c2, c3 = st.columns(3)

        # 저장/수정
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                elif not phone.strip():
                    st.error("연락처를 입력하세요.")
                else:
                    if is_new:
                        # 신규: 총등록/남은횟수 = '등록 횟수'
                        row = pd.DataFrame([{
                            "id": str(len(members) + 1),
                            "이름": name.strip(),
                            "연락처": phone.strip(),
                            "기본지점": site,
                            "등록일": reg_date.isoformat(),
                            "총등록": str(int(add_cnt)),
                            "남은횟수": str(int(add_cnt)),
                            "회원유형": "일반",
                            "메모": note,
                            "재등록횟수": "0",
                            "최근재등록일": ""
                        }])
                        members = pd.concat([members, row], ignore_index=True)
                        save_members(members)
                        st.success(f"신규 등록 완료: {name} (등록 {int(add_cnt)}회)")
                    else:
                        # 기존: 기본 정보만 수정 (횟수 반영은 아래 '재등록' 버튼에서)
                        idx = members.index[members["이름"] == sel][0]
                        members.loc[idx, ["이름", "연락처", "기본지점", "등록일", "메모"]] = \
                            [name.strip(), phone.strip(), site, reg_date.isoformat(), note]
                        save_members(members)
                        st.success("수정 완료")

        # 재등록(+횟수 반영)
        with c2:
            if st.button("재등록(+횟수 반영)", use_container_width=True, disabled=is_new):
                if is_new:
                    st.error("기존 회원을 먼저 선택하세요.")
                else:
                    idx = members.index[members["이름"] == sel][0]
                    members.loc[idx, "총등록"] = str(int(float(members.loc[idx, "총등록"] or 0)) + int(add_cnt))
                    members.loc[idx, "남은횟수"] = str(int(float(members.loc[idx, "남은횟수"] or 0)) + int(add_cnt))
                    # 재등록 카운트/최근일 갱신(없으면 생성)
                    if "재등록횟수" not in members.columns:
                        members["재등록횟수"] = "0"
                    if "최근재등록일" not in members.columns:
                        members["최근재등록일"] = ""
                    members.loc[idx, "재등록횟수"] = str(int(float(members.loc[idx, "재등록횟수"] or 0)) + 1)
                    members.loc[idx, "최근재등록일"] = date.today().isoformat()
                    save_members(members)
                    st.success(f"{sel} 재등록 +{int(add_cnt)}회 반영")

        # 삭제
        with c3:
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [])
            if st.button("멤버 삭제", use_container_width=True, disabled=members.empty):
                members = members[members["이름"] != del_name].reset_index(drop=True)
                save_members(members)
                st.success(f"{del_name} 삭제 완료")

    # ---------------- 현재 멤버 보기 ----------------
    with st.expander("📋 현재 멤버 보기", expanded=False):
        if members.empty:
            big_info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            # 누락 컬럼 보완
            for col in ["최근재등록일", "재등록횟수", "총등록", "남은횟수", "등록일", "기본지점", "연락처", "메모"]:
                if col not in show.columns:
                    show[col] = ""
            for c in ["등록일", "최근재등록일"]:
                show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
            st.dataframe(
                show[["이름", "연락처", "기본지점", "등록일", "총등록", "남은횟수", "재등록횟수", "최근재등록일", "메모"]],
                use_container_width=True,
                hide_index=True
            )

    # ---------- 데이터 백업/복구 ----------
    with st.expander("💾 데이터 백업/복구", expanded=False):
        st.caption("CSV는 앱 재배포 시 초기화될 수 있어요. 주기적으로 백업하세요!")

        colb = st.columns(2)
        with colb[0]:
            st.download_button(
                "📥 members.csv 내보내기",
                data=load_members().to_csv(index=False, encoding="utf-8-sig"),
                file_name="members.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.download_button(
                "📥 sessions.csv 내보내기",
                data=load_sessions().assign(날짜=lambda d: pd.to_datetime(d["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                                if not load_sessions().empty else d["날짜"]).to_csv(index=False, encoding="utf-8-sig"),
                file_name="sessions.csv",
                mime="text/csv",
                use_container_width=True
            )

        with colb[1]:
            up_m = st.file_uploader("members.csv 불러오기", type=["csv"])
            up_s = st.file_uploader("sessions.csv 불러오기", type=["csv"])
            if st.button("📤 업로드 적용", use_container_width=True):
                try:
                    if up_m is not None:
                        dfm = pd.read_csv(up_m, dtype=str, encoding="utf-8-sig").fillna("")
                        save_members(dfm)
                    if up_s is not None:
                        dfs = pd.read_csv(up_s, dtype=str, encoding="utf-8-sig").fillna("")
                        # 날짜 고정
                        if not dfs.empty and "날짜" in dfs.columns:
                            dfs["날짜"] = pd.to_datetime(dfs["날짜"])
                        save_sessions(dfs)
                    st.success("백업/복구 적용 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"업로드 처리 중 오류: {e}")


# ─────────────────────────────────────────────────────────────────────
# 페이지: 리포트 (회원 동작만)
# ─────────────────────────────────────────────────────────────────────
elif st.session_state.page == "report":
    st.header("📋 리포트 (회원 동작)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        sel_member = st.selectbox("멤버 선택", sorted([n for n in sessions["이름"].unique() if str(n).strip()]))
        base_month = st.date_input("기준 월", value=date.today()).replace(day=1)
        month_str = base_month.strftime("%Y-%m")

        df = sessions.copy()
        df = df[(df["구분"]=="개인") & (df["이름"]==sel_member)]
        if df.empty:
            big_info("데이터가 없습니다.")
        else:
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            cur = df[df["YM"]==month_str]
            # 동작 토큰화
            tokens = []
            for _, r in cur.iterrows():
                parts = []
                if str(r["동작(리스트)"]).strip():
                    parts += [p.strip() for p in str(r["동작(리스트)"]).split(";") if p.strip()]
                if str(r["추가동작"]).strip():
                    parts += [p.strip() for p in str(r["추가동작"]).split(",") if p.strip()]
                tokens += parts
            if not tokens:
                big_info("이번 달 저장된 동작이 없습니다.")
            else:
                top = pd.Series(tokens).value_counts().head(5).reset_index()
                top.columns = ["동작","횟수"]
                st.subheader(f"{sel_member} · {month_str} Top5")
                st.bar_chart(top.set_index("동작"))

            # 최근 6개월 추이(Top 동작들만)
            last6 = pd.date_range(base_month - pd.DateOffset(months=5), periods=6, freq="MS").strftime("%Y-%m").tolist()
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            df6 = df[df["YM"].isin(last6)].copy()
            # 동작명 나열
            rows = []
            for _, r in df6.iterrows():
                parts = []
                if str(r["동작(리스트)"]).strip():
                    parts += [p.strip() for p in str(r["동작(리스트)"]).split(";") if p.strip()]
                if str(r["추가동작"]).strip():
                    parts += [p.strip() for p in str(r["추가동작"]).split(",") if p.strip()]
                for p in parts:
                    rows.append({"YM": r["YM"], "동작": p})
            trend = pd.DataFrame(rows)
            if not trend.empty:
                trend = trend.groupby(["YM","동작"]).size().reset_index(name="cnt")
                trend = trend.pivot(index="YM", columns="동작", values="cnt").fillna(0).reindex(last6).fillna(0)
                st.subheader("최근 6개월 추이")
                st.line_chart(trend)
            else:
                big_info("최근 6개월 동작 기록이 없습니다.")


# ─────────────────────────────────────────────────────────────────────
# 페이지: 🍒 (수입, 설정 포함)
# ─────────────────────────────────────────────────────────────────────
elif st.session_state.page == "cherry":
    st.header("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****")
        if st.button("열기"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        # 설정: 방문 실수령(원) – 멤버가 방문(V)+개인일 때 자동 반영
        st.subheader("설정")
        cfg = load_cherry_cfg()
        new_visit = st.number_input("방문 실수령(원)", 0, 2_000_000, int(cfg.get("visit_pay",0)), 1000)
        if st.button("저장", use_container_width=True):
            cfg["visit_pay"] = int(new_visit)
            save_cherry_cfg(cfg)
            st.success("저장 완료!")

        # 수입 리포트
        st.subheader("수입")
        if sessions.empty:
            big_info("세션 데이터가 없습니다.")
        else:
            df = sessions.copy()
            df["Y"] = pd.to_datetime(df["날짜"]).dt.year
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            month_sum = df.groupby("YM")["페이(실수령)"].sum().astype(int).reset_index()
            year_sum  = df.groupby("Y")["페이(실수령)"].sum().astype(int).reset_index()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**월별 합계**")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("**연도 합계**")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.markdown("**상세(개별 세션)**")
            v = df.sort_values("날짜", ascending=False)
            v["날짜"] = pd.to_datetime(v["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(v, use_container_width=True, hide_index=True)








