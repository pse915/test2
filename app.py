import io
import zipfile
from pathlib import Path

import streamlit as st


# =========================================================
#  기술·가정 수업 OT 게임
#  AI Studio 스타일 UI를 Streamlit로 재구성한 단일 파일 버전
# =========================================================

st.set_page_config(
    page_title="기술·가정 수업 OT 게임",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# 기본 데이터
# -----------------------------
QUESTIONS = [
    {
        "q": "\"스마트폰으로 집안의 조명, 냉난방, 도어락을 원격 제어하는 '스마트홈'\"",
        "hint": "이것은 기술일까요, 가정일까요, 아니면 융합일까요?",
        "answer": "융합",
        "explain": "스마트홈은 센서·통신·제어 같은 기술과 주거·생활 방식이 결합된 사례입니다.",
    },
    {
        "q": "\"식품의 영양성분표를 비교해 우리 가족에게 맞는 식품을 고르는 활동\"",
        "hint": "어느 영역의 핵심 활동에 가까울까요?",
        "answer": "가정",
        "explain": "식생활과 가족의 건강·소비를 판단하는 활동으로 가정생활 영역과 관련이 깊습니다.",
    },
    {
        "q": "\"3D 프린터로 부서진 생활용품의 부품을 직접 설계해 다시 만드는 활동\"",
        "hint": "기술, 가정, 융합 중 하나를 골라 보세요.",
        "answer": "기술",
        "explain": "제품 설계와 제작, 문제 해결 과정이 중심이므로 기술 영역의 대표 사례로 볼 수 있습니다.",
    },
    {
        "q": "\"에너지 사용량을 앱으로 확인하고 가족이 전기 절약 계획을 세우는 활동\"",
        "hint": "기술과 생활이 함께 사용됩니다. 핵심 성격은?",
        "answer": "융합",
        "explain": "에너지 데이터를 측정·분석하는 기술과 가정의 생활 습관 변화가 함께 작동합니다.",
    },
    {
        "q": "\"옷의 소재와 세탁 방법을 확인하고 계절에 맞춰 의생활 계획을 세우는 활동\"",
        "hint": "생활 속 어떤 교과 영역에 더 가깝나요?",
        "answer": "가정",
        "explain": "의생활의 선택·관리·계획은 가정생활 영역의 중요한 내용입니다.",
    },
    {
        "q": "\"아두이노 센서를 이용해 교실의 온도와 습도를 자동으로 측정하는 장치 만들기\"",
        "hint": "제품을 설계하고 작동시키는 것이 핵심입니다.",
        "answer": "기술",
        "explain": "센서, 제어, 장치 설계와 제작을 직접 다루는 기술 중심 활동입니다.",
    },
    {
        "q": "\"가족회의에서 우리 집의 안전 문제를 찾고 IoT 기기로 개선 방법을 설계하는 활동\"",
        "hint": "두 영역이 결합된 사례입니다. 무엇일까요?",
        "answer": "융합",
        "explain": "가정의 문제를 발견하고 기술을 적용해 해결하므로 기술·가정의 융합 성격이 강합니다.",
    },
    {
        "q": "\"한 달 생활비를 정하고 식비·교통비·저축비의 우선순위를 정하는 활동\"",
        "hint": "생활 자원 관리와 관련된 영역을 생각해 보세요.",
        "answer": "가정",
        "explain": "가족의 자원 관리와 합리적인 소비 계획은 가정생활의 핵심 주제입니다.",
    },
    {
        "q": "\"태양광 패널을 설치할 장소를 정하고 가정의 전력 사용 패턴까지 분석하는 프로젝트\"",
        "hint": "기술적 해결과 생활 설계가 함께 들어 있습니다.",
        "answer": "융합",
        "explain": "에너지 기술과 실제 가정의 생활·자원 관리가 함께 연결된 융합형 프로젝트입니다.",
    },
    {
        "q": "\"간단한 목공 공구의 사용법을 익혀 책상 정리용 선반을 설계하고 제작하는 활동\"",
        "hint": "설계와 제작이 중심이라면 어디에 가까울까요?",
        "answer": "기술",
        "explain": "문제 해결을 위한 설계·제작과 공구 활용이 중심이므로 기술 영역의 활동입니다.",
    },
]

CHOICES = [
    ("기술", "🛠️", "Technology", "제조 · 건설 · 수송 · 정보통신"),
    ("가정", "🍲", "Home Ec.", "인간발달 · 식생활 · 의생활 · 주생활"),
    ("융합", "✨", "기술 + 가정", "첨단기술과 라이프스타일의 결합"),
]

MODULES = [
    ("1. 기술 vs 가정 분류", "🛠️"),
    ("2. 기-가 듀얼빌", "📖"),
    ("3. 생존 밸런스 로그", "⚖️"),
    ("4. 안전 수칙 & 리더십", "📋"),
    ("5. Streamlit GitHub 코드 & ZIP", "🛒"),
]


# -----------------------------
# 상태 초기화
# -----------------------------
defaults = {
    "module": 0,
    "question_index": 0,
    "score": 0,
    "answers": {},
    "selected": None,
    "show_result": False,
    "complete": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -----------------------------
# 디자인 CSS
# -----------------------------
st.markdown(
    """
<style>
/* ===== 전체 ===== */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
}
.stApp {
    background: #f7f8fb;
    color: #111827;
}
.block-container {
    max-width: 1080px;
    padding-top: 0.0rem;
    padding-bottom: 2.5rem;
}

/* Streamlit chrome 최소화 */
[data-testid="stSidebar"] { display: none; }
[data-testid="stHeader"] {
    background: transparent;
}
[data-testid="stToolbar"] {
    display: none;
}

/* ===== 상단 공지 바 ===== */
.top-banner {
    width: 100vw;
    margin-left: calc((100vw - 100%) / -2);
    min-height: 28px;
    background: linear-gradient(90deg, #ef001d 0%, #f40036 47%, #ee7600 100%);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: -0.02em;
    box-shadow: 0 1px 0 rgba(0,0,0,.04);
}
.top-banner .tag {
    padding: 3px 8px;
    border-radius: 6px;
    background: rgba(255,255,255,.16);
    border: 1px solid rgba(255,255,255,.22);
}
.top-banner .dot {
    opacity: .55;
}

/* ===== 브랜드 영역 ===== */
.brand-row {
    padding: 10px 0 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.brand-left {
    display: flex;
    align-items: center;
    gap: 9px;
}
.brand-logo {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    display: grid;
    place-items: center;
    background: #5142ea;
    color: white;
    font-size: 18px;
    font-weight: 800;
    box-shadow: 0 4px 12px rgba(81,66,234,.20);
}
.brand-title {
    font-size: 18px;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.045em;
}
.brand-sub {
    font-size: 10px;
    color: #98a2b3;
    margin-top: 1px;
    letter-spacing: -0.02em;
}
.badge {
    display: inline-block;
    margin-left: 6px;
    vertical-align: 2px;
    padding: 2px 6px;
    border: 1px solid #dbe3ff;
    border-radius: 999px;
    color: #5142ea;
    background: #f3f4ff;
    font-size: 9px;
    font-weight: 800;
}
.download-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
}

/* ===== nav ===== */
.nav-strip {
    border-top: 1px solid #e8ebf0;
    border-bottom: 1px solid #dfe5ed;
    padding: 3px 0 4px;
    margin-bottom: 18px;
}
.nav-note {
    text-align: right;
    font-size: 10px;
    color: #7d8797;
    margin-top: 2px;
}

/* Streamlit buttons */
.stButton > button, .stDownloadButton > button {
    border-radius: 8px !important;
    border: 1px solid #e0e5ee !important;
    background: #ffffff !important;
    color: #344054 !important;
    min-height: 30px !important;
    padding: 4px 10px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
    transition: all .16s ease !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #bfc8d8 !important;
    transform: translateY(-1px);
}
.stButton > button:focus {
    box-shadow: 0 0 0 2px rgba(81,66,234,.10) !important;
}

/* ===== 진행도 ===== */
.progress-shell {
    background: #ffffff;
    border: 1px solid #e2e7ef;
    border-radius: 13px;
    padding: 11px 13px 12px;
    box-shadow: 0 4px 12px rgba(16,24,40,.035);
    margin-bottom: 10px;
}
.progress-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}
.progress-pill {
    background: #eef2ff;
    color: #4f46e5;
    font-size: 10px;
    font-weight: 800;
    padding: 4px 7px;
    border-radius: 999px;
}
.score-label {
    color: #667085;
    font-size: 10px;
}
.score-number {
    color: #3f36c5;
    font-weight: 900;
}
.progress-track {
    height: 7px;
    border-radius: 999px;
    background: #edf0f5;
    overflow: hidden;
    margin-top: 11px;
}
.progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg,#5142ea,#6a60f2);
}

/* ===== 문제 카드 ===== */
.question-card {
    background: #ffffff;
    border: 1px solid #dfe4eb;
    border-radius: 15px;
    padding: 26px 25px 27px;
    box-shadow: 0 10px 24px rgba(16,24,40,.045);
}
.q-meta {
    text-align: center;
    color: #8a94a6;
    font-size: 10px;
    font-weight: 700;
}
.q-title {
    text-align: center;
    font-size: 20px;
    line-height: 1.38;
    font-weight: 800;
    color: #101828;
    margin: 7px auto 5px;
    letter-spacing: -0.055em;
}
.q-hint {
    text-align: center;
    color: #8c96a8;
    font-size: 10px;
    margin-bottom: 17px;
}
.choice-card {
    min-height: 96px;
    background: #fff;
    border: 1px solid #dde4ee;
    border-radius: 11px;
    padding: 13px 14px;
}
.choice-icon {
    width: 31px;
    height: 31px;
    display: inline-grid;
    place-items: center;
    border-radius: 8px;
    font-size: 17px;
    margin-bottom: 6px;
    background: #eff4ff;
}
.choice-title {
    color: #101828;
    font-weight: 800;
    font-size: 12px;
    line-height: 1.2;
}
.choice-en {
    color: #738096;
    font-size: 9px;
    margin-left: 2px;
}
.choice-desc {
    color: #8390a3;
    font-size: 9px;
    margin-top: 5px;
    line-height: 1.35;
}
.result-box {
    margin: 16px 0 0;
    border-radius: 11px;
    padding: 11px 13px;
    border: 1px solid #dbe4ff;
    background: #f7f8ff;
    color: #334155;
    font-size: 11px;
    line-height: 1.55;
}
.result-ok {
    color: #155eef;
    font-weight: 900;
}
.result-no {
    color: #d92d20;
    font-weight: 900;
}

/* ===== 모듈 콘텐츠 ===== */
.section-card {
    background: #ffffff;
    border: 1px solid #e1e6ee;
    border-radius: 14px;
    padding: 21px 22px;
    box-shadow: 0 8px 22px rgba(16,24,40,.035);
}
.section-title {
    font-size: 18px;
    font-weight: 850;
    letter-spacing: -0.05em;
    color: #101828;
}
.section-desc {
    font-size: 11px;
    color: #7b8799;
    line-height: 1.65;
    margin-top: 5px;
}
.mini-card {
    border: 1px solid #e3e8ef;
    border-radius: 11px;
    padding: 13px 14px;
    background: #fff;
    height: 100%;
}
.mini-card h4 {
    font-size: 12px;
    margin: 0 0 6px;
    color: #1d2939;
}
.mini-card p {
    font-size: 10px;
    color: #7a8798;
    line-height: 1.6;
    margin: 0;
}
.log-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #eef1f5;
    font-size: 10px;
}
.log-row:last-child { border-bottom: 0; }
.footer-note {
    margin-top: 19px;
    text-align: center;
    color: #9aa3b2;
    font-size: 9px;
}

/* ===== 완료 ===== */
.finish-card {
    text-align: center;
    padding: 34px 20px;
}
.finish-icon {
    font-size: 34px;
}
.finish-score {
    font-size: 32px;
    font-weight: 900;
    letter-spacing: -0.06em;
    color: #5142ea;
    margin-top: 5px;
}
.finish-text {
    color: #7b8798;
    font-size: 11px;
    margin: 5px 0 15px;
}

/* ===== 반응형 ===== */
@media (max-width: 760px) {
    .top-banner {
        font-size: 9px;
        gap: 5px;
    }
    .brand-title { font-size: 16px; }
    .question-card { padding: 21px 13px 22px; }
    .q-title { font-size: 16px; }
    .section-card { padding: 17px 14px; }
}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# 유틸
# -----------------------------
def build_deploy_zip() -> bytes:
    """현재 app.py + 최소 requirements.txt + README.md를 메모리에서 ZIP으로 생성."""
    app_path = Path(__file__)
    try:
        source = app_path.read_text(encoding="utf-8")
    except Exception:
        source = "# 현재 실행 중인 app.py를 읽지 못했습니다."

    requirements = "streamlit>=1.45,<2.0\n"
    readme = """# 기술·가정 수업 OT 게임

## Streamlit 배포
1. GitHub 저장소에 `app.py`와 `requirements.txt`를 업로드합니다.
2. Streamlit Community Cloud에서 저장소를 연결합니다.
3. Main file path를 `app.py`로 지정합니다.

이 앱은 외부 이미지·CDN 없이 동작하도록 구성되어 있습니다.
"""

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("app.py", source)
        zf.writestr("requirements.txt", requirements)
        zf.writestr("README.md", readme)
    mem.seek(0)
    return mem.getvalue()


def reset_game():
    st.session_state.question_index = 0
    st.session_state.score = 0
    st.session_state.answers = {}
    st.session_state.selected = None
    st.session_state.show_result = False
    st.session_state.complete = False


def answer_question(choice: str):
    idx = st.session_state.question_index
    if idx in st.session_state.answers:
        return

    correct = QUESTIONS[idx]["answer"]
    st.session_state.answers[idx] = choice
    st.session_state.selected = choice
    st.session_state.show_result = True

    if choice == correct:
        st.session_state.score += 10


def next_question():
    idx = st.session_state.question_index
    if idx < len(QUESTIONS) - 1:
        st.session_state.question_index += 1
        st.session_state.selected = None
        st.session_state.show_result = False
    else:
        st.session_state.complete = True


# -----------------------------
# 상단
# -----------------------------
st.markdown(
    """
<div class="top-banner">
    <span class="tag">ZIP 준비완료</span>
    <span>GitHub 업로드용 Streamlit 배포 패키지 (app.py + requirements.txt + README.md)</span>
</div>
""",
    unsafe_allow_html=True,
)

brand_cols = st.columns([0.82, 0.18], vertical_alignment="center")
with brand_cols[0]:
    st.markdown(
        """
<div class="brand-row">
  <div class="brand-left">
    <div class="brand-logo">기·가</div>
    <div>
      <div class="brand-title">
        기술·가정 수업 OT 게임
        <span class="badge">2026 오리엔테이션</span>
      </div>
      <div class="brand-sub">아이스브레이킹 게임 · GitHub 업로드용 Streamlit(app.py) 코드</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
with brand_cols[1]:
    st.download_button(
        "⬇ ZIP 다운로드",
        data=build_deploy_zip(),
        file_name="tech_home_ot_streamlit.zip",
        mime="application/zip",
        use_container_width=True,
        key="download_zip_top",
    )

# -----------------------------
# 상단 메뉴
# -----------------------------
st.markdown('<div class="nav-strip">', unsafe_allow_html=True)
nav_cols = st.columns(5, gap="small")
for i, (label, icon) in enumerate(MODULES):
    with nav_cols[i]:
        prefix = f"{icon} " if i == st.session_state.module else ""
        if st.button(
            prefix + label,
            key=f"module_{i}",
            use_container_width=True,
        ):
            st.session_state.module = i
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 모듈 1 : 핵심 게임
# -----------------------------
if st.session_state.module == 0:
    if st.session_state.complete:
        st.markdown(
            f"""
<div class="question-card finish-card">
  <div class="finish-icon">🎉</div>
  <div class="section-title">분류 게임 완료!</div>
  <div class="finish-score">{st.session_state.score}점</div>
  <div class="finish-text">
      10개의 상황을 기술·가정·융합으로 분류했습니다.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            if st.button("↻ 처음부터 다시 하기", use_container_width=True):
                reset_game()
                st.rerun()
    else:
        q_idx = st.session_state.question_index
        q = QUESTIONS[q_idx]
        total = len(QUESTIONS)
        progress = int(((q_idx + 1) / total) * 100)

        st.markdown(
            f"""
<div class="progress-shell">
  <div class="progress-top">
    <span class="progress-pill">진행도: {q_idx + 1}/{total}</span>
    <span class="score-label">현재 점수: <span class="score-number">{st.session_state.score}점</span></span>
  </div>
  <div class="progress-track">
    <div class="progress-fill" style="width:{progress}%"></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
<div class="question-card">
  <div class="q-meta">문제 #{q_idx + 1} · 일상 속 분야 맞히기</div>
  <div class="q-title">{q["q"]}</div>
  <div class="q-hint">{q["hint"]}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        # 실제 클릭 가능한 선택 영역
        choice_cols = st.columns(3, gap="small")
        for col, (label, icon, en, desc) in zip(choice_cols, CHOICES):
            with col:
                st.markdown(
                    f"""
<div class="choice-card">
  <div class="choice-icon">{icon}</div>
  <div class="choice-title">{label} <span class="choice-en">({en})</span></div>
  <div class="choice-desc">{desc}</div>
</div>
""",
                    unsafe_allow_html=True,
                )
                already = q_idx in st.session_state.answers
                button_label = "선택됨" if already and st.session_state.answers[q_idx] == label else "선택"
                if st.button(
                    button_label,
                    key=f"choice_{q_idx}_{label}",
                    use_container_width=True,
                    disabled=already,
                ):
                    answer_question(label)
                    st.rerun()

        if st.session_state.show_result:
            selected = st.session_state.selected
            correct = q["answer"]
            is_correct = selected == correct

            st.markdown(
                f"""
<div class="result-box">
  <span class="{'result-ok' if is_correct else 'result-no'}">
      {"정답입니다! +10점" if is_correct else f"아쉬워요 · 정답은 {correct}"}
  </span>
  &nbsp; {q["explain"]}
</div>
""",
                unsafe_allow_html=True,
            )

            st.write("")
            nav_c1, nav_c2, nav_c3 = st.columns([1, 1, 1])
            with nav_c2:
                next_label = "마지막 결과 보기" if q_idx == total - 1 else "다음 문제 →"
                if st.button(next_label, use_container_width=True, type="primary"):
                    next_question()
                    st.rerun()

        st.markdown(
            '<div class="footer-note">선택 → 결과 확인 → 다음 문제 · 모든 점수는 현재 브라우저 세션에서만 유지됩니다.</div>',
            unsafe_allow_html=True,
        )


# -----------------------------
# 모듈 2
# -----------------------------
elif st.session_state.module == 1:
    st.markdown(
        """
<div class="section-card">
  <div class="section-title">📖 2. 기-가 듀얼빌</div>
  <div class="section-desc">
    기술적 문제 해결과 생활 속 의사결정을 하나의 프로젝트로 연결해 보는 미니 활동입니다.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    a, b = st.columns(2, gap="small")
    with a:
        st.markdown(
            """
<div class="mini-card">
  <h4>🛠️ 기술 미션</h4>
  <p>교실 또는 집에서 불편한 문제 하나를 발견하고, 센서·제품·공간·정보를 활용한 해결 아이디어를 한 문장으로 만들어 보세요.</p>
</div>
""",
            unsafe_allow_html=True,
        )
    with b:
        st.markdown(
            """
<div class="mini-card">
  <h4>🍲 가정 미션</h4>
  <p>같은 문제를 가족의 생활 습관, 시간, 비용, 안전, 관계의 관점에서 다시 정의해 보세요.</p>
</div>
""",
            unsafe_allow_html=True,
        )
    st.write("")
    idea = st.text_area(
        "나의 융합 아이디어",
        placeholder="예) 전력 사용량을 보여 주는 가족용 대시보드를 만들고, 주간 절약 규칙을 함께 정한다.",
        height=110,
        key="dual_build_text",
    )
    if st.button("💡 아이디어 저장", type="primary", use_container_width=True):
        if idea.strip():
            st.success("아이디어를 현재 세션에 저장했습니다.")
        else:
            st.warning("한 문장 정도의 아이디어를 입력해 주세요.")


# -----------------------------
# 모듈 3
# -----------------------------
elif st.session_state.module == 2:
    st.markdown(
        """
<div class="section-card">
  <div class="section-title">⚖️ 3. 생존 밸런스 로그</div>
  <div class="section-desc">
    생활 문제를 해결할 때 기술의 편리함만 보지 않고 비용·시간·안전·환경까지 함께 점검합니다.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    log_data = [
        ("편리성", "기술이 시간을 줄여 주는가?", "높음"),
        ("비용", "도입·유지 비용을 감당할 수 있는가?", "보통"),
        ("안전", "오작동 또는 잘못된 사용에 대한 대비가 있는가?", "필수"),
        ("지속가능성", "에너지와 자원을 적절하게 사용하는가?", "확인"),
    ]
    for title, question, tag in log_data:
        st.markdown(
            f"""
<div class="log-row">
  <span><b>{title}</b> · {question}</span>
  <span style="color:#5142ea;font-weight:800">{tag}</span>
</div>
""",
            unsafe_allow_html=True,
        )


# -----------------------------
# 모듈 4
# -----------------------------
elif st.session_state.module == 3:
    st.markdown(
        """
<div class="section-card">
  <div class="section-title">📋 4. 안전 수칙 & 리더십</div>
  <div class="section-desc">
    실습과 프로젝트에서는 '잘 만드는 것'뿐 아니라 안전하게 협업하고 책임 있게 사용하는 과정이 중요합니다.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    rules = [
        ("01", "공구·전기·가열 기구를 사용하기 전 사용법과 위험요소를 먼저 확인합니다."),
        ("02", "역할을 나누되, 위험 작업은 담당자와 확인자를 함께 정합니다."),
        ("03", "실패한 결과도 기록하고 다음 설계에 반영합니다."),
        ("04", "다른 사람의 생활 문제를 해결할 때 개인정보와 안전을 우선합니다."),
    ]
    for num, text_ in rules:
        left, right = st.columns([0.12, 0.88], gap="small")
        with left:
            st.markdown(
                f"<div style='font-weight:900;color:#5142ea;font-size:15px;padding-top:7px'>{num}</div>",
                unsafe_allow_html=True,
            )
        with right:
            st.markdown(
                f"""
<div class="mini-card" style="padding:10px 13px;margin-bottom:7px">
  <p style="font-size:10px;color:#344054">{text_}</p>
</div>
""",
                unsafe_allow_html=True,
            )


# -----------------------------
# 모듈 5
# -----------------------------
else:
    st.markdown(
        """
<div class="section-card">
  <div class="section-title">🛒 5. Streamlit GitHub 코드 & ZIP</div>
  <div class="section-desc">
    이 페이지의 게임은 외부 이미지나 CDN 없이 단일 <b>app.py</b>로 동작하도록 구성했습니다.
    GitHub에 올린 뒤 Streamlit Community Cloud에서 바로 실행할 수 있습니다.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")

    st.markdown(
        """
<div class="mini-card">
  <h4>배포 구조</h4>
  <p>
  GitHub 저장소<br>
  ├─ <b>app.py</b> · 게임 본체<br>
  ├─ <b>requirements.txt</b> · Streamlit 의존성<br>
  └─ <b>README.md</b> · 배포 안내
  </p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.write("")
    st.download_button(
        "⬇ Streamlit 배포 ZIP 만들기",
        data=build_deploy_zip(),
        file_name="tech_home_ot_streamlit.zip",
        mime="application/zip",
        use_container_width=True,
        key="download_zip_bottom",
    )

    st.info(
        "Streamlit Cloud에서는 GitHub 저장소를 연결한 뒤 Main file path를 app.py로 지정하면 됩니다."
    )

# -----------------------------
# 아주 작은 하단 표시
# -----------------------------
st.markdown(
    "<div style='height:8px'></div><div class='footer-note'>Tech · Home Economics · Orientation Game</div>",
    unsafe_allow_html=True,
)
