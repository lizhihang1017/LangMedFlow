from typing import List, Dict, Optional, Any, TypedDict, Annotated
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    定义整个 Agent 系统共享的状态 (State)。
    LangGraph 中的所有节点都会读取并更新这个状态。
    """

    # messages: 保存整个对话历史。
    # Annotated[..., operator.add] 意味着每次节点返回新的 messages 时，会自动追加到列表末尾，而不是覆盖。
    # 这对多轮对话至关重要。
    messages: Annotated[List[BaseMessage], operator.add]

    # --- SFMSS 特有的上下文信息 ---

    # 患者相关信息
    patient_profile: Dict[str, Any]  # 包含姓名、年龄、病史、性格等静态画像
    patient_scene: str  # 患者当前的场景描述
    patient_disc: str  # 患者的沟通风格描述

    # 导诊护士相关信息
    nurse_department: str  # 护士负责的正确科室（用于评估）
    nurse_turn_count: int  # 护士当前的轮次计数

    # 监督者相关信息
    # 监督者对信息收集完整性的评估
    supervisor_feedback: Optional[str]
    # 监督者是否认为信息已经足够
    info_enough: bool
    # 监督者对下一轮对话的建议
    next_step_suggestion: Optional[str]
    # 监督者对整体对话质量的监控建议
    monitor_suggestion: Optional[str]

    # 当前阶段控制
    current_phase: str  # 当前所处的阶段（如：症状询问、科室推荐等）
    is_finished: bool  # 标志对话是否结束

    # 错误处理
    error: Optional[str]

    # --- 新增：复刻原项目所需的状态 ---
    chat_text: List[str]  # 纯文本格式的对话历史（原项目 agents.py 中的 self.chat_text）
    collected_knowledge: List[dict]  # DialogueLLM 收集到的已知信息列表

    # 统计信息
    input_token_p: int
    output_token_p: int
    input_token_n: int
    output_token_n: int
    input_token_s: int
    output_token_s: int
    input_token_i: int  # DialogueLLM
    output_token_i: int

    # 记录最终要保存的结构化数据
    save_chat: Dict[str, Any]
