# app.py — Pilates Manager (SQLite + exercises.json)
import os, json, sqlite3
from datetime import datetime, date, time, timedelta
from pathlib import Path
from collections import Counter

import pandas as pd
import streamlit as st

if "nav" not in st.session_state:
    st.session_state["nav"] = "📋"   # 기본 화면을 📋으로

st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")

DATA_DIR = Path(".")
DB_FILE  = DATA_DIR / "pilates.db"
EX_JSON  = DATA_DIR / "exercises.json"

# 🍒 PIN (수입 탭 잠금)
CHERRY_PIN = st.secrets.get("CHERRY_PW", "2974")

SITES = ["플로우", "리유", "방문"]

# ---------------- DB 연결/스키마 ----------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 멤버
cur.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    memo TEXT DEFAULT '',
    visit_net INTEGER DEFAULT 0,      -- 방문 실수령(개인용)
    register_date TEXT,               -- 등록일자 YYYY-MM-DD
    total_registered INTEGER DEFAULT 0,
    remaining_count INTEGER DEFAULT 0
)
""")

# 재등록 로그
cur.execute("""
CREATE TABLE IF NOT EXISTS member_recharges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    add_count INTEGER NOT NULL,
    recharge_date TEXT NOT NULL,      -- YYYY-MM-DD
    FOREIGN KEY(member_id) REFERENCES members(id)
)
""")

# 세션
cur.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER,                -- 개인일 때 멤버ID, 그룹이면 NULL
    member_name TEXT,                 -- 표시용 스냅샷
    stype TEXT DEFAULT '개인',        -- '개인' / '그룹'
    headcount INTEGER DEFAULT 1,      -- 그룹 인원
    site TEXT DEFAULT '리유',         -- 지점: 플로우/리유/방문
    sdate TEXT,                       -- YYYY-MM-DD
    stime TEXT,                       -- HH:MM
    equipment TEXT,
    level TEXT,                       -- Basic/Intermediate/Advanced/... (그룹도 보관)
    exercises_json TEXT,              -- 개인 세션의 동작들 ["Teaser",...], 그룹은 빈 리스트
    notes TEXT,                       -- 특이사항
    homework TEXT,                    -- 숙제(개인만)
    status TEXT DEFAULT '예약',       -- 예약/취소
    pay_gross REAL DEFAULT 0,         -- 총액
    pay_net REAL DEFAULT 0,           -- 실수령
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(member_id) REFERENCES members(id)
)
""")
conn.commit()

# 누락 컬럼 보강(버전 업 시 안전)
def ensure_columns():
    cur.execute("PRAGMA table_info(members)")
    mcols = {r["name"] for r in cur.fetchall()}
    if "visit_net" not in mcols:
        cur.execute("ALTER TABLE members ADD COLUMN visit_net INTEGER DEFAULT 0")
    if "register_date" not in mcols:
        cur.execute("ALTER TABLE members ADD COLUMN register_date TEXT")
    if "total_registered" not in mcols:
        cur.execute("ALTER TABLE members ADD COLUMN total_registered INTEGER DEFAULT 0")
    if "remaining_count" not in mcols:
        cur.execute("ALTER TABLE members ADD COLUMN remaining_count INTEGER DEFAULT 0")

    cur.execute("PRAGMA table_info(sessions)")
    scols = {r["name"] for r in cur.fetchall()}
    add_sql = []
    for col, sql in {
        "level": "ALTER TABLE sessions ADD COLUMN level TEXT",
        "site": "ALTER TABLE sessions ADD COLUMN site TEXT DEFAULT '리유'",
        "pay_gross": "ALTER TABLE sessions ADD COLUMN pay_gross REAL DEFAULT 0",
        "pay_net": "ALTER TABLE sessions ADD COLUMN pay_net REAL DEFAULT 0",
        "stype": "ALTER TABLE sessions ADD COLUMN stype TEXT DEFAULT '개인'",
        "headcount": "ALTER TABLE sessions ADD COLUMN headcount INTEGER DEFAULT 1",
        "member_name": "ALTER TABLE sessions ADD COLUMN member_name TEXT"
    }.items():
        if col not in scols:
            add_sql.append(sql)
    for s in add_sql:
        cur.execute(s)
    if add_sql:
        conn.commit()

ensure_columns()

# ---------------- exercises.json ----------------
if not EX_JSON.exists():
    base = {
        "Mat": {"Basic": [], "Intermediate": [], "Advanced": []},
        "Reformer": {"Basic": [], "Intermediate": [], "Advanced": []},
        "Cadillac": {"All": []},
        "Wunda chair": {"All": []},
        "Spine corrector / Barrel": {"All": []},
        "Electric chair": {"All": []},
        "Pedi-pull": {"All": []},
        "기타": {"All": []}
    }
    EX_JSON.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")

def load_exercises_dict() -> dict:
    try:
        return json.loads(EX_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}
def save_exercises_dict(d: dict):
    EX_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------- 유틸 ----------------
def norm_phone(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())

def calc_pay(site: str, stype: str, headcount: int, visit_net_personal: int) -> tuple[float, float]:
    """
    플로우: 회당 35,000원, 3.3% 공제
    리유: 개인 30,000 / 그룹(3명 40,000 / 2명(듀엣) 35,000 / 1명 25,000)
    방문: 개인은 멤버의 visit_net 사용 (gross=net=visit_net), 그룹 방문은 0 처리
    """
    if site == "플로우":
        gross = 35000.0
        net = round(gross * 0.967)  # 3.3% 공제
        return gross, float(net)
    if site == "리유":
        if stype == "개인":
            return 30000.0, 30000.0
        if headcount == 3:
            return 40000.0, 40000.0
        if headcount == 2:  # 듀엣
            return 35000.0, 35000.0
        return 25000.0, 25000.0  # 1명
    # 방문
    if stype == "개인":
        v = float(max(0, int(visit_net_personal or 0)))
        return v, v
    else:
        return 0.0, 0.0

def info(msg): st.info(msg)
def warn(msg): st.warning(msg)
def ok(msg): st.success(msg)

# ---------------- 사이드바 네비 (이모지만) ----------------
if "nav" not in st.session_state:
    st.session_state["nav"] = "📅"

nav_options = ["📅","📝","🧑‍🤝‍🧑","🍒"]
nav = st.sidebar.radio("📅", nav_options, index=nav_options.index(st.session_state["nav"]))
st.session_state["nav"] = nav

# ======================= 🧑‍🤝‍🧑 멤버 =======================
if nav == "🧑‍🤝‍🧑":
    st.title("🧑‍🤝‍🧑 멤버 관리")

    tabA, tabB, tabC = st.tabs(["➕ 등록/수정/삭제", "📋 멤버 목록", "📈 개인 동작 통계"])

    # ---- A: 등록/수정/삭제 ----
    with tabA:
        mode = st.radio("모드", ["신규 등록", "수정/삭제", "재등록 기록"], horizontal=True)

        if mode == "신규 등록":
            name = st.text_input("이름")
            phone = st.text_input("연락처 (예: 010-0000-0000)")
            visit_net = st.number_input("방문 실수령(원, 개인용)", min_value=0, max_value=1_000_000, value=0, step=1000)
            register_date = st.date_input("등록일자", value=date.today())
            memo = st.text_input("메모(선택)")
            init_total = st.number_input("초기 등록 횟수(패키지)", min_value=0, max_value=999, value=0, step=1)

            # 실시간 중복 경고(전화번호)
            if phone.strip():
                pnorm = norm_phone(콜)
                cur.execute("""
                    SELECT name FROM members
                    WHERE REPLACE(REPLACE(REPLACE(phone,'-',''),' ',''),'.','') = ?
                """, (pnorm,))
                dup = cur.fetchone()
                if dup:
                    warn(f"이미 등록된 번호예요 → {dup['name']}")

            if st.button("저장", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                elif not phone.strip():
                    st.error("연락처를 입력하세요.")
                else:
                    try:
                        cur.execute("""
                            INSERT INTO members(name, phone, memo, visit_net, register_date, total_registered, remaining_count)
                            VALUES (?,?,?,?,?,?,?)
                        """, (name.strip(), phone.strip(), memo.strip(), int(visit_net),
                              register_date.isoformat(), int(init_total), int(init_total)))
                        conn.commit()
                        ok(f"등록 완료: {name}")
                    except sqlite3.IntegrityError:
                        st.error("이미 등록된 전화번호입니다.")

        elif mode == "수정/삭제":
            cur.execute("SELECT id, name, phone, memo, visit_net, register_date, total_registered, remaining_count FROM members ORDER BY name")
            mrows = cur.fetchall()
            if not mrows:
                info("멤버가 없습니다. 먼저 등록하세요.")
            else:
                name_map = {f"{r['name']} ({r['phone']})": r for r in mrows}
                choice = st.selectbox("대상 선택", list(name_map.keys()))
                row = name_map[choice]

                new_name  = st.text_input("이름", row["name"])
                new_phone = st.text_input("연락처", row["phone"])
                new_memo  = st.text_input("메모(선택)", row["memo"])
                new_visit = st.number_input("방문 실수령(원, 개인용)", min_value=0, max_value=1_000_000, value=int(row["visit_net"] or 0), step=1000)
                reg_date  = st.date_input("등록일자", value=pd.to_datetime(row["register_date"]).date() if row["register_date"] else date.today())
                total_reg = st.number_input("총 등록 횟수", min_value=0, max_value=9999, value=int(row["total_registered"] or 0))
                remain    = st.number_input("남은 횟수", min_value=0, max_value=9999, value=int(row["remaining_count"] or 0))

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💾 수정", use_container_width=True):
                        # 본인 제외 중복 검사
                        pnorm = norm_phone(new_phone)
                        cur.execute("""
                            SELECT id, name FROM members
                            WHERE id != ? AND REPLACE(REPLACE(REPLACE(phone,'-',''),' ',''),'.','') = ?
                        """, (row["id"], pnorm))
                        other = cur.fetchone()
                        if other:
                            st.error(f"이미 사용 중인 번호입니다. (소유자: {other['name']})")
                        else:
                            cur.execute("""
                                UPDATE members
                                SET name=?, phone=?, memo=?, visit_net=?, register_date=?, total_registered=?, remaining_count=?
                                WHERE id=?
                            """, (new_name.strip(), new_phone.strip(), new_memo.strip(), int(new_visit),
                                  reg_date.isoformat(), int(total_reg), int(remain), row["id"]))
                            conn.commit()
                            ok("수정 완료")
                with c2:
                    if st.button("🗑 삭제", use_container_width=True):
                        cur.execute("DELETE FROM members WHERE id=?", (row["id"],))
                        cur.execute("DELETE FROM member_recharges WHERE member_id=?", (row["id"],))
                        conn.commit()
                        warn(f"삭제 완료: {row['name']}")

        else:  # 재등록 기록
            cur.execute("SELECT id, name, phone, remaining_count, total_registered FROM members ORDER BY name")
            mrows = cur.fetchall()
            if not mrows:
                info("멤버가 없습니다.")
            else:
                msel = st.selectbox("멤버 선택", [f"{r['name']} ({r['phone']})" for r in mrows])
                mrow = {f"{r['name']} ({r['phone']})": r for r in mrows}[msel]
                add_cnt = st.number_input("재등록 추가 횟수", min_value=1, max_value=999, value=1, step=1)
                rdate   = st.date_input("재등록일자", value=date.today())

                if st.button("➕ 재등록 반영", use_container_width=True):
                    cur.execute("INSERT INTO member_recharges(member_id, add_count, recharge_date) VALUES (?,?,?)",
                                (mrow["id"], int(add_cnt), rdate.isoformat()))
                    cur.execute("""
                        UPDATE members
                        SET total_registered = total_registered + ?,
                            remaining_count = remaining_count + ?
                        WHERE id=?
                    """, (int(add_cnt), int(add_cnt), mrow["id"]))
                    conn.commit()
                    ok("재등록이 반영되었습니다.")

                st.divider()
                st.subheader("재등록 내역")
                cur.execute("""
                    SELECT add_count, recharge_date
                    FROM member_recharges
                    WHERE member_id=?
                    ORDER BY recharge_date DESC, id DESC
                """, (mrow["id"],))
                rows = cur.fetchall()
                df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame(columns=["add_count","recharge_date"])
                df.rename(columns={"add_count":"추가횟수","recharge_date":"재등록일자"}, inplace=True)
                st.dataframe(df, use_container_width=True, hide_index=True)

    # ---- B: 멤버 목록 (등록/재등록 정보 표시) ----
    with tabB:
        cur.execute("""
            SELECT m.id, m.name, m.phone, m.register_date, m.total_registered, m.remaining_count, m.visit_net, m.memo,
                   COALESCE(SUM(r.add_count), 0) AS recharge_sum,
                   (SELECT MAX(recharge_date) FROM member_recharges rr WHERE rr.member_id = m.id) AS last_recharge
            FROM members m
            LEFT JOIN member_recharges r ON r.member_id = m.id
            GROUP BY m.id
            ORDER BY m.name
        """)
        rows = cur.fetchall()
        if not rows:
            info("표시할 멤버가 없습니다.")
        else:
            data = []
            for r in rows:
                data.append({
                    "이름": r["name"],
                    "연락처": r["phone"],
                    "등록일자": r["register_date"] or "",
                    "총등록": int(r["total_registered"] or 0),
                    "남은횟수": int(r["remaining_count"] or 0),
                    "재등록 여부": "예" if (r["recharge_sum"] or 0) > 0 else "아니오",
                    "재등록 추가횟수": int(r["recharge_sum"] or 0),
                    "최근 재등록 일자": r["last_recharge"] or "",
                    "방문실수령(개인)": int(r["visit_net"] or 0),
                    "메모": r["memo"] or ""
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    # ---- C: 개인 동작 통계 (월간 Top5 + 6개월 추이) ----
    with tabC:
        st.caption("선택 멤버의 **월간 Top5 동작**과 **최근 6개월 추이**(개인 세션만, 취소 제외)")
        cur.execute("SELECT id, name, phone FROM members ORDER BY name")
        mrows = cur.fetchall()
        if not mrows:
            info("멤버가 없습니다.")
        else:
            mmap = {f"{r['name']} ({r['phone']})": r["id"] for r in mrows}
            mlabel = st.selectbox("멤버 선택", list(mmap.keys()))
            mid = mmap[mlabel]

            base_month = st.date_input("기준 월", value=date.today().replace(day=1))
            ym = f"{base_month.year}-{base_month.month:02d}"

            cur.execute("""
                SELECT exercises_json
                FROM sessions
                WHERE member_id=? AND stype='개인' AND substr(sdate,1,7)=? AND status!='취소'
            """, (mid, ym))
            rows = cur.fetchall()
            cnt = Counter()
            for r in rows:
                try:
                    arr = json.loads(r["exercises_json"]) if r["exercises_json"] else []
                except Exception:
                    arr = []
                cnt.update(arr)

            if not cnt:
                info("이 달에는 개인 세션 동작 데이터가 없습니다.")
            else:
                top5 = cnt.most_common(5)
                df_top = pd.DataFrame(top5, columns=["동작","횟수"])
                st.subheader(f"📊 {ym} Top5 동작")
                st.bar_chart(df_top.set_index("동작"))

                # 최근 6개월 추이
                months = []
                cur_dt = base_month.replace(day=1)
                for _ in range(6):
                    months.append(f"{cur_dt.year}-{cur_dt.month:02d}")
                    if cur_dt.month == 1:
                        cur_dt = cur_dt.replace(year=cur_dt.year-1, month=12)
                    else:
                        cur_dt = cur_dt.replace(month=cur_dt.month-1)
                months = months[::-1]
                top_moves = [m for m,_ in top5]
                series = {mv: [] for mv in top_moves}
                for ymv in months:
                    cur.execute("""
                        SELECT exercises_json FROM sessions
                        WHERE member_id=? AND stype='개인' AND substr(sdate,1,7)=? AND status!='취소'
                    """, (mid, ymv))
                    rows_m = cur.fetchall()
                    c = Counter()
                    for r in rows_m:
                        try:
                            arr = json.loads(r["exercises_json"]) if r["exercises_json"] else []
                        except Exception:
                            arr = []
                        c.update(arr)
                    for mv in top_moves:
                        series[mv].append(c.get(mv, 0))
                df_line = pd.DataFrame(series, index=months)
                st.subheader("📈 Top5 동작 최근 6개월 추이")
                st.line_chart(df_line)

# ======================= 📝 세션 (그룹 간소화 + 방문 실수령 제거) =======================
elif nav == "📝":
    st.title("📝 세션 기록")

    # 구분
    stype = st.radio("세션 구분", ["개인","그룹"], horizontal=True)

    # 멤버 목록
    cur.execute("SELECT id, name, phone, visit_net FROM members ORDER BY name")
    mrows = cur.fetchall()
    members_map = {f"{r['name']} ({r['phone']})": r["id"] for r in mrows}
    visit_map   = {r["id"]: int(r["visit_net"] or 0) for r in mrows}

    c1, c2, c3 = st.columns(3)
    if stype == "개인":
        with c1:
            sel_label = st.selectbox("회원 선택(개인)", list(members_map.keys()) if mrows else ["등록된 멤버 없음"])
            member_id = members_map.get(sel_label)
        with c2:
            sdate = st.date_input("날짜", value=date.today())
        with c3:
            stime = st.time_input("시간", value=time(10, 0))
    else:  # 그룹
        with c1:
            headcount = st.number_input("인원", min_value=1, max_value=20, value=2, step=1)
        with c2:
            sdate = st.date_input("날짜", value=date.today())
        with c3:
            stime = st.time_input("시간", value=time(10, 0))
        member_id = None
        sel_label = "(그룹)"

    # 지점 + 기구/레벨
    EX = load_exercises_dict()
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        site = st.selectbox("지점", SITES, index=1)  # 기본 리유
    with sc2:
        equipment = st.selectbox("기구", list(EX.keys()))
    levels = EX[equipment] if isinstance(EX[equipment], dict) else {"All": EX[equipment]}
    with sc3:
        level_key = st.selectbox("레벨", list(levels.keys()))

    # 개인: 동작/숙제/특이사항, 그룹: 특이사항만
    if stype == "개인":
        options = levels.get(level_key, [])
        picked = st.multiselect("동작 선택(복수)", options)
        extra_txt = st.text_input("직접 추가 동작(쉼표로 구분)", placeholder="예: Mermaid, Side bends")
        new_list = [x.strip() for x in extra_txt.split(",") if x.strip()] if extra_txt.strip() else []
        notes = st.text_area("특이사항", placeholder="예: 허리 불편, 난이도 조절")
        homework = st.text_area("숙제", placeholder="예: 힙 스트레칭 매일 10분")
    else:
        picked, new_list, homework = [], [], ""
        notes = st.text_area("특이사항", placeholder="예: 수업 메모 등")

    cancel = st.checkbox("취소로 저장")

    if st.button("✅ 세션 저장", use_container_width=True):
        # exercises 합치기(개인만)
        full_moves = picked[:]
        for nm in new_list:
            if nm not in full_moves:
                full_moves.append(nm)

        # exercises.json에 '기타' 누적(개인만)
        if stype == "개인" and new_list:
            if "기타" not in EX:
                EX["기타"] = {"All": []}
            EX["기타"].setdefault("All", [])
            for nm in new_list:
                if nm not in EX["기타"]["All"]:
                    EX["기타"]["All"].append(nm)
            save_exercises_dict(EX)

        # 멤버 이름/방문 실수령
        if stype == "개인":
            if member_id is None:
                st.error("개인 세션은 회원을 선택하세요.")
                st.stop()
            cur.execute("SELECT name, visit_net FROM members WHERE id=?", (member_id,))
            m = cur.fetchone()
            member_name = m["name"]
            visit_net = int(m["visit_net"] or 0)
        else:
            member_name = "그룹"
            visit_net = 0

        # 금액 계산 (세션 화면엔 방문 실수령 입력 없음)
        gross, net = calc_pay(site, stype, int(headcount if stype=="그룹" else 1), visit_net)

        # 저장
        cur.execute("""
            INSERT INTO sessions (member_id, member_name, stype, headcount, site,
                                  sdate, stime, equipment, level, exercises_json,
                                  notes, homework, status, pay_gross, pay_net)
            VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?)
        """, (
            member_id, member_name, stype, int(headcount if stype=="그룹" else 1), site,
            sdate.isoformat(), f"{stime.hour:02d}:{stime.minute:02d}", equipment, level_key,
            json.dumps(full_moves, ensure_ascii=False), notes.strip(), homework.strip(),
            "취소" if cancel else "예약", float(gross), float(net)
        ))
        conn.commit()

        # 개인 + 예약이면 남은횟수 차감
        if stype == "개인" and not cancel:
            cur.execute("UPDATE members SET remaining_count = MAX(remaining_count-1,0) WHERE id=?", (member_id,))
            conn.commit()

        ok("세션이 저장되었습니다.")

    st.divider()
    st.subheader("최근 세션")
    cur.execute("""
        SELECT id, member_name, stype, headcount, site, sdate, stime, equipment, level, exercises_json, status
        FROM sessions
        ORDER BY sdate DESC, stime DESC, id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    if not rows:
        info("세션 데이터가 없습니다.")
    else:
        for r in rows:
            tag_txt = "[개인]" if r["stype"] == "개인" else f"[그룹 {r['headcount']}명]"
            title = f"**{r['sdate']} {r['stime']} · {tag_txt} {r['member_name']}** · *{r['equipment']} · {r['level']}* · {r['site']}"
            if r["status"] == "취소":
                title = f"<s>{title}</s>"
            st.markdown(title, unsafe_allow_html=True)
            if r["stype"] == "개인":
                moves = ", ".join(json.loads(r["exercises_json"])) if r["exercises_json"] else "-"
                st.caption(f"동작: {moves}")
            st.caption(f"상태: {r['status']}")

# ======================= 📅 스케줄 (지난 수업에 무엇을 했는지 보기) =======================
elif nav == "📅":
    st.title("📅 스케줄 (일/주/월)")
    base = st.date_input("기준 날짜", value=date.today())
    mode = st.segmented_control("보기", options=["일","주","월"], default="주")

    start_dt = datetime.combine(base, time.min)
    if mode == "일":
        end_dt = start_dt + timedelta(days=1)
    elif mode == "주":
        start_dt = start_dt - timedelta(days=start_dt.weekday())  # 월요일
        end_dt = start_dt + timedelta(days=7)
    else:
        first = start_dt.replace(day=1)
        if first.month == 12:
            next_month = first.replace(year=first.year+1, month=1)
        else:
            next_month = first.replace(month=first.month+1)
        start_dt, end_dt = first, next_month

    cur.execute("""
        SELECT id, member_id, member_name, stype, headcount, site, sdate, stime, equipment, level, exercises_json, notes, homework, status
        FROM sessions
        WHERE sdate >= ? AND sdate < ?
        ORDER BY sdate, stime, id
    """, (start_dt.date().isoformat(), end_dt.date().isoformat()))
    rows = cur.fetchall()

    if not rows:
        info("해당 기간에 일정이 없습니다.")
    else:
        for r in rows:
            tag_txt = "[개인]" if r["stype"] == "개인" else f"[그룹 {r['headcount']}명]"
            title = f"{r['sdate']} {r['stime']} · {tag_txt} **{r['member_name']}** · *{r['equipment']} · {r['level']}* · {r['site']}"
            if r["status"] == "취소":
                title = f"<s>{title}</s>"
            st.markdown(title, unsafe_allow_html=True)

            # 현재 세션 상세
            if r["stype"] == "개인":
                moves = ", ".join(json.loads(r["exercises_json"])) if r["exercises_json"] else "-"
                st.caption(f"이번 세션 동작: {moves}")
            if r["notes"]:
                st.caption(f"특이사항: {r['notes']}")
            if r["homework"] and r["stype"] == "개인":
                st.caption(f"숙제: {r['homework']}")
            st.caption(f"상태: {r['status']}")

            # 🔎 직전 세션 요약 (지난 수업에 무엇을 했는지)
            if r["stype"] == "개인" and r["member_id"]:
                cur.execute("""
                    SELECT sdate, stime, exercises_json, notes, homework
                    FROM sessions
                    WHERE member_id=? AND status!='취소'
                      AND (sdate < ? OR (sdate = ? AND stime < ?))
                    ORDER BY sdate DESC, stime DESC, id DESC
                    LIMIT 1
                """, (r["member_id"], r["sdate"], r["sdate"], r["stime"]))
                prev = cur.fetchone()
                with st.expander("📜 직전 세션 보기", expanded=False):
                    if not prev:
                        st.write("직전 세션이 없습니다.")
                    else:
                        prev_moves = ", ".join(json.loads(prev["exercises_json"])) if prev["exercises_json"] else "-"
                        st.write(f"**{prev['sdate']} {prev['stime']}**")
                        st.write(f"- 동작: {prev_moves}")
                        if prev["notes"]:
                            st.write(f"- 특이사항: {prev['notes']}")
                        if prev["homework"]:
                            st.write(f"- 숙제: {prev['homework']}")

            # 빠른 상태 변경
            c1, c2, c3 = st.columns(3)
            with c1:
                if r["status"] != "취소" and st.button("❌ 취소", key=f"cancel_{r['id']}"):
                    cur.execute("UPDATE sessions SET status='취소' WHERE id=?", (r["id"],))
                    conn.commit()
                    st.experimental_rerun()
            with c2:
                if r["status"] == "취소" and st.button("↩️ 복원", key=f"restore_{r['id']}"):
                    cur.execute("UPDATE sessions SET status='예약' WHERE id=?", (r["id"],))
                    conn.commit()
                    st.experimental_rerun()
            with c3:
                if st.button("🗑 완전 삭제", key=f"delete_{r['id']}"):
                    cur.execute("DELETE FROM sessions WHERE id=?", (r["id"],))
                    conn.commit()
                    st.experimental_rerun()

# ======================= 🍒 수입 (탭/제목 모두 이모지만) =======================
elif nav == "🍒":
    st.title("🍒")  # 제목도 글자 없이 이모지만 표시
    if "cherry_ok" not in st.session_state or not st.session_state["cherry_ok"]:
        pin = st.text_input("PIN 입력", type="password", placeholder="****")
        if st.button("열기"):
            if pin == CHERRY_PIN:
                st.session_state["cherry_ok"] = True
                st.experimental_rerun()
            else:
                st.error("PIN이 올바르지 않습니다.")
    else:
        # 월/연 합계 (취소 제외). 화면엔 금액 수치 표시는 하되, 탭/제목에는 글자 없음 (요청사항 반영)
        cur.execute("""
            SELECT substr(sdate,1,7) AS ym, SUM(pay_net) AS net_sum
            FROM sessions
            WHERE status != '취소'
            GROUP BY ym
            ORDER BY ym DESC
        """)
        month_rows = cur.fetchall()

        cur.execute("""
            SELECT substr(sdate,1,4) AS y, SUM(pay_net) AS net_sum
            FROM sessions
            WHERE status != '취소'
            GROUP BY y
            ORDER BY y DESC
        """)
        year_rows = cur.fetchall()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🍒 월별**")
            if month_rows:
                st.dataframe(pd.DataFrame([{"월": r["ym"], "실수령 합계": int(r["net_sum"] or 0)} for r in month_rows]),
                             use_container_width=True, hide_index=True)
            else:
                st.info("데이터 없음")
        with col2:
            st.markdown("**🍒 연도별**")
            if year_rows:
                st.dataframe(pd.DataFrame([{"연도": r["y"], "실수령 합계": int(r["net_sum"] or 0)} for r in year_rows]),
                             use_container_width=True, hide_index=True)
            else:
                st.info("데이터 없음")

        st.divider()
        st.markdown("**🍒 상세(개별 세션)**")
        cur.execute("""
            SELECT sdate, stime, site, stype, headcount, member_name, pay_gross, pay_net, status
            FROM sessions
            ORDER BY sdate DESC, stime DESC, id DESC
            LIMIT 200
        """)
        rows = cur.fetchall()
        if not rows:
            st.info("상세 데이터가 없습니다.")
        else:
            data = []
            for r in rows:
                tag = "개인" if r["stype"] == "개인" else f"그룹 {r['headcount']}명"
                who = r["member_name"]
                data.append({
                    "날짜": f"{r['sdate']} {r['stime']}",
                    "지점": r["site"],
                    "구분": tag,
                    "이름": who,
                    "총액": int(r["pay_gross"] or 0),
                    "실수령": int(r["pay_net"] or 0),
                    "상태": r["status"]
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


