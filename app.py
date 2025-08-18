# app.py
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple

import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────
# 기본 설정
# ──────────────────────────────────────────────────────────
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
EX_JSON      = DATA_DIR / "exercise_db.json"

# 🍒 PIN (Secrets 우선)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES = ["플로우", "리유", "방문"]
SITE_COLOR = {"플로우": "#d9f0ff", "리유": "#f0f0f0", "방문": "#e9fbe9"}

# 장비별 동작 DB(요약). 사용 중 추가하면 EX_JSON에 누적 저장됨
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat": [
        "Roll down","The hundred","Roll up","Single leg circles",
        "Rolling like a ball","Single leg stretch","Double leg stretch",
        "Spine stretch forward","Criss cross","Saw","Neck pull","Teaser"
    ],
    "Reformer": [
        "Footwork series","The hundred","Coordination","Pulling straps",
        "Backstroke","Short box series","Long stretch series","Elephant",
        "Knee stretch series","Running","Pelvic lift","Side split","Front split"
    ],
    "Cadillac": [
        "Roll back","Leg spring series","Tower","Monkey",
        "Teaser w/push through bar","Arm series","Push through bar",
        "Shoulder bridge","Hip circles"
    ],
    "Wunda chair": [
        "Footwork series","Push down","Pull up","Spine stretch forward",
        "Mountain climb","Tabletop","Front balance control"
    ],
    "Barrel/Spine": [
        "Swan","Horseback","Side sit up","Ballet stretch side","Thigh stretch"
    ],
    "기타": []
}

# ──────────────────────────────────────────────────────────
# 파일 준비
# ──────────────────────────────────────────────────────────
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","지점","등록일",
            "총등록","남은횟수","방문실수령","메모",
            "재등록횟수","최근재등록일"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제",
            "메모","취소","사유","분","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

ensure_files()

# ──────────────────────────────────────────────────────────
# 로드/저장
# ──────────────────────────────────────────────────────────
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
        if "취소" in df.columns:
            df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    df = df.copy()
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
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

# ──────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────
def calc_pay(site: str, session_type: str, headcount: int, member_visit_pay: float|None) -> Tuple[float, float]:
    """(gross, net)"""
    if site == "플로우":
        gross = 35000.0
        net = round(gross * 0.967, 0)  # 3.3% 공제
    elif site == "리유":
        if session_type == "개인":
            gross = net = 30000.0
        else:
            if headcount == 2:
                gross = net = 35000.0
            else:
                gross = net = {3: 40000.0, 2: 30000.0, 1: 25000.0}.get(headcount, 30000.0)
    else:  # 방문
        gross = net = float(member_visit_pay or 0)
    return float(gross), float(net)

def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def moves_for_equip(ex_db: Dict[str, List[str]], equip: str) -> List[str]:
    key = equip
    if equip in ["Large barrel","Spine corrector","Barrel","Spine"]:
        key = "Barrel/Spine"
    return sorted(list(ex_db.get(key, [])))

# ──────────────────────────────────────────────────────────
# 이모지 네비(옛값 호환)
# ──────────────────────────────────────────────────────────
EMOJI_TABS = ["📋","👥","📅","🍒"]  # 세션, 멤버, 스케줄, 수입
OLD_TO_NEW = {"📝 세션":"📋","🧑‍🤝‍🧑 멤버":"👥","📅 스케줄":"📅","🍒 수입":"🍒"}
cur = st.session_state.get("nav", "📋")
cur = OLD_TO_NEW.get(cur, cur)
if cur not in EMOJI_TABS:
    cur = "📋"
st.session_state["nav"] = cur

nav = st.sidebar.radio(" ", EMOJI_TABS, index=EMOJI_TABS.index(st.session_state["nav"]), horizontal=True)
st.session_state["nav"] = nav

# ──────────────────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────────────────
members = load_members()
sessions = load_sessions()
ex_db = load_ex_db()

# ──────────────────────────────────────────────────────────
# 👥 멤버
# ──────────────────────────────────────────────────────────
if nav == "👥":
    st.header("멤버 관리")

    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])
        with left:
            existing = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", existing)
            name = st.text_input("이름", "" if sel=="(새 회원)" else sel, placeholder="예: 김지현")
            phone_default = ""
            if sel != "(새 회원)" and sel in members["이름"].values:
                phone_default = members.loc[members["이름"]==sel, "연락처"].iloc[0]
            phone = st.text_input("연락처", value=phone_default, placeholder="010-0000-0000")
            # 중복 확인
            dup = (members["연락처"] == phone) & (members["이름"] != name)
            if phone and dup.any():
                st.warning("⚠️ 동일한 연락처가 이미 등록되어 있어요.")

        with right:
            site_default = "플로우"
            if sel != "(새 회원)" and sel in members["이름"].values:
                site_default = members.loc[members["이름"]==sel, "지점"].iloc[0] or "플로우"
            site = st.selectbox("기본 지점", SITES, index=SITES.index(site_default))

            reg_default = date.today()
            if sel != "(새 회원)" and sel in members["이름"].values:
                try:
                    reg_default = pd.to_datetime(members.loc[members["이름"]==sel, "등록일"].iloc[0]).date()
                except Exception:
                    pass
            reg_date = st.date_input("등록일", reg_default)

            visit_pay_default = ""
            if sel != "(새 회원)" and sel in members["이름"].values:
                visit_pay_default = members.loc[members["이름"]==sel, "방문실수령"].iloc[0]
            visit_pay = st.text_input("방문 실수령(원)", value=visit_pay_default, placeholder="예: 50000")

        note = st.text_input("메모(선택)", value="" if sel=="(새 회원)" else members.loc[members["이름"]==sel,"메모"].iloc[0] if (sel in members["이름"].values) else "")
        add_cnt = st.number_input("재등록 추가 횟수(+)", 0, 100, 0, 1)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                elif phone and dup.any():
                    st.error("동일 연락처가 이미 존재합니다.")
                else:
                    if sel == "(새 회원)":
                        new_id = str(len(members) + 1)
                        row = pd.DataFrame([{
                            "id": new_id, "이름": name.strip(), "연락처": phone.strip(),
                            "지점": site, "등록일": reg_date.isoformat(),
                            "총등록": "0", "남은횟수": "0", "방문실수령": visit_pay.strip(),
                            "메모": note, "재등록횟수":"0", "최근재등록일":""
                        }])
                        members = pd.concat([members, row], ignore_index=True)
                    else:
                        idx = members.index[members["이름"]==sel][0]
                        members.loc[idx, ["이름","연락처","지점","등록일","방문실수령","메모"]] = \
                            [name.strip(), phone.strip(), site, reg_date.isoformat(), visit_pay.strip(), note]
                    save_members(members)
                    st.success("저장 완료")

        with c2:
            if st.button("재등록 반영(+)", use_container_width=True, disabled=(sel=="(새 회원)")):
                if sel!="(새 회원)":
                    idx = members.index[members["이름"]==sel][0]
                    total = int(float(members.loc[idx,"총등록"] or 0)) + int(add_cnt)
                    remain= int(float(members.loc[idx,"남은횟수"] or 0)) + int(add_cnt)
                    rereg = int(float(members.loc[idx,"재등록횟수"] or 0)) + int(add_cnt)
                    today = date.today().isoformat()
                    members.loc[idx, ["총등록","남은횟수","재등록횟수","최근재등록일"]] = [str(total), str(remain), str(rereg), today]
                    save_members(members)
                    st.success(f"{sel} 재등록 +{add_cnt}회")

        with c3:
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [])
            if st.button("멤버 삭제", use_container_width=True, disabled=members.empty):
                members = members[members["이름"]!=del_name].reset_index(drop=True)
                save_members(members)
                st.success(f"{del_name} 삭제 완료")

    # 목록 + 리포트
    tabs = st.tabs(["📋 목록", "📈 월간 Top5 동작"])
    with tabs[0]:
        if members.empty:
            st.info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            st.dataframe(show, use_container_width=True, hide_index=True)
    with tabs[1]:
        if sessions.empty or members.empty:
            st.info("데이터가 부족합니다.")
        else:
            msel = st.selectbox("멤버", members["이름"].tolist())
            ym = st.date_input("월 선택", value=date.today().replace(day=1))
            start = datetime(ym.year, ym.month, 1)
            end = (start + pd.offsets.MonthEnd(1)).to_pydatetime()
            df = sessions[
                (sessions["구분"]=="개인") &
                (sessions["이름"]==msel) &
                (sessions["날짜"]>=start) & (sessions["날짜"]<=end)
            ].copy()
            if df.empty:
                st.info("해당 월 데이터 없음")
            else:
                # 동작 문자열을 펼쳐 집계
                items = []
                for s in (df["동작(리스트)"].fillna("").tolist() + df["추가동작"].fillna("").tolist()):
                    for p in [x.strip() for x in str(s).split(";") if x.strip()]:
                        items.append(p)
                if not items:
                    st.info("기록된 동작이 없습니다.")
                else:
                    top = pd.Series(items).value_counts().head(5)
                    st.subheader("월간 Top5")
                    st.bar_chart(top)

                    st.subheader("최근 6개월 추이(Top5 동작들)")
                    last6_start = start - pd.DateOffset(months=5)
                    df6 = sessions[(sessions["구분"]=="개인") & (sessions["이름"]==msel) &
                                   (sessions["날짜"]>=last6_start) & (sessions["날짜"]<=end)].copy()
                    if df6.empty:
                        st.info("최근 6개월 데이터 없음")
                    else:
                        recs = []
                        for _, r in df6.iterrows():
                            moves = []
                            if r["동작(리스트)"]: moves += [x.strip() for x in str(r["동작(리스트)"]).split(";") if x.strip()]
                            if r["추가동작"]:    moves += [x.strip() for x in str(r["추가동작"]).split(",") if x.strip()]
                            for mv in moves:
                                if mv in top.index:
                                    recs.append({"YM": r["날짜"].strftime("%Y-%m"), "동작": mv, "cnt": 1})
                        if recs:
                            tmp = pd.DataFrame(recs).groupby(["YM","동작"])["cnt"].sum().unstack(fill_value=0)
                            st.line_chart(tmp)
                        else:
                            st.info("추이 데이터 없음")

# ──────────────────────────────────────────────────────────
# 📋 세션
# ──────────────────────────────────────────────────────────
elif nav == "📋":
    st.header("세션 기록")

    if members.empty:
        st.info("먼저 멤버를 등록하세요.")
    cols = st.columns([1,1,1,1])
    with cols[0]:
        day = st.date_input("날짜", value=date.today())
        time_str = st.time_input("시간", value=datetime.now().time())
    with cols[1]:
        session_type = st.radio("구분", ["개인","그룹"], horizontal=True)
    with cols[2]:
        if session_type == "개인":
            mname = st.selectbox("멤버", members["이름"].tolist())
            auto_site = members.loc[members["이름"]==mname, "지점"].iloc[0] if mname in members["이름"].values else "플로우"
            site = st.selectbox("지점", SITES, index=SITES.index(auto_site))
        else:
            mname = ""
            site = st.selectbox("지점", SITES)
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
        pass  # 방문 실수령은 멤버 정보로 관리

    # 동작(개인일 때만 노출) + 특이사항/숙제
    chosen, add_free = [], ""
    if session_type == "개인":
        opts = [f"{equip} · {m}" for m in moves_for_equip(ex_db, equip)]
        chosen = st.multiselect("운동 동작(복수 선택)", options=opts)
        add_free = st.text_input("추가 동작(콤마 , 로 구분)", placeholder="예: Side bends, Mermaid")
        homework = st.text_input("숙제(선택)", placeholder="예: Wall roll down 10회")
    else:
        homework = ""  # 그룹에서는 입력 제거

    special = st.text_area("특이사항(선택)", height=70)
    cancel = st.checkbox("취소")
    reason = st.text_input("사유(선택)", placeholder="예: 회원 사정/강사 사정 등")

    if st.button("세션 저장", use_container_width=True):
        when = datetime.combine(day, time_str)

        # EX_DB 사용자 추가 반영
        if session_type=="개인" and add_free.strip():
            new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
            exdb = load_ex_db()
            exdb.setdefault("기타", [])
            for nm in new_moves:
                if nm not in exdb["기타"]:
                    exdb["기타"].append(nm)
            save_ex_db(exdb)

        # 방문 실수령(개인+방문) 은 멤버 카드에서 가져옴
        member_visit = None
        if session_type=="개인" and site=="방문":
            try:
                member_visit = float(members.loc[members["이름"]==mname,"방문실수령"].iloc[0] or 0)
            except Exception:
                member_visit = 0.0

        gross, net = calc_pay(site, session_type, int(headcount), member_visit)

        row = pd.DataFrame([{
            "id": str(len(sessions)+1),
            "날짜": when, "지점": site, "구분": session_type,
            "이름": mname if session_type=="개인" else "",
            "인원": int(headcount) if session_type=="그룹" else 1,
            "레벨": level, "기구": equip,
            "동작(리스트)": "; ".join(chosen) if session_type=="개인" else "",
            "추가동작": add_free if session_type=="개인" else "",
            "특이사항": special, "숙제": homework,
            "메모": "", "취소": bool(cancel), "사유": reason,
            "분": int(minutes), "페이(총)": float(gross), "페이(실수령)": float(net)
        }])
        sessions = pd.concat([sessions, row], ignore_index=True)
        save_sessions(sessions)

        # 개인 세션이면 남은횟수 차감(취소 아닌 경우)
        if session_type=="개인" and mname and not cancel and (mname in members["이름"].values):
            idx = members.index[members["이름"]==mname][0]
            remain = max(0, int(float(members.loc[idx,"남은횟수"] or 0)) - 1)
            members.loc[idx,"남은횟수"] = str(remain)
            save_members(members)

        st.success("세션 저장 완료!")

    st.subheader("최근 세션")
    if sessions.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        view = sessions.sort_values("날짜", ascending=False).copy()
        hide_cols = []  # 수입은 🍒에서만 보지만 여기선 보여도 무방하면 그대로, 숨기려면 ["페이(총)","페이(실수령)"]
        show_cols = [c for c in view.columns if c not in hide_cols]
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ──────────────────────────────────────────────────────────
# 📅 스케줄 (일/주/월) + 지난 수업 상세
# ──────────────────────────────────────────────────────────
elif nav == "📅":
    st.header("스케줄 (일/주/월)")
    if sessions.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        mode = st.segmented_control("보기", options=["일","주","월"], default="주")
        base = st.date_input("기준 날짜", value=date.today())
        base_dt = datetime.combine(base, datetime.min.time())

        if mode=="일":
            start = base_dt; end = base_dt + timedelta(days=1)
        elif mode=="주":
            start = base_dt - timedelta(days=base_dt.weekday()); end = start + timedelta(days=7)
        else:
            start = base_dt.replace(day=1)
            end = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

        view = sessions[(sessions["날짜"]>=start) & (sessions["날짜"]<end)].copy().sort_values("날짜")
        if view.empty:
            st.info("해당 기간 일정 없음")
        else:
            view["날짜표시"] = pd.to_datetime(view["날짜"]).dt.strftime("%m/%d %a %H:%M")
            for _, r in view.iterrows():
                name_html = f"<span style='font-size:16px; font-weight:800;'>{r['이름'] if r['이름'] else '그룹'}</span>"
                site_chip = tag(r["지점"], SITE_COLOR.get(r["지점"], "#eee"))
                title = f'{r["날짜표시"]} · {site_chip} · {name_html}'
                body = f'{r["구분"]} · {r["레벨"]} · {r["기구"]}'
                details = []
                if r["동작(리스트)"]: details.append(f'동작: {r["동작(리스트)"]}')
                if r["추가동작"]:    details.append(f'추가: {r["추가동작"]}')
                if r["숙제"]:        details.append(f'숙제: {r["숙제"]}')
                if r["특이사항"]:    details.append(f'특이: {r["특이사항"]}')
                if details: body += " · " + " · ".join(details)
                if bool(r["취소"]): title = f'<s>{title}</s>'

                st.markdown(
                    f"<div style='padding:10px;border-bottom:1px solid #333'>{title}<br>"
                    f"<span style='color:#bbb'>{body}</span></div>",
                    unsafe_allow_html=True
                )

# ──────────────────────────────────────────────────────────
# 🍒 수입 (PIN)
# ──────────────────────────────────────────────────────────
elif nav == "🍒":
    st.header("🍒")  # 텍스트 없이 이모지만
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN", type="password", placeholder="****")
        if st.button("열기"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        if sessions.empty:
            st.info("세션 데이터가 없습니다.")
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
            view = df.sort_values("날짜", ascending=False)
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view, use_container_width=True, hide_index=True)



