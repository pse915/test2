from __future__ import annotations

import hashlib
import io
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, WorksheetNotFound

# ============================================================
# 기본 설정
# ============================================================
APP_TITLE = "기술·가정 포트폴리오"
DEFAULT_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1TM-90ev9Weibwqnq1xOhOQZCP78kNHANF_p4W2XZJMo/edit"
WEEKS = list(range(1, 18))
KST = ZoneInfo("Asia/Seoul")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_CONFIG = {
    "학생명단": ["학번", "이름", "학년", "반", "번호"],
    "주차설정": ["주차", "학습목표", "활동지질문"],
    "포트폴리오": [
        "제출ID",
        "학번",
        "주차",
        "제출내용",
        "점수",
        "피드백",
        "제출일시",
        "수정일시",
        "상태",
    ],
}


def normalize_text(value: Any) -> str:
    """시트 셀 값을 안전한 문자열로 정규화합니다."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0") and re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def normalize_student_id(value: Any) -> str:
    return normalize_text(value)


def now_kst() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")


def is_blank(value: Any) -> bool:
    return normalize_text(value) == ""


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if is_blank(value):
            return default
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return default


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ============================================================
# Google Sheets 연결
# ============================================================
def _get_gsheets_config() -> Dict[str, Any]:
    """
    Google Sheets/서비스 계정 Secrets를 하나의 설정으로 합칩니다.

    지원 형식
    1) [connections.gsheets] 안에 spreadsheet + 서비스 계정 키를 모두 넣는 기존 형식
    2) [connections.gsheets]에는 spreadsheet만 넣고, [gcp_service_account]에
       서비스 계정 키를 넣는 권장 형식
    3) 사용자가 실수로 spreadsheet를 [gcp_service_account] 아래에 넣은 경우도 호환
    """
    try:
        connections = st.secrets.get("connections", {})
        gsheets = dict(connections.get("gsheets", {})) if connections else {}
        gcp = dict(st.secrets.get("gcp_service_account", {}))
    except Exception as exc:
        raise RuntimeError(
            "Streamlit Secrets를 읽지 못했습니다. [connections.gsheets] 또는 [gcp_service_account] 설정을 확인하세요."
        ) from exc

    # 권장 구조를 우선하고, 없는 값은 다른 섹션에서 보완합니다.
    config: Dict[str, Any] = dict(gcp)
    config.update(gsheets)

    # spreadsheet가 gcp_service_account 쪽에 들어간 현재 사용자 설정도 허용합니다.
    spreadsheet_ref = (
        gsheets.get("spreadsheet")
        or gsheets.get("spreadsheet_url")
        or gsheets.get("spreadsheet_id")
        or gcp.get("spreadsheet")
        or gcp.get("spreadsheet_url")
        or gcp.get("spreadsheet_id")
    )
    if spreadsheet_ref:
        config["spreadsheet"] = spreadsheet_ref
    else:
        # 시트 주소는 공개 식별자이므로 기본값으로 앱에 포함할 수 있습니다.
        # Secrets에 spreadsheet 값을 넣으면 그 값이 우선됩니다.
        config["spreadsheet"] = DEFAULT_SPREADSHEET_URL

    return config


@st.cache_resource(show_spinner=False)
def get_gspread_client() -> gspread.Client:
    """Streamlit Secrets의 [connections.gsheets] 서비스 계정 정보로 연결합니다."""
    config = _get_gsheets_config()

    required = [
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
    ]
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(
            "Google 서비스 계정 Secrets가 부족합니다. "
            "[gcp_service_account] 또는 [connections.gsheets]에 "
            "다음 항목을 추가하세요: " + ", ".join(missing)
        )

    spreadsheet_ref = config.get("spreadsheet") or config.get("spreadsheet_url") or config.get("spreadsheet_id")
    if not spreadsheet_ref:
        raise RuntimeError(
            "[connections.gsheets]에 spreadsheet(권장), spreadsheet_url 또는 spreadsheet_id 중 하나를 설정하세요."
        )

    service_account_info = {key: config[key] for key in required}
    # TOML에 private_key를 "\\n"으로 저장한 경우 실제 개행으로 변환합니다.
    service_account_info["private_key"] = str(service_account_info["private_key"]).replace("\\n", "\n")

    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(credentials)

    return client


@st.cache_resource(show_spinner=False)
def get_spreadsheet(spreadsheet_ref: str) -> gspread.Spreadsheet:
    client = get_gspread_client()
    ref = str(spreadsheet_ref).strip()
    if not ref:
        raise RuntimeError("Google Sheets 참조 정보가 없습니다.")

    try:
        if ref.startswith("http://") or ref.startswith("https://"):
            return client.open_by_url(ref)
        # 10자 이상처럼 보이는 값을 ID로 우선 시도하고, 실패하면 이름으로 엽니다.
        try:
            return client.open_by_key(ref)
        except Exception:
            return client.open(ref)
    except Exception as exc:
        raise RuntimeError(
            "Google Sheets를 열지 못했습니다. 서비스 계정 이메일에 해당 스프레드시트의 편집 권한이 있는지 확인하세요."
        ) from exc


def get_or_create_worksheet(title: str, headers: List[str]) -> gspread.Worksheet:
    config = _get_gsheets_config()
    spreadsheet_ref = config.get("spreadsheet") or config.get("spreadsheet_url") or config.get("spreadsheet_id")
    if not spreadsheet_ref:
        raise RuntimeError("[connections.gsheets]에 spreadsheet, spreadsheet_url 또는 spreadsheet_id를 설정하세요.")
    spreadsheet = get_spreadsheet(str(spreadsheet_ref))
    try:
        ws = spreadsheet.worksheet(title)
    except WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=max(1000, len(headers) + 10), cols=max(20, len(headers)))
        ws.update(range_name=f"A1:{_a1_col(len(headers))}1", values=[headers])
        return ws

    current_headers = ws.row_values(1)
    if current_headers != headers:
        # 필수 헤더가 없는 경우 자동 보정합니다. 기존 데이터 열은 임의 삭제하지 않습니다.
        current_headers = [normalize_text(v) for v in current_headers]
        missing_headers = [h for h in headers if h not in current_headers]
        if missing_headers:
            new_headers = current_headers + missing_headers
            ws.update(range_name=f"A1:{_a1_col(len(new_headers))}1", values=[new_headers])
    return ws


def _a1_col(n: int) -> str:
    result = ""
    x = n
    while x:
        x, rem = divmod(x - 1, 26)
        result = chr(65 + rem) + result
    return result


# ============================================================
# Sheets 읽기 / 캐시
# ============================================================
@st.cache_data(ttl=20, show_spinner=False)
def read_sheet_records(title: str, headers: Tuple[str, ...]) -> List[Dict[str, str]]:
    ws = get_or_create_worksheet(title, list(headers))
    values = ws.get_all_values()
    if not values:
        return []
    actual_headers = [normalize_text(v) for v in values[0]]
    records: List[Dict[str, str]] = []
    for row in values[1:]:
        padded = list(row) + [""] * max(0, len(actual_headers) - len(row))
        records.append({
            actual_headers[i]: normalize_text(padded[i]) for i in range(len(actual_headers))
        })
    return records


def invalidate_data_cache() -> None:
    read_sheet_records.clear()
    read_roster.clear()
    read_week_settings.clear()
    read_portfolios.clear()


@st.cache_data(ttl=30, show_spinner=False)
def read_roster() -> pd.DataFrame:
    records = read_sheet_records("학생명단", tuple(SHEET_CONFIG["학생명단"]))
    df = pd.DataFrame(records)
    for col in SHEET_CONFIG["학생명단"]:
        if col not in df.columns:
            df[col] = ""
    if df.empty:
        return pd.DataFrame(columns=SHEET_CONFIG["학생명단"])
    for col in df.columns:
        df[col] = df[col].map(normalize_text)
    return df[SHEET_CONFIG["학생명단"]].copy()


@st.cache_data(ttl=30, show_spinner=False)
def read_week_settings() -> pd.DataFrame:
    records = read_sheet_records("주차설정", tuple(SHEET_CONFIG["주차설정"]))
    df = pd.DataFrame(records)
    for col in SHEET_CONFIG["주차설정"]:
        if col not in df.columns:
            df[col] = ""
    if df.empty:
        return pd.DataFrame(columns=SHEET_CONFIG["주차설정"])
    df["주차"] = df["주차"].map(lambda x: safe_int(x, 0))
    return df[SHEET_CONFIG["주차설정"]].copy()


@st.cache_data(ttl=20, show_spinner=False)
def read_portfolios() -> pd.DataFrame:
    records = read_sheet_records("포트폴리오", tuple(SHEET_CONFIG["포트폴리오"]))
    df = pd.DataFrame(records)
    for col in SHEET_CONFIG["포트폴리오"]:
        if col not in df.columns:
            df[col] = ""
    if df.empty:
        return pd.DataFrame(columns=SHEET_CONFIG["포트폴리오"])

    for col in ["제출ID", "학번", "제출내용", "피드백", "제출일시", "수정일시", "상태"]:
        df[col] = df[col].map(normalize_text)
    df["주차"] = df["주차"].map(lambda x: safe_int(x, 0))
    df["점수"] = pd.to_numeric(df["점수"], errors="coerce")
    return df[SHEET_CONFIG["포트폴리오"]].copy()


# ============================================================
# 주차/Portfolio 조회
# ============================================================
def week_info(week: int) -> Tuple[str, str]:
    df = read_week_settings()
    if not df.empty:
        found = df[df["주차"] == week]
        if not found.empty:
            row = found.iloc[0]
            goal = normalize_text(row.get("학습목표", ""))
            question = normalize_text(row.get("활동지질문", ""))
            return (
                goal or f"{week}주차의 핵심 개념과 학습 내용을 정리합니다.",
                question or "이번 주 학습에서 이해한 핵심 내용, 수행 과정, 결과를 구체적으로 기록해 보세요.",
            )
    return (
        f"{week}주차의 핵심 개념과 학습 내용을 정리합니다.",
        "이번 주 학습에서 이해한 핵심 내용, 수행 과정, 결과를 구체적으로 기록해 보세요.",
    )


def latest_student_portfolio(portfolios: pd.DataFrame, student_id: str) -> pd.DataFrame:
    """같은 학생·주차의 중복 행이 있다면 가장 마지막 행을 사용합니다."""
    if portfolios.empty:
        return portfolios.copy()
    df = portfolios[portfolios["학번"].map(normalize_student_id) == normalize_student_id(student_id)].copy()
    if df.empty:
        return df
    df["_order"] = range(len(df))
    df = df.sort_values("_order").drop_duplicates(subset=["학번", "주차"], keep="last")
    return df.drop(columns=["_order"])


def get_portfolio_sheet() -> gspread.Worksheet:
    return get_or_create_worksheet("포트폴리오", SHEET_CONFIG["포트폴리오"])


def _find_portfolio_row(ws: gspread.Worksheet, student_id: str, week: int) -> Optional[int]:
    values = ws.get_all_values()
    if len(values) <= 1:
        return None
    headers = [normalize_text(v) for v in values[0]]
    try:
        id_col = headers.index("학번")
        week_col = headers.index("주차")
    except ValueError:
        raise RuntimeError("포트폴리오 시트의 헤더가 올바르지 않습니다.")

    found: Optional[int] = None
    for idx, row in enumerate(values[1:], start=2):
        padded = row + [""] * max(0, len(headers) - len(row))
        if normalize_student_id(padded[id_col]) == normalize_student_id(student_id) and safe_int(padded[week_col], -1) == week:
            found = idx
    return found


def _header_map(ws: gspread.Worksheet) -> Dict[str, int]:
    return {h: i + 1 for i, h in enumerate([normalize_text(v) for v in ws.row_values(1)])}


def save_student_submission(student_id: str, week: int, content: str) -> None:
    content = content.strip()
    if not content:
        raise ValueError("제출 내용이 비어 있습니다. 답안을 작성해 주세요.")

    ws = get_portfolio_sheet()
    header = _header_map(ws)
    row_num = _find_portfolio_row(ws, student_id, week)
    timestamp = now_kst()

    if row_num is None:
        values = [
            uuid.uuid4().hex[:12],
            normalize_student_id(student_id),
            str(week),
            content,
            "",
            "",
            timestamp,
            "",
            "제출완료",
        ]
        ws.append_row(values, value_input_option="RAW")
    else:
        # 학생 제출은 필요한 셀만 한 번의 batch_update로 갱신하여
        # 교사가 입력한 점수·피드백을 덮어쓰지 않으며 API 호출 수도 줄입니다.
        ws.batch_update([
            {"range": f"{_a1_col(header['제출내용'])}{row_num}", "values": [[content]]},
            {"range": f"{_a1_col(header['제출일시'])}{row_num}", "values": [[timestamp]]},
            {"range": f"{_a1_col(header['수정일시'])}{row_num}", "values": [[timestamp]]},
            {"range": f"{_a1_col(header['상태'])}{row_num}", "values": [["제출완료"]]},
        ], raw=True)

    invalidate_data_cache()


def save_teacher_grade(student_id: str, week: int, score: Optional[float], feedback: str) -> None:
    if score is not None and (score < 0 or score > 100):
        raise ValueError("점수는 0~100 사이로 입력하세요.")

    ws = get_portfolio_sheet()
    header = _header_map(ws)
    row_num = _find_portfolio_row(ws, student_id, week)
    if row_num is None:
        raise ValueError("아직 제출된 포트폴리오가 없어 점수를 저장할 수 없습니다.")

    score_value = "" if score is None else str(round(float(score), 1))
    # 점수·피드백을 하나의 요청으로 저장합니다.
    ws.batch_update([
        {"range": f"{_a1_col(header['점수'])}{row_num}", "values": [[score_value]]},
        {"range": f"{_a1_col(header['피드백'])}{row_num}", "values": [[feedback.strip()]]},
    ], raw=True)
    invalidate_data_cache()


# ============================================================
# 인증 / 세션 상태
# ============================================================
def init_state() -> None:
    defaults = {
        "role": None,
        "student_id": None,
        "student_name": None,
        "selected_week": 1,
        "admin_tab": "대시보드",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session() -> None:
    for key in ["role", "student_id", "student_name", "selected_week", "admin_tab"]:
        st.session_state.pop(key, None)
    st.cache_resource.clear()
    st.cache_data.clear()
    st.rerun()


def get_teacher_password_config() -> Tuple[Optional[str], Optional[str]]:
    password = st.secrets.get("TEACHER_PASSWORD")
    password_hash = st.secrets.get("TEACHER_PASSWORD_HASH")
    return (
        normalize_text(password) or None,
        normalize_text(password_hash) or None,
    )


def verify_teacher_password(password: str) -> bool:
    plain, password_hash = get_teacher_password_config()
    if password_hash:
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash
    if plain:
        return password == plain
    return False


def student_login(student_id_input: str) -> bool:
    student_id = normalize_student_id(student_id_input)
    roster = read_roster()
    if roster.empty:
        return False
    matched = roster[roster["학번"].map(normalize_student_id) == student_id]
    if matched.empty:
        return False
    row = matched.iloc[0]
    st.session_state["role"] = "student"
    st.session_state["student_id"] = student_id
    st.session_state["student_name"] = normalize_text(row["이름"])
    st.session_state["selected_week"] = 1
    return True


def render_login() -> None:
    st.markdown(
        """
        <div class='hero'>
          <div class='eyebrow'>TECH · HOME ECONOMICS</div>
          <h1>한 학기 포트폴리오</h1>
          <p>1주차부터 17주차까지의 학습 과정과 성장을 기록합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_student, tab_teacher = st.tabs(["학생 로그인", "교사 로그인"])
    with tab_student:
        with st.form("student_login_form", clear_on_submit=False):
            student_id = st.text_input(
                "학번",
                placeholder="예: 10101",
                max_chars=20,
                key="student_login_input",
            )
            submitted = st.form_submit_button("학생으로 들어가기", type="primary", use_container_width=True)
        if submitted:
            if student_login(student_id):
                st.success(f"{st.session_state['student_name']} 학생으로 로그인했습니다.")
                st.rerun()
            else:
                st.error("학생명단에서 학번을 찾지 못했습니다. 학번을 다시 확인하세요.")
        st.caption("학생 로그인은 학생명단 시트에 등록된 학번만 사용할 수 있습니다.")

    with tab_teacher:
        with st.form("teacher_login_form", clear_on_submit=False):
            password = st.text_input("관리자 비밀번호", type="password", key="teacher_password_input")
            submitted = st.form_submit_button("교사 모드로 들어가기", type="primary", use_container_width=True)
        if submitted:
            if verify_teacher_password(password):
                st.session_state["role"] = "teacher"
                st.rerun()
            if get_teacher_password_config() == (None, None):
                st.error("관리자 비밀번호가 Secrets에 설정되어 있지 않습니다.")
            else:
                st.error("관리자 비밀번호가 올바르지 않습니다.")


# ============================================================
# 스타일
# ============================================================
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp { background: #f5f5f7; }
        .block-container { max-width: 1420px; padding-top: 2.4rem; padding-bottom: 4rem; }
        .hero { padding: 1.2rem 0 1.4rem; }
        .eyebrow { font-size: .74rem; font-weight: 700; letter-spacing: .12em; color: #6e6e73; }
        .hero h1 { margin: .2rem 0 .3rem; font-size: 2.3rem; letter-spacing: -.04em; color: #1d1d1f; }
        .hero p { margin: 0; color: #6e6e73; font-size: 1rem; }
        .section-title { font-size: 1.35rem; font-weight: 750; color: #1d1d1f; margin: .3rem 0 .4rem; }
        .muted { color: #6e6e73; }
        .card { background: white; border: 1px solid rgba(0,0,0,.06); border-radius: 20px; padding: 1.1rem 1.15rem; box-shadow: 0 8px 30px rgba(0,0,0,.035); }
        .metric { background: white; border: 1px solid rgba(0,0,0,.06); border-radius: 18px; padding: .9rem 1rem; }
        .metric-label { color:#6e6e73; font-size:.78rem; }
        .metric-value { color:#1d1d1f; font-size:1.45rem; font-weight:750; margin-top:.15rem; }
        .week-badge { display:inline-block; padding:.28rem .55rem; border-radius:999px; background:#f2f2f7; color:#1d1d1f; font-size:.76rem; font-weight:700; }
        div[data-testid="stDataFrame"] { border-radius: 14px; overflow:hidden; }
        button[kind="primary"] { border-radius: 12px; }
        .stButton > button { border-radius: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 공통 UI
# ============================================================
def render_topbar(name: str, role_label: str) -> None:
    c1, c2 = st.columns([6, 1], vertical_alignment="center")
    with c1:
        st.markdown(f"<div class='muted'>{role_label}</div><div style='font-size:1.4rem;font-weight:750;color:#1d1d1f'>{name}</div>", unsafe_allow_html=True)
    with c2:
        if st.button("로그아웃", use_container_width=True):
            reset_session()


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"<div class='metric'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def student_portfolio_summary(student_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    portfolios = latest_student_portfolio(read_portfolios(), student_id)
    rows = []
    for week in WEEKS:
        found = portfolios[portfolios["주차"] == week]
        if found.empty:
            rows.append({"주차": f"{week}주차", "제출": "미제출", "점수": "-", "피드백": ""})
        else:
            row = found.iloc[0]
            score = row["점수"]
            score_text = "-" if pd.isna(score) else f"{float(score):g}"
            rows.append({
                "주차": f"{week}주차",
                "제출": "제출완료" if normalize_text(row["상태"]) or row["제출내용"] else "미제출",
                "점수": score_text,
                "피드백": normalize_text(row["피드백"]),
            })
    summary = pd.DataFrame(rows)

    scored = pd.to_numeric(portfolios["점수"], errors="coerce") if not portfolios.empty else pd.Series(dtype=float)
    return summary, pd.DataFrame({"점수": scored})


# ============================================================
# 학생 모드
# ============================================================
def render_student() -> None:
    student_id = st.session_state["student_id"]
    student_name = st.session_state["student_name"]
    roster = read_roster()
    portfolios_all = read_portfolios()
    portfolios = latest_student_portfolio(portfolios_all, student_id)

    render_topbar(f"{student_name} · {student_id}", "학생 포트폴리오")

    submitted_count = len(portfolios[portfolios["제출내용"].map(lambda x: not is_blank(x))]) if not portfolios.empty else 0
    score_series = pd.to_numeric(portfolios["점수"], errors="coerce") if not portfolios.empty else pd.Series(dtype=float)
    total_score = float(score_series.fillna(0).sum()) if not score_series.empty else 0.0
    scored_count = int(score_series.notna().sum()) if not score_series.empty else 0

    m1, m2, m3 = st.columns(3)
    with m1:
        metric_card("제출 현황", f"{submitted_count} / 17주")
    with m2:
        metric_card("누적 점수", f"{total_score:g}점")
    with m3:
        metric_card("채점 완료", f"{scored_count}주")

    st.write("")
    portfolio_tab, mypage_tab = st.tabs(["주차별 포트폴리오", "나의 성적 · 요약"])

    with portfolio_tab:
        left, right = st.columns([2, 5], vertical_alignment="bottom")
        with left:
            default_week = int(st.session_state.get("selected_week", 1))
            selected_week = st.selectbox(
                "주차 선택",
                WEEKS,
                index=WEEKS.index(default_week) if default_week in WEEKS else 0,
                format_func=lambda x: f"{x}주차",
                key="student_week_selector",
            )
            st.session_state["selected_week"] = selected_week
        with right:
            goal, question = week_info(selected_week)
            st.markdown(f"<span class='week-badge'>{selected_week}주차</span>", unsafe_allow_html=True)
            st.markdown(f"**학습 목표**  {goal}")

        st.markdown(f"### 활동지 질문\n{question}")

        existing = portfolios[portfolios["주차"] == selected_week]
        existing_content = existing.iloc[0]["제출내용"] if not existing.empty else ""
        existing_feedback = existing.iloc[0]["피드백"] if not existing.empty else ""
        existing_score = existing.iloc[0]["점수"] if not existing.empty else float("nan")
        existing_timestamp = existing.iloc[0]["수정일시"] or existing.iloc[0]["제출일시"] if not existing.empty else ""

        with st.form(f"portfolio_form_{selected_week}"):
            content = st.text_area(
                "학생 답안",
                value=existing_content,
                height=280,
                placeholder="학습 과정, 생각, 수행 결과를 구체적으로 기록해 보세요.",
                key=f"content_{selected_week}",
            )
            submitted = st.form_submit_button("제출 / 수정 저장", type="primary", use_container_width=True)

        if submitted:
            try:
                save_student_submission(student_id, selected_week, content)
                st.success(f"{selected_week}주차 포트폴리오가 저장되었습니다.")
                st.rerun()
            except (ValueError, APIError, RuntimeError) as exc:
                st.error(str(exc))

        info1, info2, info3 = st.columns(3)
        with info1:
            status = "제출완료" if not is_blank(existing_content) else "미제출"
            metric_card("상태", status)
        with info2:
            score_text = "-" if pd.isna(existing_score) else f"{float(existing_score):g}점"
            metric_card("점수", score_text)
        with info3:
            metric_card("최근 저장", existing_timestamp or "-" )

        if existing_feedback:
            st.markdown("#### 교사 피드백")
            st.info(existing_feedback)

    with mypage_tab:
        st.markdown("### 1~17주차 제출 현황")
        summary, _ = student_portfolio_summary(student_id)
        st.dataframe(summary, hide_index=True, use_container_width=True)

        completed = summary[summary["제출"] == "제출완료"]
        completion_rate = (len(completed) / 17) * 100
        score_values = pd.to_numeric(summary["점수"].replace("-", pd.NA), errors="coerce")
        avg_score = float(score_values.mean()) if score_values.notna().any() else 0.0
        total = float(score_values.fillna(0).sum()) if len(score_values) else 0.0

        a, b, c = st.columns(3)
        with a:
            metric_card("제출률", f"{completion_rate:.0f}%")
        with b:
            metric_card("평균 점수", f"{avg_score:.1f}점")
        with c:
            metric_card("총점", f"{total:g}점")

        st.markdown("### 주차별 점수")
        chart_df = pd.DataFrame({
            "주차": WEEKS,
            "점수": score_values.tolist(),
        }).fillna(0)
        fig = px.bar(chart_df, x="주차", y="점수", text_auto=True, labels={"주차": "주차", "점수": "점수"})
        fig.update_layout(height=330, margin=dict(l=10, r=10, t=30, b=10), xaxis=dict(dtick=1))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 교사 피드백")
        feedback_rows = summary[summary["피드백"].astype(str).str.strip() != ""][["주차", "피드백"]]
        if feedback_rows.empty:
            st.caption("아직 등록된 피드백이 없습니다.")
        else:
            st.dataframe(feedback_rows, hide_index=True, use_container_width=True)


# ============================================================
# 교사 대시보드
# ============================================================
def latest_all_portfolios() -> pd.DataFrame:
    df = read_portfolios().copy()
    if df.empty:
        return df
    df["_order"] = range(len(df))
    df = df.sort_values("_order").drop_duplicates(subset=["학번", "주차"], keep="last")
    return df.drop(columns=["_order"])


def build_overall_table(roster: pd.DataFrame, portfolios: pd.DataFrame) -> pd.DataFrame:
    base = roster.copy()
    if base.empty:
        return pd.DataFrame()
    if portfolios.empty:
        portfolios = pd.DataFrame(columns=SHEET_CONFIG["포트폴리오"])
    else:
        portfolios = portfolios.copy()
        portfolios["학번"] = portfolios["학번"].map(normalize_student_id)

    p = portfolios[["학번", "주차", "점수"]].copy()
    p["점수"] = pd.to_numeric(p["점수"], errors="coerce")
    pivot = p.pivot(index="학번", columns="주차", values="점수") if not p.empty else pd.DataFrame()
    pivot = pivot.reindex(columns=WEEKS, fill_value=pd.NA)
    pivot.columns = [f"{w}주차" for w in WEEKS]
    if not pivot.empty:
        pivot["총점"] = pivot.sum(axis=1, skipna=True)
        pivot["채점주"] = pivot[[f"{w}주차" for w in WEEKS]].notna().sum(axis=1)
    else:
        pivot = pd.DataFrame(index=pd.Index([], name="학번"))
        for w in WEEKS:
            pivot[f"{w}주차"] = pd.NA
        pivot["총점"] = 0
        pivot["채점주"] = 0

    result = base.merge(pivot.reset_index(), on="학번", how="left")
    week_cols = [f"{w}주차" for w in WEEKS]
    result["총점"] = result["총점"].fillna(0)
    result["채점주"] = result["채점주"].fillna(0).astype(int)
    result["제출주"] = 0
    if not portfolios.empty:
        submitted = portfolios[portfolios["제출내용"].map(lambda x: not is_blank(x))].drop_duplicates(["학번", "주차"])
        count_map = submitted.groupby("학번")["주차"].nunique()
        result["제출주"] = result["학번"].map(count_map).fillna(0).astype(int)
    result["제출률"] = result["제출주"] / len(WEEKS) * 100
    return result[["학번", "이름", "학년", "반", "번호", "제출주", "제출률", "채점주", "총점"] + week_cols]


def build_class_stats(roster: pd.DataFrame, portfolios: pd.DataFrame) -> pd.DataFrame:
    overall = build_overall_table(roster, portfolios)
    if overall.empty:
        return pd.DataFrame()
    stats = overall.groupby(["학년", "반"], dropna=False).agg(
        학생수=("학번", "nunique"),
        제출률=("제출률", "mean"),
        평균총점=("총점", "mean"),
    ).reset_index()
    stats["학급"] = stats["학년"].astype(str) + "학년 " + stats["반"].astype(str) + "반"
    return stats[["학급", "학생수", "제출률", "평균총점"]].sort_values("학급")


def render_teacher_dashboard(roster: pd.DataFrame, portfolios: pd.DataFrame) -> None:
    st.markdown("### 종합 현황")
    overall = build_overall_table(roster, portfolios)
    class_stats = build_class_stats(roster, portfolios)

    submitted = int((overall["제출주"].sum()) if not overall.empty else 0)
    expected = len(overall) * len(WEEKS)
    submission_rate = submitted / expected * 100 if expected else 0
    avg_total = float(overall["총점"].mean()) if not overall.empty else 0.0
    scored_records = int((pd.to_numeric(portfolios["점수"], errors="coerce").notna()).sum()) if not portfolios.empty else 0

    a, b, c, d = st.columns(4)
    with a:
        metric_card("등록 학생", f"{len(overall):,}명")
    with b:
        metric_card("전체 제출률", f"{submission_rate:.1f}%")
    with c:
        metric_card("학생 평균 총점", f"{avg_total:.1f}점")
    with d:
        metric_card("채점 데이터", f"{scored_records:,}건")

    st.write("")
    st.markdown("#### 학급별 제출률")
    if class_stats.empty:
        st.info("학생명단에 학생을 등록하면 통계가 표시됩니다.")
    else:
        fig = px.bar(
            class_stats,
            x="학급",
            y="제출률",
            text=class_stats["제출률"].round(1).astype(str) + "%",
            labels={"학급": "학급", "제출률": "제출률(%)"},
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=20), yaxis=dict(range=[0, 100]))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(class_stats.round({"제출률": 1, "평균총점": 1}), hide_index=True, use_container_width=True)

    st.markdown("#### 학년별 비교")
    if not overall.empty:
        grade_stats = overall.groupby("학년", dropna=False).agg(
            학생수=("학번", "nunique"),
            제출률=("제출률", "mean"),
            평균총점=("총점", "mean"),
        ).reset_index()
        st.dataframe(grade_stats.round({"제출률": 1, "평균총점": 1}), hide_index=True, use_container_width=True)


def render_teacher_grade(roster: pd.DataFrame, portfolios: pd.DataFrame) -> None:
    st.markdown("### 개별 학생 채점 · 피드백")
    if roster.empty:
        st.warning("학생명단 시트에 학생이 없습니다.")
        return

    grade_values = sorted([x for x in roster["학년"].unique() if x != ""], key=lambda x: safe_int(x, 999))
    grade = st.selectbox("학년", grade_values, key="grade_selector")
    class_values = sorted([x for x in roster.loc[roster["학년"] == grade, "반"].unique() if x != ""], key=lambda x: safe_int(x, 999))
    class_no = st.selectbox("반", class_values, key="class_selector")

    students = roster[(roster["학년"] == grade) & (roster["반"] == class_no)].copy()
    students = students.sort_values(by="번호", key=lambda s: s.map(lambda x: safe_int(x, 999)))
    student_options = students["학번"].tolist()
    student_id = st.selectbox(
        "학생",
        student_options,
        format_func=lambda sid: f"{sid} · {students.loc[students['학번'] == sid, '이름'].iloc[0]}",
        key="teacher_student_selector",
    )
    week = st.selectbox("주차", WEEKS, format_func=lambda x: f"{x}주차", key="teacher_week_selector")

    student_row = students[students["학번"] == student_id].iloc[0]
    st.markdown(f"#### {student_row['이름']} · {student_id} · {week}주차")

    current = latest_student_portfolio(portfolios, student_id)
    current = current[current["주차"] == week]
    if current.empty or is_blank(current.iloc[0]["제출내용"]):
        st.info("해당 주차에 학생이 아직 제출한 포트폴리오가 없습니다.")
        return

    row = current.iloc[0]
    st.markdown("##### 학생 제출 내용")
    st.markdown(f"<div class='card'>{normalize_text(row['제출내용']).replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
    st.caption(f"제출일시: {row['제출일시'] or '-'}")

    has_score = not pd.isna(row["점수"])
    current_score = 0.0 if not has_score else float(row["점수"])
    current_feedback = normalize_text(row["피드백"])
    with st.form("teacher_grade_form"):
        grade_enabled = st.checkbox("채점 완료", value=has_score, key="grade_enabled")
        score = st.number_input("점수 (0~100)", min_value=0.0, max_value=100.0, value=float(current_score), step=1.0)
        feedback = st.text_input("피드백(한 줄 평)", value=current_feedback, max_chars=300)
        save = st.form_submit_button("점수 · 피드백 저장", type="primary", use_container_width=True)

    if save:
        try:
            save_teacher_grade(student_id, week, score if grade_enabled else None, feedback)
            st.success("점수와 피드백이 저장되었습니다.")
            st.rerun()
        except (ValueError, APIError, RuntimeError) as exc:
            st.error(str(exc))


def render_teacher_download(roster: pd.DataFrame, portfolios: pd.DataFrame) -> None:
    st.markdown("### 전체 성적표 다운로드")
    overall = build_overall_table(roster, portfolios)
    if overall.empty:
        st.info("다운로드할 학생 데이터가 없습니다.")
        return

    csv_bytes = overall.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "전체 학생 주차별 점수표 CSV 다운로드",
        data=csv_bytes,
        file_name=f"기술가정_포트폴리오_성적표_{datetime.now(KST).strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.dataframe(overall, hide_index=True, use_container_width=True, height=560)


def render_teacher() -> None:
    roster = read_roster()
    portfolios = latest_all_portfolios()
    render_topbar("교사 관리자", "기술·가정 포트폴리오 · 관리자 모드")

    tab_dashboard, tab_grade, tab_download = st.tabs(["종합 대시보드", "학생 채점", "성적표 다운로드"])
    with tab_dashboard:
        render_teacher_dashboard(roster, portfolios)
    with tab_grade:
        render_teacher_grade(roster, portfolios)
    with tab_download:
        render_teacher_download(roster, portfolios)

    with st.expander("Google Sheets 연결 상태", expanded=False):
        st.caption("앱은 서비스 계정으로 학생명단 · 주차설정 · 포트폴리오 시트를 읽고 씁니다.")
        if st.button("데이터 캐시 새로고침"):
            invalidate_data_cache()
            st.rerun()


# ============================================================
# 초기화 / 메인
# ============================================================
def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    init_state()

    if not st.session_state.get("role"):
        render_login()
        return

    # 연결을 실제로 열어 초기 오류를 숨기지 않고 바로 안내합니다.
    try:
        config = _get_gsheets_config()
        spreadsheet_ref = config.get("spreadsheet") or config.get("spreadsheet_url") or config.get("spreadsheet_id")
        if not spreadsheet_ref:
            raise RuntimeError("[connections.gsheets]에 spreadsheet, spreadsheet_url 또는 spreadsheet_id를 설정하세요.")
        get_spreadsheet(str(spreadsheet_ref))
    except Exception as exc:
        st.error("Google Sheets 연결 설정을 확인해 주세요.")
        with st.expander("진단 정보"):
            st.code(str(exc))
        return

    if st.session_state["role"] == "student":
        render_student()
    elif st.session_state["role"] == "teacher":
        render_teacher()
    else:
        reset_session()


if __name__ == "__main__":
    main()
