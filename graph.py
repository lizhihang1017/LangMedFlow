from langgraph.graph import StateGraph, END, START
from state import AgentState
from nodes import patient_node, nurse_node, supervisor_node
from langgraphics import watch

def should_continue(state: AgentState) -> str:
    """
    条件边路由函数 (Conditional Edge Routing Function)
    决定 Supervisor 执行完后，是继续让 Nurse 回复，还是结束整个对话图。
    对应原项目中 while not end and turn < 10 的逻辑。
    """
    # 如果患者决定结束对话
    if state.get("is_finished", False):
        return "end"

    # 如果对话轮次达到上限（原项目是 < 10，所以达到 10 就结束）
    if state.get("nurse_turn_count", 1) >= 10:
        return "end"

    # 否则继续由护士回复
    return "continue"


def build_graph() -> StateGraph:
    """
    构建并编译 LangGraph 的状态图。
    """
    # 1. 初始化图，并指定状态的类型
    workflow = StateGraph(AgentState)

    # 2. 添加节点 (Nodes)
    # 将我们在 nodes.py 中定义的函数注册为图中的节点
    workflow.add_node("patient", patient_node)
    workflow.add_node("nurse", nurse_node)
    workflow.add_node("supervisor", supervisor_node)

    # 3. 定义边 (Edges) - 即流程的流转方向

    # 图启动后，首先进入 Patient 节点
    # （我们在初始化 state 时，会放入护士的第一句问候，所以患者先反应）
    workflow.add_edge(START, "patient")

    # 患者说完话后，交由 Supervisor 进行信息提取和评估
    workflow.add_edge("patient", "supervisor")

    # Supervisor 评估完后，需要进行条件判断
    workflow.add_conditional_edges(
        "supervisor",  # 起始节点
        should_continue,  # 路由函数
        {
            "continue": "nurse",  # 如果函数返回 "continue"，则走向 nurse 节点
            "end": END  # 如果函数返回 "end"，则结束图的执行
        }
    )

    # 护士回复完后，交回给患者，形成循环
    workflow.add_edge("nurse", "patient")

    # 4. 编译图
    app = workflow.compile()

    return app
