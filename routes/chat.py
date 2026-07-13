"""P0: AI 智能助教 — WebSocket 对话接口"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Optional
import json
import logging

from ..deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["AI助教"])

# 对话历史管理（内存中，生产环境应使用Redis）
class ChatSession:
    def __init__(self, user_id: int, subject_id: str = "math"):
        self.user_id = user_id
        self.subject_id = subject_id
        self.history: list[dict] = []
        self.max_history = 20

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_context(self) -> list[dict]:
        system_prompt = {
            "role": "system",
            "content": "你是一位耐心的高考数学辅导老师。请根据学生的提问，"
                       "给出清晰的讲解。始终用中文回答。"
                       "如果学生问的是知识点概念，先解释定义，再举例说明。"
                       "如果学生问的是解题方法，分步骤讲解，并给出类似的练习题。"
                       "鼓励学生独立思考，不要直接给答案。"
        }
        return [system_prompt] + self.history[-10:]


# 会话管理器
_sessions: dict[str, ChatSession] = {}


def _get_session(user_id: int, session_id: Optional[str] = None) -> tuple[str, ChatSession]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    sid = f"user_{user_id}_{len(_sessions)}"
    _sessions[sid] = ChatSession(user_id)
    return sid, _sessions[sid]


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket 对话 — AI 智能助教"""
    await websocket.accept()
    session_id = None
    try:
        # 认证
        auth_msg = await websocket.receive_json()
        user_id = auth_msg.get("user_id", 0)
        subject_id = auth_msg.get("subject_id", "math")
        session_id, session = _get_session(user_id)

        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "你好！我是你的AI助教，有什么学习问题吗？"
        })

        while True:
            data = await websocket.receive_json()
            user_msg = data.get("message", "").strip()
            if not user_msg:
                continue

            session.add_message("user", user_msg)

            # 尝试调用LLM，失败时使用模板回复
            try:
                import openai
                client = openai.AsyncOpenAI()
                resp = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=session.get_context(),
                    temperature=0.5,
                    max_tokens=1024,
                )
                reply = resp.choices[0].message.content or "抱歉，我没理解你的问题。能换个方式问吗？"
            except Exception:
                # LLM不可用时的降级回复
                kp_keywords = {
                    "函数": "函数是描述变量之间对应关系的规则。例如 f(x)=x² 就是一个函数。"
                            "我建议你先复习函数的基本概念，然后再看具体题型。",
                    "导数": "导数描述函数在某一点的变化率。比如速度是位移的导数。"
                            "你具体遇到了哪类导数问题？",
                    "三角": "三角函数包括 sin、cos、tan 等。它们在描述周期性现象时非常有用。"
                            "你可以先记住基本的诱导公式。",
                    "向量": "向量是有大小和方向的量。平面向量可以用坐标表示。"
                            "你是在做向量运算还是向量证明题？",
                    "概率": "概率描述事件发生的可能性。古典概型中 P(A) = 有利结果数/总结果数。"
                            "你可以试试先做几道基础概率题。",
                    "数列": "数列是按一定顺序排列的一列数。等差数列和等比数列是两种基本类型。"
                            "你掌握了通项公式和求和公式吗？",
                }
                reply = "这个问题我需要想一想。"
                for kw, answer in kp_keywords.items():
                    if kw in user_msg:
                        reply = answer
                        break
                if reply == "这个问题我需要想一想。":
                    reply = ("很好的问题！我建议你先回顾相关知识点的基础概念，"
                             "然后尝试做几道典型例题。如果还有具体疑问，可以继续问我。")

            session.add_message("assistant", reply)
            await websocket.send_json({
                "type": "message",
                "content": reply,
                "history_length": len(session.history),
            })

    except WebSocketDisconnect:
        logger.info(f"Chat WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


@router.post("/message")
async def send_message(
    message: str,
    session_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """HTTP 方式发送消息（非WebSocket场景）"""
    _, session = _get_session(user["id"], session_id)
    session.add_message("user", message)
    try:
        import openai
        client = openai.AsyncOpenAI()
        resp = await client.chat.completions.create(
            model="deepseek-chat",
            messages=session.get_context(),
            temperature=0.5,
            max_tokens=1024,
        )
        reply = resp.choices[0].message.content or ""
    except Exception:
        reply = f"已收到你的问题：「{message[:50]}」。当前LLM服务暂不可用，请稍后重试。"
    session.add_message("assistant", reply)
    return {
        "reply": reply,
        "session_id": session_id or f"user_{user['id']}_{len(_sessions)}",
    }


@router.get("/history/{session_id}")
async def get_chat_history(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """获取对话历史"""
    session = _sessions.get(session_id)
    if not session:
        return {"history": []}
    return {"history": session.history[-20:]}
