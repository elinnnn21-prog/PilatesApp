# app.py — Pilates Manager (SQLite + exercises.json + 개인/그룹 구분)
import os, json, sqlite3
from datetime import datetime, date, time, timedelta
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")

DATA_DIR = Path(".")
DB_FILE = DATA_DIR / "pilates.db"
EX_JSON = DATA_DIR / "exercises.json"

def norm_phone(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())

# ---------------- DB 준비 ----------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    memo TEXT DEFAULT ''
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER,          -- 개인일 때 멤버ID, 그룹이면 NULL
    member_name TEXT,           -- 표시용 스냅샷(그룹/비회원 시 이름)
    stype TEXT DEFAULT '개인',  -- '개인' / '그룹'
    headcount INTEGER DEFAULT 1,
    group_names TEXT DEFAULT '',-- 그룹일 때 참석자 이름들(콤마구분)
    sdate TEXT,                 -- YYYY-MM-DD
    stime TEXT,                 -- HH:MM
    equipment TEXT,
    exercises_json TEXT,        -- ["Teaser","Elephant",...]
    notes TEXT,                 -- 특이사항
    homework TEXT,              -- 숙제
    status TEXT DEFAULT '예약',  -- 예약/취소
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(member_id) REFERENCES members(id)
)
""")
conn.commit()

# 기존 DB에 누락 컬럼이 있으면 추가
def ensure_session_columns():
    cur.execute("PRAGMA table_info(sessions)")
    cols = {r["name"] for r in cur.fetchall()}
    to_add = []
    if "stype" not in cols:
        to_add.append("ALTER TABLE sessions ADD COLUMN stype TEXT DEFAULT '개인'")
    if "headcount" not in cols:
        to_add.append("ALTER TABLE sessions ADD COLUMN headcount INTEGER DEFAULT 1")
    if "group_names" not in cols:
        to_add.append("ALTER TABLE sessions ADD COLUMN group_names TEXT DEFAULT ''")
    if "member_name" not in cols:
        to_add.append("ALTER TABLE sessions ADD COLUMN member_name TEXT")
    for sql in to_add:
        cur.execute(sql)
    if to_add:
        conn.commit()

ensure_session_columns()

# -------------- exercises.json --------------
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

EX = load_exercises_dict()

# -------------- 사이드바 --------------
if "nav" not in st.session_state:
    st.session_state["nav"] = "📅 스케줄"
nav = st.sidebar.radio("탭", ["📅 스케줄","📝 세션","🧑‍🤝‍🧑 멤버"],
                       index=["📅 스케줄","📝 세션","🧑‍🤝‍🧑 멤버"].index(st.session_state["nav"]))
st.session_state["nav"] = nav

# ================= 멤버 =================
if nav == "🧑‍🤝‍🧑 멤버":
    st.title("🧑‍🤝‍🧑 멤버 관리")
    tabA, tabB = st.tabs(["➕ 등록/수정/삭제", "📋 멤버 목록"])
    with tabA:
        mode = st.radio("모드", ["신규 등록", "수정/삭제"], horizontal=True)

        if mode == "신규 등록":
            name = st.text_input("이름")
            phone = st.text_input("연락처 (예: 010-0000-0000)")
            memo = st.text_input("메모(선택)")

            if phone.strip():
                pnorm = norm_phone(콜)
                cur.execute("SELECT name FROM members WHERE REPLACE(REPLACE(REPLACE(phone,'-',''),' ',''),'.','') = ?", (pnorm,))
                dup = cur.fetchone()
                if dup:
                    st.warning(f"⚠️ 이미 등록된 번호예요 → {dup['name']}")

            if st.button("저장", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력하세요.")
                elif not phone.strip():
                    st.error("연락처를 입력하세요.")
                else:
                    try:
                        cur.execute("INSERT INTO members(name, phone, memo) VALUES (?,?,?)",
                                    (name.strip(), phone.strip(), memo.strip()))
                        conn.commit()
                        st.success(f"등록 완료: {name}")
                    except sqlite3.IntegrityError:
                        st.error("이미 등록된 전화번호입니다.")

        else:
            cur.execute("SELECT id, name, phone, memo FROM members ORDER BY name")
            mrows = cur.fetchall()
            if not mrows:
                st.info("멤버가 없습니다. 먼저 등록하세요.")
            else:
                name_map = {f"{r['name']} ({r['phone']})": r for r in mrows}
                choice = st.selectbox("대상 선택", list(name_map.keys()))
                row = name_map[choice]

                new_name = st.text_input("이름", row["name"])
                new_phone = st.text_input("연락처", row["phone"])
                new_memo = st.text_input("메모(선택)", row["memo"])

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💾 수정", use_container_width=True):
                        pnorm = norm_phone(new_phone)
                        cur.execute("""
                            SELECT id, name FROM members
                            WHERE id != ? AND REPLACE(REPLACE(REPLACE(phone,'-',''),' ',''),'.','') = ?
                        """, (row["id"], pnorm))
                        other = cur.fetchone()
                        if other:
                            st.error(f"이미 사용 중인 번호입니다. (소유자: {other['name']})")
                        else:
                            cur.execute("UPDATE members SET name=?, phone=?, memo=? WHERE id=?",
                                        (new_name.strip(), new_phone.strip(), new_memo.strip(), row["id"]))
                            conn.commit()
                            st.success("수정 완료")
                with c2:
                    if st.button("🗑 삭제", use_container_width=True):
                        cur.execute("DELETE FROM members WHERE id=?", (row["id"],))
                        conn.commit()
                        st.warning(f"삭제 완료: {row['name']}")

    with tabB:
        cur.execute("SELECT id, name, phone, memo FROM members ORDER BY name")
        rows = cur.fetchall()
        if not rows:
            st.info("표시할 멤버가 없습니다.")
        else:
            import pandas as pd
            st.dataframe(pd.DataFrame([dict(r) for r in rows]), use_container_width=True, hide_index=True)

# ================= 세션 =================
elif nav == "📝 세션":
    st.title("📝 세션 기록")

    # 구분
    stype = st.radio("세션 구분", ["개인","그룹"], horizontal=True)

    # 멤버 목록
    cur.execute("SELECT id, name, phone FROM members ORDER BY name")
    mrows = cur.fetchall()
    members_map = {"(선택 안 함)": None}
    for r in mrows:
        members_map[f"{r['name']} ({r['phone']})"] = r["id"]

    c1, c2, c3 = st.columns(3)
    with c1:
        if stype == "개인":
            sel_member = st.selectbox("회원 선택(개인)", list(members_map.keys())[1:] if mrows else ["등록된 멤버 없음"])
            member_id = members_map.get(sel_member, None)
        else:
            sel_member = "(그룹)"
            member_id = None
    with c2:
        sdate = st.date_input("날짜", value=date.today())
    with c3:
        stime = st.time_input("시간", value=time(10, 0))

    # 그룹 전용
    if stype == "그룹":
        gc1, gc2 = st.columns(2)
        with gc1:
            headcount = st.number_input("인원", min_value=1, max_value=20, value=2, step=1)
        with gc2:
            group_names = st.text_input("참여자 이름들 (콤마로 구분)", placeholder="예: 김A, 이B, 박C")
    else:
        headcount = 1
        group_names = ""

    # 기구 → 레벨/동작
    equip = st.selectbox("기구 선택", list(EX.keys()))
    levels = EX[equip] if isinstance(EX[equip], dict) else {"All": EX[equip]}
    level_key = st.selectbox("레벨/그룹", list(levels.keys()))
    options = levels.get(level_key, [])

    picked = st.multiselect("동작 선택(복수)", options, help="선택한 기구/레벨의 동작만 표시됩니다.")
    extra_txt = st.text_input("직접 추가 동작(쉼표로 구분)", placeholder="예: Mermaid, Side bends")
    new_list = [x.strip() for x in extra_txt.split(",") if x.strip()] if extra_txt.strip() else []

    notes = st.text_area("특이사항", placeholder="예: 허리 불편, 난이도 조절")
    homework = st.text_area("숙제", placeholder="예: 힙 스트레칭 매일 10분")

    if st.button("✅ 세션 저장", use_container_width=True):
        # exercises 합치기
        full_moves = picked[:]
        for nm in new_list:
            if nm not in full_moves:
                full_moves.append(nm)

        # exercises.json에 '기타'로 누적
        if new_list:
            if "기타" not in EX:
                EX["기타"] = {"All": []}
            EX["기타"].setdefault("All", [])
            for nm in new_list:
                if nm not in EX["기타"]["All"]:
                    EX["기타"]["All"].append(nm)
            save_exercises_dict(EX)

        # 표시용 이름
        if stype == "개인":
            if member_id is None:
                st.error("개인 세션은 회원을 선택하세요.")
                st.stop()
            cur.execute("SELECT name FROM members WHERE id=?", (member_id,))
            member_name = cur.fetchone()["name"]
        else:
            member_name = "그룹"

        cur.execute("""
            INSERT INTO sessions (member_id, member_name, stype, headcount, group_names,
                                  sdate, stime, equipment, exercises_json, notes, homework, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '예약')
        """, (
            member_id, member_name, stype, int(headcount), group_names.strip(),
            sdate.isoformat(), f"{stime.hour:02d}:{stime.minute:02d}", equip,
            json.dumps(full_moves, ensure_ascii=False), notes.strip(), homework.strip()
        ))
        conn.commit()
        st.success("세션이 저장되었습니다.")

    st.divider()
    st.subheader("최근 세션")
    cur.execute("""
        SELECT id, member_name, stype, headcount, group_names, sdate, stime, equipment, exercises_json, status
        FROM sessions
        ORDER BY sdate DESC, stime DESC, id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    if not rows:
        st.info("세션 데이터가 없습니다.")
    else:
        for r in rows:
            moves = ", ".join(json.loads(r["exercises_json"])) if r["exercises_json"] else "-"
            tag = "[개인]" if r["stype"] == "개인" else f"[그룹 {r['headcount']}명]"
            names = f" · ({r['group_names']})" if r["stype"] == "그룹" and r["group_names"] else ""
            status_txt = "❌ 취소" if r["status"] == "취소" else "✅ 예약"
            st.markdown(f"**{r['sdate']} {r['stime']} · {tag} {r['member_name']}{names}**  — *{r['equipment']}*")
            st.caption(f"동작: {moves} · {status_txt}")

# ================= 스케줄 =================
elif nav == "📅 스케줄":
    st.title("📅 스케줄")
    base = st.date_input("기준 날짜", value=date.today())
    mode = st.segmented_control("보기", options=["일","주","월"], default="주")

    start = datetime.combine(base, time.min)
    if mode == "일":
        end = start + timedelta(days=1)
    elif mode == "주":
        start = start - timedelta(days=start.weekday())  # 월
        end = start + timedelta(days=7)
    else:
        first = start.replace(day=1)
        next_month = (first.replace(year=first.year+1, month=1)
                      if first.month == 12 else first.replace(month=first.month+1))
        start, end = first, next_month

    cur.execute("""
        SELECT id, member_name, stype, headcount, group_names, sdate, stime, equipment, exercises_json, status
        FROM sessions
        WHERE sdate >= ? AND sdate < ?
        ORDER BY sdate, stime, id
    """, (start.date().isoformat(), end.date().isoformat()))
    rows = cur.fetchall()

    if not rows:
        st.info("해당 기간에 일정이 없습니다.")
    else:
        for r in rows:
            moves = ", ".join(json.loads(r["exercises_json"])) if r["exercises_json"] else "-"
            tag = "[개인]" if r["stype"] == "개인" else f"[그룹 {r['headcount']}명]"
            names = f" · ({r['group_names']})" if r["stype"] == "그룹" and r["group_names"] else ""
            title = f"{r['sdate']} {r['stime']} · {tag} **{r['member_name']}**{names} · *{r['equipment']}*"
            if r["status"] == "취소":
                title = f"<s>{title}</s>"
            st.markdown(title, unsafe_allow_html=True)
            st.caption(f"동작: {moves}")

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
