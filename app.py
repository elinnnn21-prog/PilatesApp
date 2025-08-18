import streamlit as st
import sqlite3
import json
import os
from datetime import datetime

# =========================
# DB 연결
# =========================
conn = sqlite3.connect("sessions.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER,
    date TEXT,
    equipment TEXT,
    exercise TEXT,
    notes TEXT,
    homework TEXT,
    status TEXT DEFAULT '예약됨',
    FOREIGN KEY(member_id) REFERENCES members(id)
)
""")
conn.commit()

# =========================
# 운동 리스트 로드
# =========================
if os.path.exists("exercises.json"):
    with open("exercises.json", "r", encoding="utf-8") as f:
        EXERCISES = json.load(f)
else:
    EXERCISES = {
        "Mat": {"Basic": [], "Intermediate": [], "Advanced": []},
        "Reformer": {"Basic": [], "Intermediate": [], "Advanced": []},
        "Cadillac": {},
        "Wunda chair": {},
        "Spine corrector": {},
        "Ladder barrel": {}
    }

# =========================
# 멤버 관리 탭
# =========================
def member_management():
    st.header("👤 멤버 관리")

    menu = ["멤버 추가", "멤버 목록"]
    choice = st.radio("선택", menu)

    if choice == "멤버 추가":
        name = st.text_input("이름")
        phone = st.text_input("전화번호")

        if st.button("저장"):
            if not name or not phone:
                st.warning("이름과 전화번호를 입력하세요.")
            else:
                try:
                    c.execute("INSERT INTO members (name, phone) VALUES (?, ?)", (name, phone))
                    conn.commit()
                    st.success(f"{name} 님이 등록되었습니다.")
                except sqlite3.IntegrityError:
                    st.error("⚠️ 이미 등록된 전화번호입니다.")

    elif choice == "멤버 목록":
        members = c.execute("SELECT * FROM members").fetchall()
        for m in members:
            st.write(f"{m[0]} | {m[1]} | {m[2]}")

# =========================
# 세션 관리 탭
# =========================
def session_management():
    st.header("📅 세션 관리")

    members = c.execute("SELECT * FROM members").fetchall()
    member_dict = {f"{m[1]} ({m[2]})": m[0] for m in members}

    if not member_dict:
        st.warning("등록된 멤버가 없습니다. 멤버를 먼저 추가하세요.")
        return

    member = st.selectbox("멤버 선택", list(member_dict.keys()))
    member_id = member_dict[member]

    date = st.date_input("세션 날짜")
    equipment = st.selectbox("기구 선택", list(EXERCISES.keys()))

    # 기구별 동작 필터링
    exercise_options = []
    if isinstance(EXERCISES[equipment], dict):
        for level, ex_list in EXERCISES[equipment].items():
            exercise_options.extend([f"{level}: {ex}" for ex in ex_list])
    else:
        exercise_options = EXERCISES[equipment]

    exercise = st.multiselect("동작 선택", exercise_options)
    custom_exercise = st.text_input("직접 입력 (콤마로 구분)")
    if custom_exercise:
        exercise.extend([e.strip() for e in custom_exercise.split(",")])

    notes = st.text_area("특이사항")
    homework = st.text_area("숙제")

    if st.button("세션 저장"):
        c.execute("""
        INSERT INTO sessions (member_id, date, equipment, exercise, notes, homework)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (member_id, str(date), equipment, ", ".join(exercise), notes, homework))
        conn.commit()
        st.success("세션이 저장되었습니다 ✅")

    st.subheader("예약된 세션")
    sessions = c.execute("""
    SELECT s.id, m.name, s.date, s.equipment, s.exercise, s.status
    FROM sessions s
    JOIN members m ON s.member_id = m.id
    ORDER BY s.date
    """).fetchall()

    for s in sessions:
        st.write(f"{s[1]} | {s[2]} | {s[3]} | {s[4]} | 상태: {s[5]}")
        if st.button(f"세션 취소 {s[0]}", key=f"cancel_{s[0]}"):
            c.execute("UPDATE sessions SET status='취소됨' WHERE id=?", (s[0],))
            conn.commit()
            st.warning(f"세션 {s[0]}이 취소되었습니다.")

# =========================
# 메인 앱 실행
# =========================
def main():
    st.title("Pilates Manager")

    menu = ["멤버 관리", "세션 관리"]
    choice = st.sidebar.radio("메뉴 선택", menu)

    if choice == "멤버 관리":
        member_management()
    elif choice == "세션 관리":
        session_management()

if __name__ == "__main__":
    main()
