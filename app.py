# app.py (STEP 1 + 전화번호 중복확인)
from pathlib import Path
from datetime import date
import pandas as pd
import streamlit as st

# ---------- 기본 설정 ----------
st.set_page_config(page_title="Pilates Manager", page_icon="🏋️", layout="wide")
DATA_DIR = Path(".")
MEMBERS_CSV = DATA_DIR / "members.csv"
SITES = ["플로우", "리유", "방문"]

# ---------- 유틸 ----------
def ensure_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEMBERS_CSV.exists():
        cols = ["id", "이름", "연락처", "지점", "등록일", "메모"]
        pd.DataFrame(columns=cols).to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def load_members() -> pd.DataFrame:
    def norm_phone(s: str) -> str:
    """전화번호 비교용: 숫자만 남김 (010-1111-2222 == 01011112222)"""
    return "".join(ch for ch in str(s) if ch.isdigit())

    ensure_files()
    return pd.read_csv(MEMBERS_CSV, dtype=str, encoding="utf-8-sig").fillna("")

def save_members(df: pd.DataFrame):
    df.to_csv(MEMBERS_CSV, index=False, encoding="utf-8-sig")

def norm_phone(s: str) -> str:
    """숫자만 남겨 비교용으로 사용"""
    return "".join(ch for ch in str(s) if ch.isdigit())

ensure_files()

# ---------- 사이드바 ----------
nav = st.sidebar.radio("탭", ["🧑‍🤝‍🧑 멤버"], index=0)

# ---------- 멤버 탭 ----------
if nav == "🧑‍🤝‍🧑 멤버":
    st.title("🧑‍🤝‍🧑 멤버 관리 (STEP 1)")
    members = load_members()

    st.subheader("등록 / 수정")
    col1, col2 = st.columns(2)

    with col1:
        mode = st.radio("모드 선택", ["신규 등록", "수정/삭제"], horizontal=True)

        if mode == "신규 등록":
            name  = st.text_input("이름")
            phone = st.text_input("연락처", placeholder="010-0000-0000")
            site  = st.selectbox("기본 지점", SITES, index=0)
            reg_date = st.date_input("등록일", value=date.today())
            memo  = st.text_input("메모(선택)")

            # 입력 즉시 중복 경고(선택)
            if phone.strip():
                np = norm_phone(phone)
                dup = members[members["연락처"].apply(norm_phone) == np]
                if not dup.empty:
                    st.warning(f"⚠️ 이미 등록된 번호예요 → {dup.iloc[0]['이름']}")

            if st.button("➕ 등록", use_container_width=True):
                if not name.strip():
                    st.error("이름을 입력해 주세요.")
                elif not phone.strip():
                    st.error("연락처를 입력해 주세요.")
                else:
                    np = norm_phone(phone)
                    # 최종 중복 체크
                    if any(members["연락처"].apply(norm_phone) == np):
                        who = members[members["연락처"].apply(norm_phone) == np].iloc[0]["이름"]
                        st.error(f"이미 등록된 전화번호입니다. (소유자: {who})")
                    else:
                        new_id = str(len(members) + 1)
                        row = pd.DataFrame([{
                            "id": new_id,
                            "이름": name.strip(),
                            "연락처": phone.strip(),  # 원문 그대로 저장
                            "지점": site,
                            "등록일": reg_date.isoformat(),
                            "메모": memo.strip()
                        }])
                        members = pd.concat([members, row], ignore_index=True)
                        save_members(members)
                        st.success(f"등록 완료: {name}")

        else:  # 수정/삭제
            if members.empty:
                st.info("멤버가 없습니다. 먼저 등록하세요.")
            else:
                target = st.selectbox("대상 선택", members["이름"].tolist())
                row = members[members["이름"] == target].iloc[0]

                name  = st.text_input("이름", row["이름"])
                phone = st.text_input("연락처", row["연락처"])
                site  = st.selectbox("기본 지점", SITES,
                                     index=SITES.index(row["지점"] or "플로우"))
                try:
                    d = pd.to_datetime(row["등록일"]).date()
                except Exception:
                    d = date.today()
                reg_date = st.date_input("등록일", d)
                memo = st.text_input("메모(선택)", row["메모"])

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💾 수정", use_container_width=True):
                        idx = members.index[members["이름"] == target][0]
                        np = norm_phone(phone)
                        # 자신의 레코드를 제외하고 중복 검사
                        others = members.drop(index=idx)
                        if any(others["연락처"].apply(norm_phone) == np):
                            who = others[others["연락처"].apply(norm_phone) == np].iloc[0]["이름"]
                            st.error(f"이미 다른 회원이 사용 중인 번호입니다. (소유자: {who})")
                        else:
                            members.loc[idx, ["이름","연락처","지점","등록일","메모"]] = [
                                name.strip(), phone.strip(), site, reg_date.isoformat(), memo.strip()
                            ]
                            save_members(members)
                            st.success("수정 완료")

                with c2:
                    if st.button("🗑 삭제", use_container_width=True):
                        members = members[members["이름"] != target].reset_index(drop=True)
                        save_members(members)
                        st.success(f"삭제 완료: {target}")

    st.subheader("현재 멤버")
    members = load_members()
    if members.empty:
        st.info("표시할 멤버가 없습니다.")
    else:
        show = members.copy()
        show["등록일"] = pd.to_datetime(show["등록일"], errors="coerce").dt.date.astype(str)
        st.dataframe(show, use_container_width=True, hide_index=True)

