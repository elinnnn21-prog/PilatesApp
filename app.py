# app.py — Pilates Manager (SQLite + exercises.json)
import os, json, sqlite3
from datetime import datetime, date, time
from pathlib import Path

import streamlit as st

# ------------------------------
# 기본 설정
# ------------------------------
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")
DATA_DIR = Path(".")
DB_FILE = DATA_DIR / "pilates.db"
EX_JSON = DATA_DIR / "exercises.json"

# ------------------------------
# 유틸: 전화번호 숫자만 추출(중복검사용)
# ------------------------------
def norm_phone(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())

# ------------------------------
# DB 준비
# ------------------------------
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
    member_id INTEGER,
    member_name TEXT,           -- 그룹/비회원 기록 대비(스냅샷명)
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

# ------------------------------
# exercises.json 준비(없으면 기본 골격 생성)
# ------------------------------
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

# ------------------------------
# 사이드바 내비
# ------------------------------
if "nav" not in st.session_state:
    st.session_state["nav"] = "📅 스케줄"

nav = st.sidebar.radio("탭", ["📅 스케줄","📝 세션","🧑‍🤝‍🧑 멤버"], index=["📅 스케줄","📝 세션","🧑‍🤝‍🧑 멤버"].index(st.session_state["nav"]))
st.session_state["nav"] = nav

# ==============================
# 🧑‍🤝‍🧑 멤버 탭
# ==============================
if nav == "🧑‍🤝‍🧑 멤버":
    st.title("🧑‍🤝‍🧑 멤버 관리")

    tabA, tabB = st.tabs(["➕ 등록/수정/삭제", "📋 멤버 목록"])
    with tabA:
        mode = st.radio("모드", ["신규 등록", "수정/삭제"], horizontal=True)

        if mode == "신규 등록":
            name = st.text_input("이름")
            phone = st.text_input("연락처 (예: 010-0000-0000)")
            memo = st.text_input("메모(선택)")

            # 실시간 중복 경고
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
            # 수정/삭제
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
                            cur.execute("UPDATE members SET name=?, phone=?, memo=? WHERE id=?",
                                        (new_name.strip(), new_phone.strip(), new_memo.strip(), row["id"]))
                            conn.commit()
                            st.success("수정 완료")

                with c2:
                    if st.button("🗑 삭제", use_container_width=True):
                        # 관련 세션 남기고 싶으면 status만 '취소'로 바꾸는 선택지도 가능
                        cur.execute("DELETE FROM members WHERE id=?", (row["id"],))
                        conn.commit()
                        st.warning(f"삭제 완료: {row['name']}")

    with tabB:
        cur.execute("SELECT id, name, phone, memo FROM members ORDER BY name")
        df = [dict(r) for r in cur.fetchall()]
        if not df:
            st.info("표시할 멤버가 없습니다.")
        else:
            import pandas as pd
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)

# ==============================
# 📝 세션 탭
# ==============================
elif nav == "📝 세션":
    st.title("📝 세션 기록")

    # 멤버 목록
    cur.execute("SELECT id, name, phone FROM members ORDER BY name")
    mrows = cur.fetchall()
    members_map = {"(그룹/비회원)": None}
    for r in mrows:
        members_map[f"{r['name']} ({r['phone']})"] = r["id"]

    c1, c2, c3 = st.columns(3)
    with c1:
        sel_member = st.selectbox("회원 선택", list(members_map.keys()))
        member_id = members_map[sel_member]
    with c2:
        sdate = st.date_input("날짜", value=date.today())
    with c3:
        stime = st.time_input("시간", value=time(10, 0))

    # 기구 → 레벨/동작 필터
    equip = st.selectbox("기구 선택", list(EX.keys()))
    levels = EX[equip] if isinstance(EX[equip], dict) else {"All": EX[equip]}
    level_key = st.selectbox("레벨/그룹", list(levels.keys()))
    options = levels.get(level_key, [])

    picked = st.multiselect("동작 선택(복수)", options, help="선택한 기구/레벨의 동작만 표시됩니다.")
    extra_txt = st.text_input("직접 추가 동작(쉼표로 구분)", placeholder="예: Mermaid, Side bends")

    # 추가 동작을 DB로도 남기고, exercises.json에도 누적 저장(중복 방지)
    if extra_txt.strip():
        new_list = [x.strip() for x in extra_txt.split(",") if x.strip()]
    else:
        new_list = []

    notes = st.text_area("특이사항", placeholder="예: 허리 불편, 난이도 조절")
    homework = st.text_area("숙제", placeholder="예: 힙 스트레칭 매일 10분")

    if st.button("✅ 세션 저장", use_container_width=True):
        # exercises 합치기
        full_moves = picked[:]
        for nm in new_list:
            if nm not in full_moves:
                full_moves.append(nm)

        # exercises.json에 '기타'로 누적(선택 레벨 밑에 넣어도 됨)
        if new_list:
            # '기타' 섹션 보장
            if "기타" not in EX:
                EX["기타"] = {"All": []}
            if isinstance(EX["기타"], dict):
                EX["기타"].setdefault("All", [])
                for nm in new_list:
                    if nm not in EX["기타"]["All"]:
                        EX["기타"]["All"].append(nm)
            else:
                # 혹시 dict가 아닌 구조면 리스트로만 관리
                for nm in new_list:
                    if nm not in EX["기타"]:
                        EX["기타"].append(nm)
            save_exercises_dict(EX)

        # member_name 스냅샷(그룹/비회원 시 이름 입력받도록)
        if member_id is None:
            grp_name = st.text_input("그룹/비회원 세션 이름(표시용)", key="grp_name_for_save")
            # 즉시 저장 흐름이라 입력이 안 들어갈 수 있어 한 번 더 요청
            if not grp_name:
                grp_name = "그룹 세션"
            member_name = grp_name
        else:
            cur.execute("SELECT name FROM members WHERE id=?", (member_id,))
            member_name = cur.fetchone()["name"]

        cur.execute("""
            INSERT INTO sessions (member_id, member_name, sdate, stime, equipment, exercises_json, notes, homework, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '예약')
        """, (
            member_id,
            member_name,
            sdate.isoformat(),
            f"{stime.hour:02d}:{stime.minute:02d}",
            equip,
            json.dumps(full_moves, ensure_ascii=False),
            notes.strip(),
            homework.strip()
        ))
        conn.commit()
        st.success("세션이 저장되었습니다.")

    st.divider()
    st.subheader("최근 세션")
    cur.execute("""
        SELECT id, member_name, sdate, stime, equipment, exercises_json, status
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
            status_txt = "❌ 취소" if r["status"] == "취소" else "✅ 예약"
            st.markdown(f"**{r['sdate']} {r['stime']} · {r['member_name']}**  — *{r['equipment']}*  · 동작: {moves}  · {status_txt}")

# ==============================
# 📅 스케줄 탭 (취소 가능)
# ==============================
elif nav == "📅 스케줄":
    st.title("📅 스케줄")
    base = st.date_input("기준 날짜", value=date.today())
    mode = st.segmented_control("보기", options=["일","주","월"], default="주")

    # 기간 계산
    from datetime import timedelta
    start = datetime.combine(base, time.min)
    if mode == "일":
        end = start + timedelta(days=1)
    elif mode == "주":
        start = start - timedelta(days=start.weekday())  # 월
        end = start + timedelta(days=7)
    else:
        first = start.replace(day=1)
        if first.month == 12:
            next_month = first.replace(year=first.year+1, month=1)
        else:
            next_month = first.replace(month=first.month+1)
        start = first
        end = next_month

    # 조회
    cur.execute("""
        SELECT id, member_name, sdate, stime, equipment, exercises_json, status
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
            title = f"{r['sdate']} {r['stime']} · **{r['member_name']}** · *{r['equipment']}*"
            if r["status"] == "취소":
                title = f"<s>{title}</s>"
            st.markdown(title, unsafe_allow_html=True)
            st.caption(f"동작: {moves}")

            cols = st.columns(3)
            with cols[0]:
                if r["status"] != "취소" and st.button("❌ 취소", key=f"cancel_{r['id']}"):
                    cur.execute("UPDATE sessions SET status='취소' WHERE id=?", (r["id"],))
                    conn.commit()
                    st.experimental_rerun()
            with cols[1]:
                if r["status"] == "취소" and st.button("↩️ 복원", key=f"restore_{r['id']}"):
                    cur.execute("UPDATE sessions SET status='예약' WHERE id=?", (r["id"],))
                    conn.commit()
                    st.experimental_rerun()
            with cols[2]:
                if st.button("🗑 완전 삭제", key=f"delete_{r['id']}"):
                    cur.execute("DELETE FROM sessions WHERE id=?", (r["id"],))
                    conn.commit()
                    st.experimental_rerun()

        st.info("취소하면 제목에 취소선이 생겨요. 필요하면 복원/완전삭제도 가능!")
