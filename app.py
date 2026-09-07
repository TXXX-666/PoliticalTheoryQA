from __future__ import annotations

from html import escape

import streamlit as st

from qabank.config import Settings
from qabank.security import check_rate_limit, token_matches
from qabank.service import QuestionAnswerService, TYPE_LABELS


st.set_page_config(
    page_title="政治理论题库问答",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp { background: #f7f8fa; color: #17202a; }
    .block-container { max-width: 1120px; padding-top: 2rem; }
    [data-testid="stSidebar"] { background: #eef2f6; }
    .answer-title { color: #176b45; font-size: 1.3rem; font-weight: 700; }
    .answer-option { padding: .55rem 0; border-bottom: 1px solid #dfe5ea; }
    .meta { color: #52606d; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="正在加载题库...")
def load_service() -> QuestionAnswerService:
    return QuestionAnswerService()


settings = Settings.from_env()
if settings.require_auth and not settings.access_token:
    st.error("服务要求鉴权，但服务器尚未配置 QABANK_ACCESS_TOKEN。")
    st.stop()

if settings.require_auth and not st.session_state.get("authenticated"):
    st.title("政治理论题库问答")
    with st.form("login"):
        supplied = st.text_input("访问令牌", type="password")
        if st.form_submit_button("登录", type="primary"):
            if token_matches(settings.access_token, supplied):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("访问令牌不正确。")
    st.stop()

try:
    service = load_service()
except Exception as exc:
    st.error(f"题库初始化失败：{exc}")
    st.info("请将题库文件放到 source/question_bank.docx，并运行 python scripts/import_docx.py。")
    st.stop()

stats = service.stats()

with st.sidebar:
    st.header("题库状态")
    st.metric("题目总数", stats["question_count"])
    counts = stats["type_counts"]
    st.caption(
        f"单选 {counts.get('single_choice', 0)} · "
        f"多选 {counts.get('multiple_choice', 0)} · "
        f"判断 {counts.get('true_false', 0)}"
    )
    st.divider()
    candidate_count = st.slider("候选题数量", 3, 10, 5)
    show_details = st.toggle("显示检索详情", value=False)
    st.caption("精确匹配 + FTS5 + 模糊检索")
    if settings.require_auth and st.button("退出登录"):
        st.session_state.clear()
        st.rerun()

st.title("政治理论题库问答")

with st.form("question-form", clear_on_submit=False):
    query = st.text_area(
        "题目",
        key="question_input",
        height=150,
        max_chars=settings.max_query_chars,
        placeholder="粘贴完整题干，也可以连同 A/B/C/D 选项一起粘贴。",
    )
    submitted = st.form_submit_button("查找标准答案", type="primary")

if submitted:
    allowed, timestamps, retry_after = check_rate_limit(
        st.session_state.get("query_timestamps", []),
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    st.session_state["query_timestamps"] = timestamps
    if not allowed:
        st.warning(f"请求过于频繁，请在约 {retry_after} 秒后重试。")
    elif not query.strip():
        st.warning("请输入题目。")
    else:
        st.session_state["search_result"] = service.ask(
            query, limit=candidate_count
        )
        st.session_state.pop("selected_question_id", None)
        st.session_state.pop("candidate_question_id", None)


def render_answer(answer: dict) -> None:
    st.markdown(
        f'<div class="answer-title">题库答案：{escape(answer["answer"])}</div>',
        unsafe_allow_html=True,
    )
    if answer["answer_options"]:
        for option in answer["answer_options"]:
            st.markdown(
                f'<div class="answer-option"><strong>{option["letter"]}.</strong> '
                f'{escape(option["text"])}</div>',
                unsafe_allow_html=True,
            )
    st.markdown(
        f'<p class="meta">第 {answer["question_id"]} 题 · '
        f'{escape(answer["question_type_label"])} · {escape(answer["section"])}</p>',
        unsafe_allow_html=True,
    )
    with st.expander("查看完整题目与选项"):
        st.write(answer["question"])
        for letter, text in answer["options"].items():
            st.write(f"{letter}. {text}")


result = st.session_state.get("search_result")
if result:
    st.divider()
    if result["status"] == "no_match":
        st.warning(result["reason"])
    elif result["status"] == "ambiguous":
        st.warning(result["reason"])
        candidates = result["candidates"]
        selected_id = st.radio(
            "请选择你输入的原题",
            options=[item["question"]["id"] for item in candidates],
            key="candidate_question_id",
            format_func=lambda question_id: next(
                f'第 {item["question"]["id"]} 题 · '
                f'{item["question"]["question"][:90]}'
                for item in candidates
                if item["question"]["id"] == question_id
            ),
        )
        if st.button("确认并查看答案", type="primary"):
            st.session_state["selected_question_id"] = selected_id
        if st.session_state.get("selected_question_id"):
            selected_answer = service.answer_question_id(
                int(st.session_state["selected_question_id"])
            )
            if selected_answer:
                render_answer(selected_answer)
    else:
        render_answer(result["answer"])

    if show_details:
        with st.expander("检索诊断", expanded=True):
            st.json(
                {
                    "status": result["status"],
                    "reason": result["reason"],
                    "normalized_query": result["normalized_query"],
                    "candidates": [
                        {
                            "question_id": item["question"]["id"],
                            "score": round(item["score"], 4),
                            "method": item["match_method"],
                            "lexical": round(item["lexical_score"], 4),
                        }
                        for item in result["candidates"]
                    ],
                }
            )

st.divider()
st.caption("本系统用于题库检索和学习辅助。标准答案来自导入题库，不代表对题库内容进行事实核验。")
