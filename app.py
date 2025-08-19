# app.py  — Pilates Manager (full patched build)
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple

import pandas as pd
import streamlit as st
import altair as alt

# =============================================================================
# 기본 설정
# =============================================================================
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
EX_JSON      = DATA_DIR / "exercise_db.json"      # 동작 DB
SETTINGS_JSON= DATA_DIR / "settings.json"         # 앱 설정(방문 실수령 등)

# 🍒 PIN (Streamlit Cloud secrets에 CHERRY_PW 가 있으면 그 값 사용)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

# 지점 표기: 내부는 F/R/V, 화면 라벨은 한글
SITE_LABEL = {"F":"플로우","R":"리유","V":"방문"}
SITE_FROM_KO = {"플로우":"F","리유":"R","방문":"V"}
SITES = ["F","R","V"]
SITE_COLOR = {"F":"#d9f0ff", "R":"#f0f0f0", "V":"#e9fbe9"}

# 그룹/개인
SESSION_TYPES = ["개인","그룹"]

# 기구별 기본 동작(요약본; 필요 시 JSON에서 확장/수정 가능)
EX_DB_DEFAULT: Dict[str, List[str]] = {
    "Mat(Basic)": [
        "Roll down","The hundred","Single leg circles","Rolling like a ball",
        "Single leg stretch","Double leg stretch","Spine stretch forward"
    ],
    "Reformer": [
        "Footwork series","The hundred","Coordination","Long box - pulling straps",
        "Backstroke","Short box series","Long stretch series","Elephant",
        "Knee stretch series","Running","Pelvic lift","Side split","Front split"
    ],
    "Cadillac": [
        "Roll back","Leg spring series","Tower","Monkey","Push through bar",
        "Arm series","Shoulder bridge","Teaser"
    ],
    "Wunda chair": ["Footwork series","Push down","Pull up","Spine stretch forward","Teaser"],
    "Barrel/Spine": ["Swan","Horseback","Side sit up","Ballet stretch side","Thigh stretch"],
    "기타": []
}

# =============================================================================
# 파일/설정 유틸
# =============================================================================
def load_settings() -> dict:
    """앱 설정 로드(없으면 기본값 생성). 현재는 방문 실수령만 사용."""
    default = {"visit_net": 0}  # 방문 수업 실수령(원) — 🍒 탭에서 설정
    if SETTINGS_JSON.exists():
        try:
            return {**default, **json.loads(SETTINGS_JSON.read_text(encoding="utf-8"))}
        except Exception:
            return default
    SETTINGS_JSON.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
    return default

def save_settings(d: dict):
    SETTINGS_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)

    # 멤버 파일
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","지점","유형","등록일",
            "총등록","남은횟수","최근재등록일","메모"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

    # 세션 파일
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이","숙제",
            "메모","취소","사유","분","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

    # 동작 DB
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

    # 설정
    load_settings()  # 없으면 생성

def upgrade_members_schema(df: pd.DataFrame) -> pd.DataFrame:
    """예전 CSV 호환: 누락 컬럼을 추가하고, 지점 한글을 F/R/V로 변환."""
    need_cols = ["id","이름","연락처","지점","유형","등록일","총등록","남은횟수","최근재등록일","메모"]
    for c in need_cols:
        if c not in df.columns:
            df[c] = ""
    # 지점 KO → F/R/V
    df["지점"] = df["지점"].replace(SITE_FROM_KO)
    df.loc[~df["지점"].isin(SITES), "지점"] = "F"
    # 유형 기본값
    df.loc[~df["유형"].isin(["개인","방문"]), "유형"] = "개인"
    return df[need_cols]

def upgrade_sessions_schema(df: pd.DataFrame) -> pd.DataFrame:
    need = ["id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이","숙제",
            "메모","취소","사유","분","페이(총)","페이(실수령)"]
    for c in need:
        if c not in df.columns:
            df[c] = ""
    # 지점 KO → F/R/V
    df["지점"] = df["지점"].replace(SITE_FROM_KO)
    df.loc[~df["지점"].isin(SITES), "지점"] = "F"
    # 타입 보정
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        for c in ["인원","분","페이(총)","페이(실수령)"]:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df[need]

def load_members() -> pd.DataFrame:
    df = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return upgrade_members_schema(df)

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return upgrade_sessions_schema(df)

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

# -----------------------------------------------------------------------------
ensure_files()
settings = load_settings()
members = load_members()
sessions = load_sessions()
ex_db = load_ex_db()

# =============================================================================
# 공통 도움 함수
# =============================================================================
def tag(text: str, bg: str) -> str:
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def calc_pay(site: str, session_type: str, headcount: int) -> Tuple[float,float]:
    """
    returns (gross, net)
    F(플로우): 회당 35,000원, 3.3% 공제
    R(리유): 개인 30,000 / 3명 40,000 / 2명 35,000(듀엣) / 1명 25,000 (공제 없음)
    V(방문): 🍒 설정의 visit_net 사용 (gross=net=설정값)
    """
    site = site if site in SITES else "F"
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
        if headcount == 3:
            return 40000.0, 40000.0
        if headcount == 1:
            return 25000.0, 25000.0
        return 30000.0, 30000.0
    # 방문
    visit_net = float(settings.get("visit_net", 0) or 0)
    return visit_net, visit_net

# =============================================================================
# =============================================================================
# =============================================================================
# 사이드바 메뉴 (불릿 제거, 깔끔하게 버튼 형식)

if "page" not in st.session_state:
    st.session_state.page = "schedule"   # 첫 페이지: 스케줄

MENU = {
    "📅 스케줄": "schedule",
    "✍️ 세션": "session",
    "👥 멤버": "member",
    "📋 리포트": "report",
    "🍒": "cherry"
}

st.sidebar.markdown("## 메뉴")

# CSS로 버튼 스타일 지정
st.markdown("""
    <style>
    .sidebar-button {
        display:block;
        font-size:20px;
        padding:8px 6px;
        margin-bottom:4px;
        text-align:left;
        background-color:transparent;
        border:none;
        cursor:pointer;
    }
    .sidebar-button:hover {
        font-weight:700;
        color:#FF4B4B;
    }
    .active {
        font-weight:800;
        color:#FF4B4B;
    }
    </style>
""", unsafe_allow_html=True)

# 메뉴 버튼 만들기
for label, key in MENU.items():
    cls = "active" if st.session_state.page == key else ""
    if st.sidebar.button(label, key=f"_menu_{key}"):
        st.session_state.page = key
    st.sidebar.markdown(
        f'<div class="sidebar-button {cls}">{label}</div>',
        unsafe_allow_html=True
    )
# =============================================================================
# 페이지: 스케줄
# =============================================================================
if st.session_state.page == "schedule":
    st.header("📅 스케줄")
    if sessions.empty:
        st.info("세션 데이터가 없습니다. 먼저 세션을 기록해 주세요.")
    else:
        mode = st.segmented_control("보기", options=["일","주","월"], default="주")
        base = st.date_input("기준 날짜", value=date.today())
        base_dt = datetime.combine(base, datetime.min.time())

        if mode == "일":
            start = base_dt
            end = start + timedelta(days=1)
        elif mode == "주":
            start = base_dt - timedelta(days=base_dt.weekday())  # 월요일
            end   = start + timedelta(days=7)
        else:
            start = base_dt.replace(day=1)
            end   = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

        df = sessions.copy()
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        view = df[(df["날짜"]>=start) & (df["날짜"]<end)].sort_values("날짜")

        if view.empty:
            st.info("해당 기간에 일정이 없습니다.")
        else:
            view["날짜표시"] = view["날짜"].dt.strftime("%m/%d %a %H:%M")
            rows = []
            for _, r in view.iterrows():
                name_html = f'<span style="font-size:16px; font-weight:800;">{r["이름"] if r["이름"] else "(그룹)"}'
                name_html += '</span>'
                chip = tag(SITE_LABEL.get(r["지점"], r["지점"]), SITE_COLOR.get(r["지점"], "#eee"))
                title = f'{r["날짜표시"]} · {chip} · {name_html}'
                body  = f'{r["구분"]} · {r["레벨"]} · {r["기구"]}'
                # 지난 수업 내용(동작·특이·숙제) 표시
                extra = []
                if r["동작(리스트)"]:
                    extra.append("동작: " + r["동작(리스트)"])
                if r["추가동작"]:
                    extra.append("+" + r["추가동작"])
                if r["특이"]:
                    extra.append("특이: " + r["특이"])
                if r["숙제"]:
                    extra.append("숙제: " + r["숙제"])
                if extra:
                    body += " · " + " / ".join(extra)
                if bool(r["취소"]):
                    title = f'<s>{title}</s>'
                rows.append(f"<div style='padding:10px; border-bottom:1px solid #333'>{title}<br><span style='color:#bbb'>{body}</span></div>")
            st.markdown("<div>"+ "".join(rows) +"</div>", unsafe_allow_html=True)

# =============================================================================
# 페이지: 세션
# =============================================================================
elif st.session_state.page == "session":
    st.header("✍️ 세션 기록")
    if members.empty:
        st.info("먼저 멤버를 등록하세요. (👥 멤버 탭)")
    else:
        c0, c1, c2, c3 = st.columns([1,1,1,1])
        with c0:
            day = st.date_input("날짜", value=date.today())
            time_str = st.time_input("시간", value=datetime.now().time())
        with c1:
            session_type = st.radio("구분", SESSION_TYPES, horizontal=True)
        with c2:
            if session_type == "개인":
                mname = st.selectbox("멤버", members["이름"].tolist())
                # 멤버 기본 지점
                mrow = members.loc[members["이름"]==mname].iloc[0]
                site_default = mrow["지점"] if mrow["지점"] in SITES else "F"
                site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES],
                                    index=SITES.index(site_default), format_func=lambda x:x)
                site = SITE_FROM_KO.get(site, site) if site in SITE_FROM_KO else {v:k for k,v in SITE_LABEL.items()}.get(site, site)
            else:
                site = st.selectbox("지점", [SITE_LABEL[s] for s in SITES], index=0)
                site = SITE_FROM_KO.get(site, site)
                mname = ""
        with c3:
            minutes = st.number_input("수업 분", 10, 180, 50, 5)

        c4 = st.columns([1,1,1,1])
        with c4[0]:
            level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"])
        with c4[1]:
            equip = st.selectbox("기구", ["Reformer","Cadillac","Wunda chair","Barrel/Spine","Mat(Basic)","기타"])
        with c4[2]:
            headcount = st.number_input("인원(그룹)", 1, 10, 2 if session_type=="그룹" else 1, 1, disabled=(session_type=="개인"))
        with c4[3]:
            st.write("")  # 자리 맞춤

        # 동작 선택: 개인일 때만 노출, 기구 매칭 옵션
        chosen = []
        add_free = ""
        spec = ""
        hw = ""
        if session_type == "개인":
            # 기구 필터
            per_moves = []
            # EX JSON에서 해당 카테고리만 로드
            cat = equip
            db = load_ex_db()
            for k, v in db.items():
                if k == cat:
                    per_moves.extend(v)
            # 멀티 선택 + 자유입력
            chosen = st.multiselect("운동 동작(복수)", sorted(per_moves))
            add_free = st.text_input("추가 동작(콤마 , 로 구분)", placeholder="ex) Side bends, Mermaid")
            spec = st.text_area("특이사항", height=70, placeholder="ex) 어깨 불편, 허리 통증 완화 등")
            hw   = st.text_area("숙제", height=70, placeholder="ex) Cat&cow 10회, 호흡 연습 등")
        else:
            spec = st.text_area("특이사항(그룹)", height=70)

        cancel = st.checkbox("취소")
        reason = st.text_input("사유(선택)", placeholder="ex) 회원 사정/강사 사정 등")
        memo   = st.text_area("메모(선택)", height=60)

        if st.button("세션 저장", use_container_width=True):
            when = datetime.combine(day, time_str)

            # 개인 추가 동작을 DB에 누적(기타 카테고리)
            if session_type == "개인" and add_free.strip():
                new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
                exdb = load_ex_db()
                exdb.setdefault("기타", [])
                for nm in new_moves:
                    if nm not in exdb["기타"]:
                        exdb["기타"].append(nm)
                save_ex_db(exdb)

            gross, net = calc_pay(site, session_type, int(headcount))

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
                "특이": spec,
                "숙제": hw if session_type=="개인" else "",
                "메모": memo,
                "취소": bool(cancel),
                "사유": reason,
                "분": int(minutes),
                "페이(총)": float(gross),
                "페이(실수령)": float(net)
            }])
            sessions_local = load_sessions()
            sessions_local = pd.concat([sessions_local, row], ignore_index=True)
            save_sessions(sessions_local)

            # 개인 세션 차감
            if session_type=="개인" and mname and not cancel and (mname in members["이름"].values):
                ms = load_members()
                idx = ms.index[ms["이름"]==mname][0]
                remain = max(0, int(float(ms.loc[idx,"남은횟수"] or 0)) - 1)
                ms.loc[idx,"남은횟수"] = str(remain)
                save_members(ms)

            st.success("세션 저장 완료!")

    # 최근 목록(페이 컬럼 숨김)
    st.subheader("최근 세션")
    sessions_view = load_sessions()
    if sessions_view.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        v = sessions_view.sort_values("날짜", ascending=False).copy()
        v["날짜"] = pd.to_datetime(v["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        hide = ["페이(총)","페이(실수령)"]
        show_cols = [c for c in v.columns if c not in hide]
        # 지점 라벨
        v["지점"] = v["지점"].map(SITE_LABEL).fillna(v["지점"])
        st.dataframe(v[show_cols], use_container_width=True, hide_index=True)

# =============================================================================
# 페이지: 멤버
# =============================================================================
elif st.session_state.page == "member":
    st.header("👥 멤버 관리")

    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns([1,1])
        ms = load_members()

        with left:
            existing = ["(새 회원)"] + ms["이름"].tolist()
            sel = st.selectbox("회원 선택", existing)
            # 중복 전화번호 경고
            def dup_phone(p: str, who: str) -> bool:
                if not p.strip(): return False
                df = ms[(ms["연락처"]==p.strip()) & (ms["이름"]!=who)]
                return not df.empty

            base_name = "" if sel=="(새 회원)" else sel
            name = st.text_input("이름", base_name, placeholder="예: 김지현")
            phone = st.text_input(
                "연락처", 
                value="" if sel=="(새 회원)" else (ms.loc[ms["이름"]==sel,"연락처"].iloc[0] if sel in ms["이름"].values else ""),
                placeholder="010-0000-0000"
            )
            if dup_phone(phone, base_name):
                st.warning("⚠️ 동일 전화번호가 이미 존재합니다.")

        with right:
            site_default = "F"
            if sel != "(새 회원)" and sel in ms["이름"].values:
                site_default = ms.loc[ms["이름"]==sel,"지점"].iloc[0] or "F"
            site = st.selectbox("기본 지점", [SITE_LABEL[s] for s in SITES],
                                index=SITES.index(site_default))
            site = SITE_FROM_KO.get(site, site)
            typ_default = "개인"
            if sel != "(새 회원)" and sel in ms["이름"].values:
                typ_default = ms.loc[ms["이름"]==sel,"유형"].iloc[0] or "개인"
            utype = st.selectbox("유형", ["개인","방문"], index=["개인","방문"].index(typ_default))
            reg_default = date.today()
            if sel != "(새 회원)" and sel in ms["이름"].values:
                try:
                    reg_default = pd.to_datetime(ms.loc[ms["이름"]==sel,"등록일"].iloc[0]).date()
                except Exception:
                    reg_default = date.today()
            reg_date = st.date_input("등록일", reg_default)

        note = st.text_input("메모(선택)",
            value="" if sel=="(새 회원)" else ms.loc[ms["이름"]==sel,"메모"].iloc[0] if sel in ms["이름"].values else "")

        add_cnt = st.number_input("재등록 추가 횟수(+)", 0, 100, 0, 1)

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                elif dup_phone(phone, base_name):
                    st.error("동일 전화번호가 이미 존재합니다.")
                else:
                    ms = load_members()
                    if sel=="(새 회원)":
                        new_id = str(len(ms)+1)
                        row = pd.DataFrame([{
                            "id":new_id,"이름":name.strip(),"연락처":phone.strip(),
                            "지점":site,"유형":utype,"등록일":reg_date.isoformat(),
                            "총등록":"0","남은횟수":"0","최근재등록일":"","메모":note
                        }])
                        ms = pd.concat([ms, row], ignore_index=True)
                        save_members(ms)
                        st.success(f"신규 등록: {name}")
                    else:
                        idx = ms.index[ms["이름"]==sel][0]
                        ms.loc[idx,"이름"] = name.strip()
                        ms.loc[idx,"연락처"] = phone.strip()
                        ms.loc[idx,"지점"] = site
                        ms.loc[idx,"유형"] = utype
                        ms.loc[idx,"등록일"] = reg_date.isoformat()
                        ms.loc[idx,"메모"] = note
                        save_members(ms)
                        st.success("수정 완료")

        with c2:
            if st.button("재등록(+반영)", use_container_width=True, disabled=(sel=="(새 회원)")):
                if sel=="(새 회원)":
                    st.error("기존 회원을 먼저 선택하세요.")
                else:
                    ms = load_members()
                    idx = ms.index[ms["이름"]==sel][0]
                    total = int(float(ms.loc[idx,"총등록"] or 0)) + int(add_cnt)
                    remain = int(float(ms.loc[idx,"남은횟수"] or 0)) + int(add_cnt)
                    ms.loc[idx,"총등록"] = str(total)
                    ms.loc[idx,"남은횟수"] = str(remain)
                    ms.loc[idx,"최근재등록일"] = date.today().isoformat()
                    save_members(ms)
                    st.success(f"{sel} 재등록 +{add_cnt}회 반영")

        with c3:
            del_name = st.selectbox("삭제 대상", ms["이름"].tolist() if not ms.empty else [])
            if st.button("멤버 삭제", use_container_width=True, disabled=ms.empty):
                ms = ms[ms["이름"]!=del_name].reset_index(drop=True)
                save_members(ms)
                st.success(f"{del_name} 삭제 완료")

    with st.expander("📋 현재 멤버 보기 (토글)", expanded=False):
        ms = load_members()
        if ms.empty:
            st.info("등록된 멤버가 없습니다.")
        else:
            show = ms.copy()
            for c in ["등록일","최근재등록일"]:
                show[c] = pd.to_datetime(show[c], errors="coerce").dt.date.astype(str)
            show["지점"] = show["지점"].map(SITE_LABEL).fillna(show["지점"])
            st.dataframe(show, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📈 월간 Top5 동작 (개인 세션 기준)")

    ms = load_members()
    if not ms.empty:
        msel = st.selectbox("멤버 선택", ms["이름"].tolist())
        now_ym = date.today().strftime("%Y-%m")
        month = st.text_input("월(YYYY-MM)", value=now_ym)

        ss = load_sessions()
        if ss.empty:
            st.info("세션 데이터가 없습니다.")
        else:
            df = ss[(ss["구분"]=="개인") & (ss["이름"]==msel)].copy()
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            cur = df[df["YM"]==month]
            if cur.empty:
                st.info("해당 월 데이터가 없습니다.")
            else:
                # 동작 분해
                def explode_moves(s: pd.Series) -> pd.DataFrame:
                    tmp = s.fillna("").str.cat(["; ",""], sep="")  # 항상 세미콜론 보장
                    out = []
                    for x in tmp:
                        parts = [p.strip() for p in x.split(";") if p.strip()]
                        out.extend(parts)
                    return pd.DataFrame({"동작": out})
                mov = explode_moves(cur["동작(리스트)"])
                top5 = mov.value_counts("동작").head(5).reset_index()
                top5.columns = ["동작","횟수"]
                c1, c2 = st.columns([1,1])
                with c1:
                    st.write("**이달 Top5**")
                    chart = alt.Chart(top5).mark_bar().encode(
                        x=alt.X("횟수:Q"),
                        y=alt.Y("동작:N", sort="-x")
                    )
                    st.altair_chart(chart, use_container_width=True)

                with c2:
                    st.write("**최근 6개월 추이**")
                    last6 = pd.to_datetime(df["날짜"])
                    mask = last6 >= (pd.Timestamp.today() - pd.DateOffset(months=6))
                    df2 = df[mask].copy()
                    df2["YM"] = pd.to_datetime(df2["날짜"]).dt.strftime("%Y-%m")

                    lines = []
                    for mv in top5["동작"].tolist():
                        cnt = df2["동작(리스트)"].fillna("").apply(lambda s: mv in s.split(";"))
                        tmp = pd.DataFrame({"YM": df2["YM"], "hit": cnt.astype(int)})
                        agg = tmp.groupby("YM")["hit"].sum().reset_index()
                        agg["동작"] = mv
                        lines.append(agg)
                    if lines:
                        trend = pd.concat(lines, ignore_index=True)
                        chart2 = alt.Chart(trend).mark_line(point=True).encode(
                            x="YM:N", y="hit:Q", color="동작:N"
                        )
                        st.altair_chart(chart2, use_container_width=True)
                # 표
                st.write("**세부표(해당 월 개인 세션)**")
                cur_view = cur.copy()
                cur_view["지점"] = cur_view["지점"].map(SITE_LABEL)
                cur_view["날짜"] = pd.to_datetime(cur_view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
                st.dataframe(cur_view[["날짜","지점","레벨","기구","동작(리스트)","추가동작","특이","숙제"]],
                             use_container_width=True, hide_index=True)

# =============================================================================
# 페이지: 리포트 (회원 동작만)
# =============================================================================
elif st.session_state.page == "report":
    st.header("📋 리포트 (회원 동작)")
    ss = load_sessions()
    if ss.empty:
        st.info("데이터가 없습니다.")
    else:
        # 개인 세션만
        df = ss[ss["구분"]=="개인"].copy()
        df["Y"]  = pd.to_datetime(df["날짜"]).dt.year
        df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")

        mnames = sorted(df["이름"].dropna().unique().tolist())
        if not mnames:
            st.info("개인 세션 데이터가 없습니다.")
        else:
            msel = st.selectbox("멤버 선택", mnames)
            month = st.text_input("월(YYYY-MM)", value=date.today().strftime("%Y-%m"))

            cur = df[(df["이름"]==msel) & (df["YM"]==month)]
            if cur.empty:
                st.info("해당 월 데이터가 없습니다.")
            else:
                def explode_moves(s: pd.Series) -> pd.DataFrame:
                    out=[]
                    for x in s.fillna(""):
                        parts = [p.strip() for p in x.split(";") if p.strip()]
                        out.extend(parts)
                    return pd.DataFrame({"동작": out})
                top5 = explode_moves(cur["동작(리스트)"]).value_counts("동작").head(5).reset_index()
                top5.columns = ["동작","횟수"]
                st.write("**Top5 동작**")
                st.altair_chart(alt.Chart(top5).mark_bar().encode(x="횟수:Q", y=alt.Y("동작:N", sort="-x")),
                                use_container_width=True)

                # 6개월 추이
                last6mask = pd.to_datetime(df["날짜"]) >= (pd.Timestamp.today() - pd.DateOffset(months=6))
                df2 = df[(df["이름"]==msel) & last6mask].copy()
                df2["YM"] = pd.to_datetime(df2["날짜"]).dt.strftime("%Y-%m")
                lines=[]
                for mv in top5["동작"].tolist():
                    cnt = df2["동작(리스트)"].fillna("").apply(lambda s: mv in s.split(";"))
                    tmp = pd.DataFrame({"YM": df2["YM"], "hit": cnt.astype(int)})
                    agg = tmp.groupby("YM")["hit"].sum().reset_index()
                    agg["동작"] = mv
                    lines.append(agg)
                if lines:
                    trend = pd.concat(lines, ignore_index=True)
                    st.write("**최근 6개월 추이**")
                    st.altair_chart(
                        alt.Chart(trend).mark_line(point=True).encode(x="YM:N", y="hit:Q", color="동작:N"),
                        use_container_width=True
                    )

# =============================================================================
# 페이지: 🍒 (수입 + 설정)
# =============================================================================
elif st.session_state.page == "cherry":
    st.header("🍒")
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****")
        if st.button("열기"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        st.subheader("설정")
        visit_net = st.number_input("방문 수업 실수령(원)", 0, 1_000_000, int(settings.get("visit_net", 0)), 1000)
        if st.button("설정 저장"):
            settings["visit_net"] = int(visit_net)
            save_settings(settings)
            st.success("저장 완료!")

        st.markdown("---")
        st.subheader("수입 요약")
        ss = load_sessions()
        if ss.empty:
            st.info("세션 데이터가 없습니다.")
        else:
            df = ss.copy()
            df["Y"]  = pd.to_datetime(df["날짜"]).dt.year
            df["YM"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m")
            month_sum = df.groupby("YM")["페이(실수령)"].sum().astype(int).reset_index()
            year_sum  = df.groupby("Y")["페이(실수령)"].sum().astype(int).reset_index()
            col1, col2 = st.columns(2)
            with col1:
                st.write("**월별 합계**")
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with col2:
                st.write("**연도 합계**")
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.subheader("상세(개별 세션)")
            view = df.sort_values("날짜", ascending=False)
            view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            view["지점"] = view["지점"].map(SITE_LABEL).fillna(view["지점"])
            st.dataframe(view, use_container_width=True, hide_index=True)


