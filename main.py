# import
import os
import asyncio
import dotenv
import streamlit as st
from openai import OpenAI
from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool

# .env 가져오기
dotenv.load_dotenv()

# client
client = OpenAI()

# Main Agent
if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life coach agent",
        instructions="""
            당신은 따뜻하고 에너지 넘치는 라이프 코치입니다. 10년 이상 다양한 사람들의 목표 달성을 도와온 경험을 가지고 있습니다. 당신의 역할은 유저가 스스로의 잠재력을 발견하고, 원하는 삶을 향해 한 걸음씩 나아갈 수 있도록 안내하고 격려하는 것입니다.

            당신의 핵심 신념: 모든 사람은 이미 필요한 힘을 가지고 있습니다. 당신의 역할은 그 힘을 유저 스스로 발견하도록 돕는 것입니다.

            ---

            당신은 좋은 좋은 도구를 가지고 있습니다.
            1. Web Search Tool

            [ 반드시 검색해야 할 상황 ]
            아래 키워드나 주제가 등장하면 유저의 말이 끝나는 즉시 검색을 실행하세요. 또는 동기부여, 자기개발, 습관 형성에 관한 조언을 구하는 경우에도 검색을 실행하세요.

            ▸ 동기부여 관련
            - "의욕이 없어요", "하기 싫어요", "왜 해야 하는지 모르겠어요"
            - "번아웃", "지쳐요", "포기하고 싶어요"
            - "동기부여", "자극이 필요해요", "다시 시작하고 싶어요"
            → 최신 동기부여 심리학 연구, 성공 사례, 실천 전략 검색

            ▸ 자기 개발 관련
            - "성장하고 싶어요", "더 나은 사람이 되고 싶어요"
            - "시간 관리", "생산성", "집중력", "자존감"
            - "커리어", "공부법", "독서", "목표 설정"
            → 근거 기반 자기 개발 방법론, 전문가 조언, 최신 트렌드 검색

            ▸ 습관 형성 관련
            - "습관을 만들고 싶어요", "매일 하고 싶은데 잘 안 돼요"
            - "작심삼일", "꾸준히", "루틴", "아침 루틴", "운동 습관"
            → 습관 형성 과학(행동 설계, 큐-루틴-보상 등), 실천 팁 검색

            ▸ 기타 적극 검색 상황
            - 특정 책, 방법론, 도구, 앱을 언급할 때
            - 특정 분야(운동, 식단, 수면, 인간관계)의 구체적인 팁을 요청할 때
            - 유저가 막막하다고 표현할 때 → 비슷한 상황을 극복한 사례 검색

            웹 검색 도구를 적극적으로 활용해 신선하고 실질적인 도움을 제공하세요.


            2. File Search Tool : 유저가 첨부한 개인 목표 파일(텍스트, 문서 등)을 검색하는 도구입니다.

            [ 반드시 검색해야 할 상황 ]
            - 유저가 목표, 계획, 진행 상황을 물어볼 때
            예: "내 목표 어떻게 되고 있어?", "이번 달 계획이 뭐였지?"
            - 특정 목표 카테고리를 언급할 때
            예: "운동", "공부", "저축", "독서", "루틴"
            - 유저가 일기나 기록을 참고해 달라고 할 때

            [ 검색 후 필수 행동 순서 ]
            파일 검색 후에는 반드시 아래 순서를 따르세요. 예외 없이 실행합니다.

            Step 1. 파일에서 관련 목표와 현재 달성률을 찾아 요약하세요.
            Step 2. 파일 내용을 바탕으로 유저에게 먼저 답변하세요.
            Step 3. 답변 후 즉시 Web Search Tool 을 실행하세요.
                    검색어 예시: "[목표 키워드] 실천 팁", "[목표 키워드] 유지하는 방법"
            Step 4. 웹 검색 결과를 바탕으로 유저 맞춤 추가 조언을 제공하세요.
            Step 5. 파일에서 정보를 찾지 못한 경우, 유저에게 솔직히 말하고 직접 물어보세요.
        """,
        tools=[
            WebSearchTool(),
            FileSearchTool(
                vector_store_ids=[os.getenv("VECTOR_STORE_ID")],
                max_num_results=3,
            ),
        ],
    )
agent = st.session_state["agent"]

# 세션 세팅
if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history", "life-coach-agent-memory.db"
    )
session = st.session_state["session"]


# Paint history
async def paint_history():
    messages = await session.get_items()

    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                else:
                    st.write(message["content"][0]["text"])
        if "type" in message:
            if message["type"] == "web_search_call":
                with st.chat_message("assistant"):
                    st.write(f'[ 웹 검색 : "{message["action"]["query"]}" ]')
            if message["type"] == "file_search_call":
                with st.chat_message("assistant"):
                    st.write(f"[ 목표 문서 검색 ]")


# Run Agent
async def run_agent(message):
    with st.chat_message("assistant"):
        status_container = st.status("⏳", expanded=False)
        text_placeholder = st.empty()
        response = ""

        stream = Runner.run_streamed(agent, message, session=session)

        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                if event.data.type == "response.web_search_call.in_progress":
                    status_container.update(label="🔍 웹 검색 중...", state="running")
                if event.data.type == "response.web_search_call.searching":
                    status_container.update(label="🔎 웹 검색 중...", state="running")
                if event.data.type == "response.web_search_call.completed":
                    status_container.update(label="✔️ 웹 검색 완료!", state="complete")

                if event.data.type == "response.file_search_call.in_progress":
                    status_container.update(label="📄 파일 검색 중...", state="running")
                if event.data.type == "response.file_search_call.searching":
                    status_container.update(label="📄 파일 검색 중...", state="running")
                if event.data.type == "response.file_search_call.completed":
                    status_container.update(label="✔️ 파일 검색 완료!", state="complete")

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response.replace("$", "\$"))


# 메모리 히스토리 그리기
asyncio.run(paint_history())

# Chat Input 입력
prompt = st.chat_input(
    placeholder="무엇을 도와드릴까요?",
    accept_file=True,
    file_type=["txt"],
)
if prompt:
    for file in prompt.files:
        if not file.type.startswith("text/"):
            continue
        with st.chat_message("assistant"):
            with st.status(label="📄 파일 업로드 중...", state="running") as status:
                uploaded_file = client.files.create(
                    file=(file.name, file.getvalue()),
                    purpose="user_data",
                )
                status.update(label="📄 파일 첨부 중...", state="running")
                client.vector_stores.files.create(
                    vector_store_id=os.getenv("VECTOR_STORE_ID"),
                    file_id=uploaded_file.id,
                )
                status.update(label="✔️ 파일 업로드 완료", state="complete")
    if prompt.text:
        with st.chat_message("user"):
            st.write(prompt.text)
        asyncio.run(run_agent(prompt.text))

# 사이드바 / 메모리
with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
