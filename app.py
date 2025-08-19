# app.py
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

# =========================
# 기본 설정
# =========================
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV   = DATA_DIR / "members.csv"
SESSIONS_CSV  = DATA_DIR / "sessions.csv"
EXER_DB_JSON  = DATA_DIR / "exercise_db.json"

# 🍒 PIN (Streamlit Cloud의 Secrets에 CHERRY_PW가 있으면 그 값을 우선 사용)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

# 내부 저장 값(한글)은 그대로 유지, 화면 표시는 F/R/V 로
SITES = ["플로우", "리유", "방문"]
SITE_COLOR = {"플로우": "#d9f0ff", "리유": "#eeeeee", "방문": "#e9fbe9"}  # 칩 배경색
SITE_MAP = {"플로우": "F", "리유": "R", "방문": "V"}  # 저장값 -> 표시라벨
REV_SITE_MAP = {v: k for k, v in SITE_MAP.items()}   # 표시라벨 -> 저장값
SITE_LABELS = ["F", "R", "V"]  # selectbox 표시 순서

def site_to_label(site: str) -> str:
    return SITE_MAP.get(site, site)

def label_to_site(label: str) -> str:
    return REV_SITE_MAP.get(label, label)

# 레벨/기구/동작 초기 DB (없으면 자동 생성/저장, 이후 사용자가 추가한 동작은 누적)
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat(Basic)": [
        "Roll down","The hundred","Roll up","Single leg circles",
        "Rolling like a ball","Single leg stretch","Double leg stretch",
        "Spine stretch forward"
    ],
    "Mat(Intermediate/Advanced)":[
        "Criss cross","Open leg rocker","Saw","Neck pull","Side kick series",
        "Teaser","Swimming","Scissors","Bicycle","Jack knife","Seal"
    ],
    "Reformer": [
        "Footwork series","Toes","Arches","Heels","Tendon stretch","The hundred",
        "Leg circles","Short box series","Elephant","Knee stretch series","Running",
        "Pelvic lift","Long box - pulling straps","Backstroke","Long stretch series",
        "Side split","Front split","Coordination"
    ],
    "Cadillac": [
        "Roll back","Leg spring series","Tower","Monkey","Teaser (push-through)",
        "Arm series","Push-through bar","Breathing"
    ],
    "Wunda chair": [
        "Footwork series","Push down","Pull up","Spine stretch forward","Teaser",
        "Mountain climb","Tabletop","Front balance control"
    ],
    "Spine corrector/Barrel":[
        "Swan","Horseback","Side sit up","Ballet stretch side","Thigh stretch"
    ],
    "Electric chair": ["Pumping series","Going up front","Press up bottom","Press up front"],
    "Pedi-pull": ["Chest expansion","Arm circles","Knee bends","Centering"],
    "기타": []
}

# =========================
# 파일 유틸
# =========================
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","지점","등록일",
            "총등록","남은횟수","메모",
            "방문 실수령(원)","최근 재등록일","재등록 누적"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제","메모",
            "취소","사유","분","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    if not EXER_DB_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EXER_DB_JSON, force_ascii=False)

ensure_files()

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
    return df

def save_sessions(df: pd.DataFrame):
    df = df.copy()
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

def load_ex_db() -> Dict[str, List[str]]:
    try:
        ser = pd.read_json(EXER_DB_JSON, typ="series")
        d = {k: list(v) for k, v in ser.items()}
        for k, v in EX_DB_DEFAULT.items():
            d.setdefault(k, v)
        return d
    except Exception:
        pd.Series(EX_DB_DEFAULT).to_json(EXER_DB_JSON, force_ascii=False)
        return EX_DB_DEFAULT

def save_ex_db(db: Dict[str, List[str]]):
    pd.Series(db).to_json(EXER_DB_JSON, force_ascii=False)

# =========================
# 공통
# =========================
def big_info(msg: str, kind="info"):
    if kind == "warn": st.warning(msg)
    elif kind == "error": st.error(msg)
    else: st.info(msg)

def tag(text, bg):
    return f"<span style='background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;'>{text}</span>"

def calc_pay(site: str, session_type: str, headcount: int, visit_net: float|None) -> Tuple[float,float]:
    """
    returns (gross, net)
    플로우: 회당 35,000원, 3.3% 공제
    리유: 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣 35,000 (공제 없음)
    방문: 멤버 기본설정 '방문 실수령(원)' 사용 (gross=net)
    """
    gross = net = 0.0
    if site == "플로우":
        gross = 35000.0
        net = round(gross * 0.967, 0)
    elif site == "리유":
        if session_type == "개인":
            gross = net = 30000.0
        else:
            if headcount == 2:
                gross = net = 35000.0
            else:
                mapping = {3:40000.0, 2:30000.0, 1:25000.0}
                gross = net = mapping.get(headcount, 30000.0)
    else:  # 방문
        gross = net = float(visit_net or 0)
    return gross, net

# =========================
# 네비게이션 (세로 사이드바 / 첫 페이지 = 스케줄)
# =========================
if "nav" not in st.session_state:
    st.session_state["nav"] = "📅 스케줄"

nav_options = ["📅 스케줄","📝 세션","👥 멤버","📋 리포트","🍒"]  # 🍒만 이모지
nav = st.sidebar.radio(" ", options=nav_options,
                       index=nav_options.index(st.session_state["nav"]),
                       horizontal=False, key="nav_radio")
st.session_state["nav"] = nav
st.sidebar.markdown("&nbsp;", unsafe_allow_html=True)

# 데이터 로드
members = load_members()
sessions = load_sessions()
ex_db = load_ex_db()

# =========================================================
# 👥 멤버
# =========================================================
if nav.startswith("👥"):
    st.header("멤버 관리")

    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])

        existing = ["(새 회원)"] + (members["이름"].tolist() if not members.empty else [])
        sel = st.selectbox("회원 선택", existing, key="mem_select")

        sel_row = members[members["이름"]==sel].iloc[0] if (sel != "(새 회원)" and not members.empty and sel in members["이름"].values) else None

        with left:
            name  = st.text_input("이름", "" if sel == "(새 회원)" else sel, key="mem_name")
            phone = st.text_input(
                "연락처",
                "" if sel_row is None else sel_row.get("연락처",""),
                placeholder="010-0000-0000",
                key="mem_phone"
            )
            # 전화번호 중복 체크
            duplicated = False
            if phone.strip():
                dup = members[(members["연락처"]==phone) & (members["이름"]!=name)]
                if not dup.empty:
                    st.error("⚠️ 이미 등록된 연락처입니다. 확인해주세요.")
                    duplicated = True

            # 기본 지점(F/R/V 표시)
            site_default = "플로우" if sel_row is None else (sel_row.get("지점") or "플로우")
            site_label_default = site_to_label(site_default)
            site_label = st.selectbox("기본 지점", options=SITE_LABELS,
                                      index=SITE_LABELS.index(site_label_default),
                                      key="mem_site_label")
            site = label_to_site(site_label)  # 저장은 한글

            visit_net_default = 0 if sel_row is None else int(float(sel_row.get("방문 실수령(원)") or 0))
            visit_net = st.number_input("방문 실수령(원)", 0, 1_000_000, visit_net_default, 1000, key="mem_visitnet")

        with right:
            reg_default = date.today() if sel_row is None else (
                pd.to_datetime(sel_row.get("등록일"), errors="coerce").date() if sel_row.get("등록일") else date.today()
            )
            reg_date = st.date_input("등록일", reg_default, key="mem_regdate")

            add_cnt = st.number_input("재등록 추가 횟수(+)", 0, 100, 0, 1, key="mem_addcnt")
            note = st.text_input("메모(선택)", "" if sel_row is None else sel_row.get("메모",""), key="mem_note")

        c1, c2, c3 = st.columns(3)
        with c1:
            disabled = duplicated or not name.strip()
            if st.button("저장/수정", use_container_width=True, key="mem_save", disabled=disabled):
                if sel == "(새 회원)":
                    new_id = str(len(members)+1)
                    row = pd.DataFrame([{
                        "id":new_id,"이름":name.strip(),"연락처":phone.strip(),
                        "지점":site,"등록일":reg_date.isoformat(),
                        "총등록":"0","남은횟수":"0","메모":note,
                        "방문 실수령(원)": str(visit_net),
                        "최근 재등록일":"", "재등록 누적":"0"
                    }])
                    members_new = pd.concat([members, row], ignore_index=True)
                    save_members(members_new)
                    st.success(f"신규 등록: {name}")
                else:
                    idx = members.index[members["이름"]==sel][0]
                    members.loc[idx,"이름"] = name.strip()
                    members.loc[idx,"연락처"] = phone.strip()
                    members.loc[idx,"지점"] = site
                    members.loc[idx,"등록일"] = reg_date.isoformat()
                    members.loc[idx,"메모"] = note
                    members.loc[idx,"방문 실수령(원)"] = str(visit_net)
                    save_members(members)
                    st.success("수정 완료")

        with c2:
            if st.button("재등록 반영(+남은횟수, 총등록)", use_container_width=True, key="mem_reenroll", disabled=(sel=="(새 회원)" or add_cnt<=0)):
                idx = members.index[members["이름"]==sel][0]
                total = int(float(members.loc[idx,"총등록"] or 0)) + int(add_cnt)
                remain = int(float(members.loc[idx,"남은횟수"] or 0)) + int(add_cnt)
                members.loc[idx,"총등록"] = str(total)
                members.loc[idx,"남은횟수"] = str(remain)
                members.loc[idx,"최근 재등록일"] = date.today().isoformat()
                members.loc[idx,"재등록 누적"] = str(int(float(members.loc[idx,"재등록 누적"] or 0)) + int(add_cnt))
                save_members(members)
                st.success(f"{sel} 재등록 +{add_cnt}회 반영")

        with c3:
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [], key="mem_del_sel")
            if st.button("멤버 삭제", use_container_width=True, key="mem_delete", disabled=members.empty):
                members2 = members[members["이름"]!=del_name].reset_index(drop=True)
                save_members(members2)
                st.success(f"{del_name} 삭제 완료")

    with st.expander("📋 멤버 목록 (등록일/재등록 정보 포함)", expanded=False):
        if members.empty:
            big_info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            show["표시지점"] = show["지점"].apply(site_to_label)
            show["등록일"] = pd.to_datetime(show["등록일"], errors="coerce").dt.date.astype(str)
            st.dataframe(show.drop(columns=["지점"]), use_container_width=True, hide_index=True)

    st.subheader("📈 월간 Top5 동작 & 6개월 추이")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        mnames = ["(선택)"] + sorted([x for x in sessions["이름"].dropna().unique() if x])
        selm = st.selectbox("멤버 선택", mnames, key="stats_member")
        if selm != "(선택)":
            now = date.today()
            month_mask = (
                (sessions["이름"]==selm) & (sessions["구분"]=="개인") &
                (sessions["날짜"].dt.year==now.year) & (sessions["날짜"].dt.month==now.month)
            )
            dfm = sessions.loc[month_mask].copy()
            if dfm.empty:
                big_info("이번 달 기록이 없습니다.")
            else:
                acts = []
                for s in dfm["동작(리스트)"].fillna(""):
                    items = [x.strip() for x in s.split(";") if x.strip()]
                    acts.extend(items)
                if acts:
                    top = pd.Series(acts).value_counts().head(5).reset_index()
                    top.columns = ["동작","횟수"]
                    st.write("**이번 달 Top5 동작**")
                    st.bar_chart(top.set_index("동작"))

                    # 6개월 추이(Top5 기준)
                    target_moves = top["동작"].tolist()
                    since = pd.Timestamp(now) - pd.DateOffset(months=5)
                    dfl = sessions[(sessions["이름"]==selm) & (sessions["구분"]=="개인") & (sessions["날짜"]>=since)].copy()
                    rows = []
                    for _, r in dfl.iterrows():
                        mm = [x.strip() for x in str(r["동작(리스트)"]).split(";") if x.strip()]
                        for m in mm:
                            if m in target_moves:
                                rows.append({"YM": r["날짜"].strftime("%Y-%m"), "동작": m})
                    if rows:
                        agg = pd.DataFrame(rows).value_counts(["YM","동작"]).rename("횟수").reset_index()
                        pivot = agg.pivot(index="YM", columns="동작", values="횟수").fillna(0).sort_index()
                        st.write("**최근 6개월 추이**")
                        st.line_chart(pivot)
                else:
                    big_info("이번 달에 기록된 동작 항목이 없습니다.")

# =========================================================
# 📝 세션 (개인/그룹)
# =========================================================
elif nav.startswith("📝"):
    st.header("세션 기록")

    if members.empty:
        big_info("먼저 멤버를 등록하세요.")
    else:
        # 공통 상단
        c0, c1, c2, c3 = st.columns([1,1,1,1])
        with c0:
            day = st.date_input("날짜", value=date.today(), key="ses_day")
            time_str = st.time_input("시간", value=datetime.now().time(), key="ses_time")
        with c1:
            session_type = st.radio("구분", ["개인","그룹"], horizontal=True, key="ses_type")
        with c2:
            site_label_sel = st.selectbox("지점(F/R/V)", SITE_LABELS, key="ses_site_label")
            site = label_to_site(site_label_sel)  # 저장은 한글
        with c3:
            minutes = st.number_input("수업 분", 10, 180, 50, 5, key="ses_minutes")

        # 공통 레벨/기구
        cc1, cc2 = st.columns([1,1])
        with cc1:
            level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"], key="ses_level")
        with cc2:
            equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Spine corrector/Barrel","Mat","기타"], key="ses_equip")

        # 개인 / 그룹 분기
        mname = ""
        headcount = 1
        if session_type == "개인":
            # 멤버 선택 및 지점 자동 제안(F/R/V)
            mname = st.selectbox("멤버", members["이름"].tolist(), key="ses_member")
            if mname:
                try:
                    auto_site = members.loc[members["이름"]==mname,"지점"].iloc[0] or "플로우"
                    auto_label = site_to_label(auto_site)
                    site_label_sel = st.selectbox("지점(자동 추천, F/R/V)", SITE_LABELS,
                                                  index=SITE_LABELS.index(auto_label), key="ses_site_auto_label")
                    site = label_to_site(site_label_sel)
                except Exception:
                    pass
        else:  # 그룹
            headcount = st.number_input("인원(그룹)", 1, 10, 2, 1, key="ses_group_headcount")

        # 기구별 동작 필터
        equip_map = {
            "Mat": ["Mat(Basic)", "Mat(Intermediate/Advanced)"],
            "Reformer": ["Reformer"],
            "Cadillac": ["Cadillac"],
            "Wunda chair": ["Wunda chair"],
            "Spine corrector/Barrel": ["Spine corrector/Barrel", "Large barrel", "Small barrel / Spine corrector", "Spine corrector"],
            "기타": ["Electric chair","Pedi-pull","기타"]
        }
        cat_list = equip_map.get("Mat" if equip=="Mat" else equip, [])
        per_moves_list = []
        for cat in cat_list:
            if cat in ex_db:
                per_moves_list.extend(list(ex_db[cat]))
        per_moves_list = sorted({m for m in per_moves_list if isinstance(m, str) and m.strip()})

        # 입력 UI (요청대로: 그룹은 동작/숙제 입력 없음)
        if session_type == "개인":
            chosen = st.multiselect("운동 동작(복수)", options=per_moves_list, key="ses_moves_select")
            add_free = st.text_input("추가 동작(쉼표 , 로 구분)", placeholder="예: Side bends, Mermaid", key="ses_moves_free")
            col_note, col_hw = st.columns([1,1])
            with col_note:
                special_note = st.text_area("특이사항(선택)", height=80, key="ses_special_note")
            with col_hw:
                homework = st.text_area("숙제(선택)", height=80, key="ses_homework")
        else:
            chosen = []
            add_free = ""
            special_note = st.text_area("특이사항(선택)", height=80, key="group_special_note")
            homework = ""

        cancel = st.checkbox("취소", key="ses_cancel")
        reason = st.text_input("사유(선택)", placeholder="예: 회원 사정/강사 사정 등", key="ses_reason")

        if st.button("세션 저장", use_container_width=True, key="ses_save_btn"):
            when = datetime.combine(day, time_str)

            # 자유 입력 동작 '기타'에 누적
            if add_free.strip():
                new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
                updated = load_ex_db()
                updated.setdefault("기타", [])
                for nm in new_moves:
                    if nm not in updated["기타"]:
                        updated["기타"].append(nm)
                save_ex_db(updated)

            # 방문(개인) 실수령은 멤버 프로필에서
            custom_visit = None
            if session_type == "개인" and site == "방문" and mname:
                if "방문 실수령(원)" in members.columns:
                    try:
                        custom_visit = float(members.loc[members["이름"]==mname, "방문 실수령(원)"].iloc[0] or 0)
                    except Exception:
                        custom_visit = None

            gross, net = calc_pay(site, session_type, int(headcount), custom_visit)

            row = {
                "id": str(len(sessions) + 1),
                "날짜": when,
                "지점": site,                         # 저장은 한글
                "구분": session_type,
                "이름": mname if session_type == "개인" else "",
                "인원": int(headcount) if session_type == "그룹" else 1,
                "레벨": level,
                "기구": equip,
                "동작(리스트)": "; ".join(chosen),
                "추가동작": add_free,
                "특이사항": special_note,
                "숙제": homework,
                "메모": "",
                "취소": bool(cancel),
                "사유": reason,
                "분": int(minutes),
                "페이(총)": float(gross),
                "페이(실수령)": float(net),
            }
            # 누락 컬럼 대비
            for col in row.keys():
                if col not in sessions.columns:
                    sessions[col] = ""
            sessions = pd.concat([sessions, pd.DataFrame([row])], ignore_index=True)
            save_sessions(sessions)

            # 개인 정상 진행이면 남은횟수 차감
            if session_type == "개인" and mname and not cancel and (mname in members["이름"].values):
                idx = members.index[members["이름"]==mname][0]
                try:
                    remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
                except Exception:
                    remain = 0
                members.loc[idx,"남은횟수"] = str(remain)
                save_members(members)

            st.success("세션 저장 완료!")

        st.subheader("최근 세션 목록")
        if sessions.empty:
            big_info("세션 데이터가 없습니다.")
        else:
            view = sessions.sort_values("날짜", ascending=False).copy()
            hide_cols = ["페이(총)","페이(실수령)"]
            view["표시지점"] = view["지점"].apply(site_to_label)  # F/R/V로
            view["날짜"] = pd.to_datetime(view["날짜"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
            show_cols = [c for c in view.columns if c not in hide_cols and c != "지점"]
            # 보기 좋은 위치에 표시지점 삽입
            if "표시지점" not in show_cols:
                insert_pos = show_cols.index("구분")+1 if "구분" in show_cols else 1
                show_cols = show_cols[:insert_pos] + ["표시지점"] + show_cols[insert_pos:]
            st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# =========================================================
# 📅 스케줄 (일/주/월) + 지난 수업 상세 + 취소 토글
# =========================================================
elif nav.startswith("📅"):
    st.header("스케줄 (일/주/월)")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        mode = st.segmented_control("보기", options=["일","주","월"], default="주", key="cal_mode")
        base = st.date_input("기준 날짜", value=date.today(), key="cal_base")
        base_dt = datetime.combine(base, datetime.min.time())

        if mode == "일":
            start = base_dt
            end   = base_dt + timedelta(days=1)
        elif mode == "주":
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
            st.caption("과거 세션은 **동작/특이사항/숙제**가 함께 보입니다. (취소 토글 가능)")

            with st.form("cancel_form"):
                rows_html = []
                updates = []

                for _, r in view.iterrows():
                    dt_txt = pd.to_datetime(r["날짜"]).strftime("%m/%d %a %H:%M")
                    who = r["이름"] if r["이름"] else "(그룹)"
                    site_label = site_to_label(r["지점"])
                    site_chip = tag(site_label, SITE_COLOR.get(r["지점"], "#eee"))

                    details = []
                    if pd.to_datetime(r["날짜"]) < datetime.now():
                        if r.get("동작(리스트)"): details.append(f'동작: {r.get("동작(리스트")}')
                        if r.get("추가동작"):     details.append(f'추가: {r.get("추가동작")}')
                        if r.get("특이사항"):     details.append(f'특이: {r.get("특이사항")}')
                        if r.get("숙제"):         details.append(f'숙제: {r.get("숙제")}')

                    title_html = f"{dt_txt} · {site_chip} · <b>{who}</b> · {r['구분']} · {r['레벨']} · {r['기구']}"
                    if bool(r["취소"]): title_html = f"<s>{title_html}</s>"

                    body_html = ""
                    if details:
                        body_html = "<div style='color:#bbb; margin-top:2px;'>" + " · ".join(details) + "</div>"

                    cb_key = f"cancel_{r['id']}"
                    val = st.checkbox(f"취소 ⬅️  ({dt_txt} / {who})", value=bool(r["취소"]), key=cb_key)
                    updates.append((r.name, val))

                    rows_html.append(
                        f"<div style='padding:10px 0; border-bottom:1px solid #333'>{title_html}{body_html}</div>"
                    )

                st.markdown("<div>" + "".join(rows_html) + "</div>", unsafe_allow_html=True)
                if st.form_submit_button("변경 저장", use_container_width=True):
                    for idx, v in updates:
                        sessions.loc[idx,"취소"] = bool(v)
                    save_sessions(sessions)
                    st.success("취소 상태가 반영되었습니다.")

# =========================================================
# 📋 리포트 (간단 보드)
# =========================================================
elif nav.startswith("📋"):
    st.header("📋 리포트")
    if sessions.empty:
        big_info("세션 데이터가 없습니다.")
    else:
        df = sessions.copy()
        df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
        s1 = df.groupby("YM")["id"].count().rename("세션수")
        s2 = df.groupby("YM")["분"].sum().rename("총분")
        board = pd.concat([s1, s2], axis=1).reset_index()
        st.dataframe(board, use_container_width=True, hide_index=True)

# =========================================================
# 🍒 수입 (PIN 잠금, 헤더는 이모지만)
# =========================================================
elif nav == "🍒":
    st.header("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****", key="cherry_pin")
        if st.button("열기", key="cherry_open"):
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
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("월별 합계")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with c2:
                st.subheader("연도 합계")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.subheader("상세(개별 세션)")
            v = df.sort_values("날짜", ascending=False)
            v["표시지점"] = v["지점"].apply(site_to_label)
            v["날짜"] = pd.to_datetime(v["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(v.drop(columns=["지점"]), use_container_width=True, hide_index=True)
