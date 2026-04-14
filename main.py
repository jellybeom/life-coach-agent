# import
import asyncio
import dotenv
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

# .env 가져오기
dotenv.load_dotenv()

# Main Agent
if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life coach agent",
        instructions="""
            당신은 따뜻하고 에너지 넘치는 라이프 코치입니다. 10년 이상 다양한 사람들의 목표 달성을 도와온 경험을 가지고 있습니다. 당신의 역할은 유저가 스스로의 잠재력을 발견하고, 원하는 삶을 향해 한 걸음씩 나아갈 수 있도록 안내하고 격려하는 것입니다.

            당신의 핵심 신념: 모든 사람은 이미 필요한 힘을 가지고 있습니다. 당신의 역할은 그 힘을 유저 스스로 발견하도록 돕는 것입니다.

            ---

            당신은 좋은 좋은 도구를 가지고 있습니다.
            - Web Search Tool

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
        """,
        tools=[WebSearchTool()],
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
        if "type" in message and message["type"] == "web_search_call":
            with st.chat_message("assistant"):
                st.write(f'[ 웹 검색 : "{message["action"]["query"]}" ]')


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

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response)


# 메모리 히스토리 그리기
asyncio.run(paint_history())

# Chat Input 입력
prompt = st.chat_input("무엇을 도와드릴까요?")
if prompt:
    with st.chat_message("user"):
        st.write(prompt)
    asyncio.run(run_agent(prompt))

# 사이드바 / 메모리
with st.sidebar:
    reset = st.button("Reset memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
