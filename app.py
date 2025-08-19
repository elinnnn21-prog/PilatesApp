# app.py
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List
import pandas as pd
import streamlit as st

# ───────────────────────── 기본 설정 ─────────────────────────
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")

DATA_DIR = Path(".")
MEMBERS_CSV  = DATA_DIR / "members.csv"
SESSIONS_CSV = DATA_DIR / "sessions.csv"
EX_JSON      = DATA_DIR / "exercise_db.json"

# 🍒 PIN (secrets.toml 에 CHERRY_PW가 있으면 그 값, 없으면 2974)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

# 지점 코드: F=Flow, R=Reyou, V=Visit
SITES = ["F", "R", "V"]
SITE_COLOR = {"F": "#d9f0ff", "R": "#f0f0f0", "V": "#e9fbe9"}

# ── 동작 DB(기본) : 필요하면 자유롭게 늘려 쓰기 ──
EX_DB_DEFAULT: Dict[str, List[str]] = {
    # Mat
    "Mat(Basic)": [
        "Roll down","The hundred","Roll up","Single leg circles","Rolling like a ball",
        "Single leg stretch","Double leg stretch","Spine stretch forward"
    ],
    "Mat(Intermediate/Advanced)": [
        "Criss cross","Open leg rocker","Saw","Neck pull","Side kick series",
        "Teaser","Swimming","Scissors","Bicycle","Jack knife","Seal"
    ],
    # Reformer
    "Reformer": [
        "Footwork series","The hundred","Coordination","Long box - pulling straps",
        "Backstroke","Short box series","Long stretch series","Elephant",
        "Knee stretch series","Running","Pelvic lift","Side split","Front split","Teaser"
    ],
    # Cadillac
    "Cadillac": [
        "Roll back","Leg spring series","Tower","Monkey","Teaser w/push through bar",
        "Arm series","Push through bar","Hip circles","Shoulder bridge","Breathing"
    ],
    # Wunda & Barrel/Spine etc.
    "Wunda chair": [
        "Footwork series","Push down","Pull up","Spine stretch forward",
        "Teaser","Mountain climb","Tabletop","Front balance control"
    ],
    "Barrel/Spine": [
        "Swan","Horseback","Side sit up","Ballet stretch side","Thigh stretch"
    ],
    "Electric chair": ["Pumping series","Going up front"],
    "Pedi-pull": ["Chest expansion","Arm circles","Knee bends","Centering"],
    "기타": []
}
# 기구 ↔ 카테고리 매핑(세션에서 기구 선택 시 해당 동작만 보여주기)
EQUIP_TO_CATS = {
    "Mat": ["Mat(Basic)", "Mat(Intermediate/Advanced)"],
    "Reformer": ["Reformer"],
    "Cadillac": ["Cadillac"],
    "Wunda chair": ["Wunda chair"],
    "Barrel/Spine": ["Barrel/Spine"],
    "Electric chair": ["Electric chair"],
    "Pedi-pull": ["Pedi-pull"],
    "기타": ["기타"],
}

# ───────────────────────── 파일 유틸 ─────────────────────────
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMBERS_CSV.exists():
        pd.DataFrame(columns=[
            "id","이름","연락처","지점","등록일","총등록","남은횟수",
            "최근재등록일","방문실수령","메모"
        ]).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")
    if not SESSIONS_CSV.exists():
        pd.DataFrame(columns=[
            "id","날짜","지점","구분","이름","인원","레벨","기구",
            "동작(리스트)","추가동작","특이사항","숙제","메모",
            "취소","사유","분","페이(총)","페이(실수령)"
        ]).to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")
    if not EX_JSON.exists():
        pd.Series(EX_DB_DEFAULT).to_json(EX_JSON, force_ascii=False)

def load_members() -> pd.DataFrame:
    df = pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    # 타입 보정
    if "방문실수령" in df.columns:
        df["방문실수령"] = pd.to_numeric(df["방문실수령"], errors="coerce").fillna(0).astype(int)
    return df

def save_members(df: pd.DataFrame):
    out = df.copy()
    out.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_sessions() -> pd.DataFrame:
    df = pd.read_csv(SESSIONS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    if df.empty:
        return df
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    for c in ["인원","분","페이(총)","페이(실수령)"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["취소"] = df["취소"].astype(str).str.lower().isin(["true","1","y","yes"])
    return df

def save_sessions(df: pd.DataFrame):
    out = df.copy()
    if not out.empty:
        out["날짜"] = pd.to_datetime(out["날짜"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(SESSIONS_CSV, index=False, encoding="utf-8-sig")

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
members = load_members()
sessions = load_sessions()

# ───────────────────────── 공통 ─────────────────────────
def tag(text, bg):
    return f'<span style="background:{bg}; padding:2px 8px; border-radius:8px; font-size:12px;">{text}</span>'

def calc_pay(site: str, session_type: str, headcount: int, visit_pay: float|None) -> tuple[float, float]:
    """
    returns (gross, net)
    F(Flow): 회당 35,000원, 3.3% 공제
    R(Reyou): 개인 30,000 / 3명 40,000 / 2명 30,000 / 1명 25,000 / 듀엣 35,000 (공제 없음)
    V(Visit): 멤버의 '방문실수령' 사용 (gross=net)
    """
    gross = net = 0.0
    if site == "F":
        gross = 35000.0
        net = round(gross * 0.967, 0)
    elif site == "R":
        if session_type == "개인":
            gross = net = 30000.0
        else:  # 그룹
            if headcount == 2:
                gross = net = 35000.0
            elif headcount == 3:
                gross = net = 40000.0
            elif headcount == 1:
                gross = net = 25000.0
            else:
                gross = net = 30000.0
    else:  # V
        gross = net = float(visit_pay or 0)
    return gross, net

def extract_moves(s: str):
    out = []
    for p in str(s).split(";"):
        p = p.strip()
        if not p:
            continue
        if "·" in p:
            out.append(p.split("·", 1)[1].strip())
        else:
            out.append(p)
    return out

# ───────────────────────── 네비게이션 ─────────────────────────
if "nav" not in st.session_state:
    st.session_state["nav"] = "📅 스케줄"

nav_options = ["📅 스케줄", "✍️ 세션", "👥 멤버", "📋 리포트", "🍒"]
with st.sidebar:
    st.markdown("### 메뉴")
    nav = st.radio(
        label="",
        options=nav_options,
        index=nav_options.index(st.session_state["nav"]),
        key="nav_radio"
    )
st.session_state["nav"] = nav

# ───────────────────────── 👥 멤버 ─────────────────────────
if nav == "👥 멤버":
    st.title("👥 멤버 관리")

    with st.expander("➕ 등록/수정/재등록", expanded=True):
        left, right = st.columns(2)
        with left:
            existing = ["(새 회원)"] + members["이름"].tolist()
            sel = st.selectbox("회원 선택", existing, key="mem_sel")
            # 선택된 기존 값 로드
            if sel != "(새 회원)" and sel in members["이름"].values:
                row = members[members["이름"]==sel].iloc[0]
                name_default = row["이름"]
                phone_default = row["연락처"]
                site_default = row["지점"] or "F"
                reg_default = pd.to_datetime(row["등록일"] or date.today()).date()
                note_default = row["메모"]
                visit_default = int(row["방문실수령"]) if str(row["방문실수령"]).strip() else 0
            else:
                name_default = ""
                phone_default = ""
                site_default = "F"
                reg_default = date.today()
                note_default = ""
                visit_default = 0

            name  = st.text_input("이름", name_default, placeholder="예: 김지현", key="mem_name")
            phone = st.text_input("연락처", phone_default, placeholder="010-0000-0000", key="mem_phone")

        with right:
            site = st.selectbox("기본 지점(F/R/V)", SITES, index=SITES.index(site_default), key="mem_site")
            reg  = st.date_input("등록일", reg_default, key="mem_reg")
            visit_pay = st.number_input("방문 실수령(원)", 0, 1_000_000, visit_default, 1000, key="mem_visit")
        note = st.text_input("메모(선택)", note_default, key="mem_note")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("저장/수정", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                else:
                    # 전화번호 중복 검사
                    if phone.strip():
                        dup = members[(members["연락처"]==phone.strip()) & (members["이름"]!=name.strip())]
                        if not dup.empty:
                            st.warning(f"⚠️ 동일 전화번호가 이미 등록되어 있습니다: {dup.iloc[0]['이름']}")
                    if sel == "(새 회원)":
                        new_id = str(len(members)+1)
                        row = pd.DataFrame([{
                            "id":new_id,"이름":name.strip(),"연락처":phone.strip(),
                            "지점":site,"등록일":reg.isoformat(),"총등록":"0","남은횟수":"0",
                            "최근재등록일":"","방문실수령":int(visit_pay),"메모":note
                        }])
                        members[:] = pd.concat([members, row], ignore_index=True)
                        save_members(members)
                        st.success(f"신규 등록: {name}")
                    else:
                        idx = members.index[members["이름"]==sel][0]
                        members.loc[idx, ["이름","연락처","지점","등록일","메모","방문실수령"]] = [
                            name.strip(), phone.strip(), site, reg.isoformat(), note, int(visit_pay)
                        ]
                        save_members(members)
                        st.success("수정 완료")

        with c2:
            add_cnt = st.number_input("재등록 횟수(+)", 0, 100, 0, 1, key="mem_addcnt")
            if st.button("재등록 반영", use_container_width=True, disabled=(sel=="(새 회원)")):
                if sel=="(새 회원)":
                    st.error("기존 회원을 먼저 선택하세요.")
                else:
                    idx = members.index[members["이름"]==sel][0]
                    total = int(float(members.loc[idx,"총등록"] or 0)) + int(add_cnt)
                    remain = int(float(members.loc[idx,"남은횟수"] or 0)) + int(add_cnt)
                    members.loc[idx,"총등록"] = str(total)
                    members.loc[idx,"남은횟수"] = str(remain)
                    members.loc[idx,"최근재등록일"] = date.today().isoformat()
                    save_members(members)
                    st.success(f"{sel} 재등록 +{add_cnt}회 반영")

        with c3:
            del_name = st.selectbox("삭제 대상", members["이름"].tolist() if not members.empty else [], key="mem_del")
            if st.button("멤버 삭제", use_container_width=True, disabled=members.empty):
                members = members[members["이름"]!=del_name].reset_index(drop=True)
                save_members(members)
                st.success(f"{del_name} 삭제 완료")

    with st.expander("📋 현재 멤버 보기", expanded=False):
        if members.empty:
            st.info("등록된 멤버가 없습니다.")
        else:
            show = members.copy()
            st.dataframe(show, use_container_width=True, hide_index=True)

# ───────────────────────── ✍️ 세션 ─────────────────────────
elif nav == "✍️ 세션":
    st.title("✍️ 세션 기록")

    ex_db = load_ex_db()

    if members.empty:
        st.info("먼저 멤버를 등록하세요.")
    else:
        cols = st.columns(4)
        with cols[0]:
            day = st.date_input("날짜", value=date.today(), key="ses_day")
            t   = st.time_input("시간", value=datetime.now().time(), key="ses_time")
        with cols[1]:
            session_type = st.radio("구분", ["개인","그룹"], horizontal=True, key="ses_type")
        with cols[2]:
            site = st.selectbox("지점(F/R/V)", SITES, key="ses_site")
        with cols[3]:
            minutes = st.number_input("수업 분", 10, 180, 50, 5, key="ses_minutes")

        c2 = st.columns(4)
        with c2[0]:
            level = st.selectbox("레벨", ["Basic","Intermediate","Advanced","Mixed","NA"], key="ses_level")
        with c2[1]:
            equip = st.selectbox("기구", list(EQUIP_TO_CATS.keys()), key="ses_equip")
        with c2[2]:
            headcount = st.number_input("인원(그룹)", 1, 10, 2 if session_type=="그룹" else 1, 1,
                                        disabled=(session_type=="개인"), key="ses_head")
        with c2[3]:
            cancel = st.checkbox("취소", key="ses_cancel")

        # 개인/그룹 분기
        if session_type == "개인":
            mname = st.selectbox("멤버", members["이름"].tolist(), key="ses_mname")
            # 멤버의 기본지점 제안
            if mname and mname in members["이름"].values:
                default_site = members.loc[members["이름"]==mname,"지점"].iloc[0] or "F"
                if site != default_site:
                    st.caption(f"기본 지점 제안: {default_site}")

            # 기구에 해당하는 동작만 표시
            cats = EQUIP_TO_CATS.get(equip, ["기타"])
            per_moves = []
            for c in cats:
                per_moves.extend([f"{c} · {m}" for m in ex_db.get(c, [])])
            per_moves.extend(ex_db.get("기타", []))
            chosen = st.multiselect("운동 동작(복수)", sorted(per_moves), key="ses_moves")
            add_free = st.text_input("추가 동작(콤마 , 로)", key="ses_addfree")

            spec = st.text_area("특이사항", key="ses_spec")
            hw   = st.text_area("숙제", key="ses_homework")
        else:
            mname = ""
            chosen = []
            add_free = ""
            spec = st.text_area("특이사항(그룹)", key="ses_spec_grp")
            hw   = ""

        reason = st.text_input("사유(선택)", key="ses_reason")
        memo   = st.text_area("메모(선택)", height=70, key="ses_memo")

        # 저장
        if st.button("세션 저장", use_container_width=True):
            when = datetime.combine(day, t)

            # 자유 동작 DB에 누적
            if add_free.strip():
                new_moves = [x.strip() for x in add_free.split(",") if x.strip()]
                exdb = load_ex_db()
                exdb.setdefault("기타", [])
                for nm in new_moves:
                    if nm not in exdb["기타"]:
                        exdb["기타"].append(nm)
                save_ex_db(exdb)

            # 방문 실수령(개인 + V) 자동 적용
            visit_pay = 0
            if session_type=="개인" and site=="V" and mname:
                try:
                    visit_pay = int(members.loc[members["이름"]==mname,"방문실수령"].iloc[0])
                except Exception:
                    visit_pay = 0

            gross, net = calc_pay(site, session_type, int(headcount), visit_pay)

            row = pd.DataFrame([{
                "id": str(len(sessions)+1),
                "날짜": when,
                "지점": site,
                "구분": session_type,
                "이름": mname if session_type=="개인" else "",
                "인원": int(headcount) if session_type=="그룹" else 1,
                "레벨": level,
                "기구": equip,
                "동작(리스트)": "; ".join(chosen),
                "추가동작": add_free,
                "특이사항": spec,
                "숙제": hw,
                "메모": memo,
                "취소": bool(cancel),
                "사유": reason,
                "분": int(minutes),
                "페이(총)": float(gross),
                "페이(실수령)": float(net)
            }])
            sessions[:] = pd.concat([sessions, row], ignore_index=True)
            save_sessions(sessions)

            # 개인 세션 남은횟수 차감
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
        hide_cols = ["페이(총)","페이(실수령)"]
        show_cols = [c for c in view.columns if c not in hide_cols]
        view["날짜"] = pd.to_datetime(view["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ───────────────────────── 📅 스케줄 ─────────────────────────
elif nav == "📅 스케줄":
    st.title("📅 스케줄")

    if sessions.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        mode = st.segmented_control("보기", options=["일","주","월"], default="주", key="sch_mode")
        base = st.date_input("기준 날짜", value=date.today(), key="sch_base")
        base_dt = datetime.combine(base, datetime.min.time())

        if mode=="일":
            start = base_dt
            end = base_dt + timedelta(days=1)
        elif mode=="주":
            start = base_dt - timedelta(days=base_dt.weekday())
            end = start + timedelta(days=7)
        else:
            start = base_dt.replace(day=1)
            end = (start + pd.offsets.MonthEnd(1)).to_pydatetime() + timedelta(days=1)

        view = sessions[(sessions["날짜"]>=start) & (sessions["날짜"]<end)].copy()
        if view.empty:
            st.info("해당 기간 일정이 없습니다.")
        else:
            view = view.sort_values("날짜")
            # 취소 토글/메모 빠른수정
            for i, r in view.iterrows():
                name_html = f"<span style='font-size:16px; font-weight:800;'>{r['이름'] if r['이름'] else '(그룹)'}</span>"
                site_chip = tag(r["지점"], SITE_COLOR.get(r["지점"], "#eee"))
                body = f"{r['구분']} · {r['레벨']} · {r['기구']}"
                # 지난 수업엔 동작 표시
                if r["날짜"] <= datetime.now() and (r["동작(리스트)"] or r["추가동작"]):
                    body += " · 동작: " + ", ".join([r["동작(리스트)"], r["추가동작"]]).strip(" ,")
                if str(r.get("특이사항","")).strip():
                    body += f" · 특이: {r['특이사항']}"
                if str(r.get("숙제","")).strip():
                    body += f" · 숙제: {r['숙제']}"

                title = f"{pd.to_datetime(r['날짜']).strftime('%m/%d %a %H:%M')} · {site_chip} · {name_html}"
                if bool(r["취소"]):
                    title = f"<s>{title}</s>"

                with st.container(border=True):
                    st.markdown(title + "<br><span style='color:#bbb'>" + body + "</span>", unsafe_allow_html=True)
                    cc1, cc2, cc3 = st.columns([1,1,2])
                    with cc1:
                        new_cancel = st.checkbox("취소", value=bool(r["취소"]), key=f"cancel_{i}")
                    with cc2:
                        new_reason = st.text_input("사유", value=r["사유"], key=f"reason_{i}")
                    with cc3:
                        if st.button("저장", key=f"save_{i}"):
                            sessions.loc[i, "취소"] = bool(new_cancel)
                            sessions.loc[i, "사유"] = new_reason
                            save_sessions(sessions)
                            st.success("업데이트 완료")
            st.caption("※ 취소/사유는 여기서 바로 수정 가능")

# ───────────────────────── 📋 리포트(회원 동작 전용) ─────────────────────────
elif nav == "📋 리포트":
    st.title("📋 회원 동작 리포트")
    if sessions.empty:
        st.info("세션 데이터가 없습니다.")
    else:
        df = sessions.copy()
        df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
        df = df[(df["구분"]=="개인") & (~df["취소"].astype(bool))]
        members_list = sorted([x for x in df["이름"].unique() if str(x).strip()])
        if not members_list:
            st.info("개인 세션 데이터에 이름이 없습니다.")
        else:
            ctop = st.columns([1,1,2])
            with ctop[0]:
                m = st.selectbox("멤버", members_list, key="rpt_member")
            with ctop[1]:
                base_day = st.date_input("기준 월", value=pd.Timestamp.today(), key="rpt_month")
                ym = pd.Timestamp(base_day).strftime("%Y-%m")

            df["YM"] = df["날짜"].dt.strftime("%Y-%m")
            target = df[df["이름"]==m].copy()
            mv = (target.assign(_moves=target["동작(리스트)"].apply(extract_moves))
                        .explode("_moves"))
            mv = mv[mv["_moves"].astype(str).str.strip()!=""]

            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f"📈 {m} · {ym} · Top5")
                top5 = (mv[mv["YM"]==ym]["_moves"]
                        .value_counts().head(5)
                        .rename_axis("동작").reset_index(name="횟수"))
                if top5.empty:
                    st.info("해당 월 데이터가 없습니다.")
                else:
                    st.bar_chart(top5.set_index("동작"))
                    st.dataframe(top5, use_container_width=True, hide_index=True)

            with col2:
                st.subheader("📊 최근 6개월 추이")
                last6 = (pd.date_range(end=pd.to_datetime(ym+"-01"), periods=6, freq="MS")
                         .strftime("%Y-%m"))
                series = (mv[mv["YM"].isin(last6)]
                          .groupby(["YM","_moves"]).size()
                          .unstack(fill_value=0)
                          .reindex(index=last6, fill_value=0))
                if series.empty:
                    st.info("최근 6개월 데이터가 없습니다.")
                else:
                    st.line_chart(series)

            st.subheader("세부 기록")
            show = target.sort_values("날짜", ascending=False)[
                ["날짜","지점","레벨","기구","동작(리스트)","추가동작","특이사항","숙제","메모"]
            ].copy()
            show["날짜"] = pd.to_datetime(show["날짜"]).dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(show, use_container_width=True, hide_index=True)

# ───────────────────────── 🍒 수입(이모지표시만) ─────────────────────────
elif nav == "🍒":
    st.title("🍒")
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
            st.info("세션 데이터가 없습니다.")
        else:
            df = sessions.copy()
            df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
            df["Y"] = df["날짜"].dt.year
            df["YM"] = df["날짜"].dt.strftime("%Y-%m")

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("월별 합계")
                month_sum = df.groupby("YM")["페이(실수령)"].sum().astype(int).reset_index()
                st.dataframe(month_sum, use_container_width=True, hide_index=True)
            with c2:
                st.subheader("연도 합계")
                year_sum = df.groupby("Y")["페이(실수령)"].sum().astype(int).reset_index()
                st.dataframe(year_sum, use_container_width=True, hide_index=True)

            st.subheader("상세 (개별 세션)")
            view = df.sort_values("날짜", ascending=False).copy()
            view["날짜"] = view["날짜"].dt.strftime("%Y-%m-%d %H:%M")
            st.dataframe(view, use_container_width=True, hide_index=True)
