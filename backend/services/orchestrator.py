"""九个维度角色 + 总控的话术生成。

纯逻辑模块：不算耗时、不发请求、不 sleep。之前这里混着 time.sleep(0.3)，
节奏控制不该由内容生成模块负责（压测时不该被这里拖住），
现在统一交给 services/pipeline.py 按阶段控制。
"""
from backend.schemas import DimensionDraft

DIMENSIONS = ["后勤", "评价", "方案", "成果", "资源", "执行", "安全", "课程", "研学"]
FIVE_FOCUS = ["目标定位", "资源组织", "执行路径", "风险与安全", "评估与成果"]
MASTER_AGENT = "总控"


def generate_five_focus_drafts(question: str, retrieval: list) -> list:
    """基于检索片段生成五维草案。"""
    context = "；".join([item.get("snippet", "") for item in retrieval]) or "暂无外部片段"
    return [
        DimensionDraft(
            name=focus,
            draft=f"[{focus}] 针对“{question}”，结合检索信息（{context}），输出优先策略、实施动作、验收标准。",
        )
        for focus in FIVE_FOCUS
    ]


def build_chat_round_1(question: str, five_drafts: list) -> list:
    """第一轮：总控开场 + 九个维度各表态。"""
    messages = [{"agent": MASTER_AGENT, "content": f"收到用户问题：{question}。请九位同事基于草案给出观点。"}]
    for idx, dimension in enumerate(DIMENSIONS):
        ref = five_drafts[idx % len(five_drafts)]
        messages.append(
            {
                "agent": dimension,
                "content": f"我从{dimension}视角补充：优先落地“{ref.name}”，并在本维度形成可执行清单。",
            }
        )
    return messages


def build_chat_round_2(five_drafts: list) -> tuple:
    """第二轮：总控做二次调和，产出最终综合方案。"""
    messages = [{"agent": MASTER_AGENT, "content": "二次协同开始：我将合并冲突并做统一取舍。"}]

    for dimension in DIMENSIONS:
        messages.append({"agent": dimension, "content": "同意合并结果，可进入实施。"})

    final_solution = (
        "综合执行方案\n"
        + "\n".join([f"- {item.name}: {item.draft}" for item in five_drafts])
        + "\n- 统一原则: 安全优先、资源复用、执行可追踪、过程可评价、成果可传播。"
    )
    return messages, final_solution
