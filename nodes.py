import json
import os
import random
import tiktoken
from typing import Dict, Any, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from system_prompt import (
    SYSTEM_PROMPT_J_D, SYSTEM_PROMPT_D, SYSTEM_PROMPT_D_2, NURSE_PHASE,
    SYSTEM_PROMPT_J_P, SYSTEM_PROMPT_P_C, SYSTEM_PROMPT_S_C, SYSTEM_PROMPT_P, PATIENT_PHASE,
    SYSTEM_PROMPT_M, SYSTEM_PROMPT_M_B,
    SYSTEM_PROMPT_DIALOGUE
)
from state import AgentState
from data_process import calculate_tokens

# ==========================================
# 配置加载与工具函数
# ==========================================

CONFIG_PATH = os.path.join(os.getcwd(), "config", "agent_config.json")


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


agent_config = load_config()


def get_llm(role_name, temperature=0.7):
    config = agent_config.get(role_name)
    if not config:
        raise ValueError(f"Role {role_name} not found in config")
    return ChatOpenAI(
        model=config['model_name'],
        api_key=config['api_key'],
        base_url=config['base_url'],
        temperature=temperature
    )

def parse_json_response(content: str) -> dict:
    """处理大模型返回的带有 markdown 标记的 JSON"""
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


# ==========================================
# Patient Node 逻辑
# ==========================================

def patient_node(state: AgentState) -> dict:
    """复刻原 Patient 类的 phase_judge 和 chat 逻辑"""

    patient_profile = state['patient_profile']
    chat_text_list = state.get('chat_text', [])
    messages = state.get('messages', [])

    input_token_inc = 0
    output_token_inc = 0

    llm = get_llm("Patient", temperature=0.7)

    # 1. 判断阶段 (Phase Judge)
    chat_text_str = ''.join(chat_text_list)
    judge_input = f"<导诊对话>：{chat_text_str}\n\n<患者的基本情况>：{patient_profile['chief_complaint']}\n\n<患者的沟通风格>：{state['patient_disc']}"

    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT_J_P + "\n请以JSON格式输出，字段包含action。"),
            HumanMessage(content=judge_input)
        ])
        data = parse_json_response(response.content)
        phase = data.get('action', '问题提出')

    except Exception as e:
        print(f"Patient phase_judge error: {e}")
        phase = "问题提出"
        response = None

    input_token_inc += calculate_tokens(SYSTEM_PROMPT_J_P + judge_input)
    if response:
        output_token_inc += calculate_tokens(response.content)

    function = PATIENT_PHASE.get(phase, "提出相关问题")

    # 2. 随机无关话题逻辑 (复刻原项目)
    if random.random() < 0.1 and phase not in ['结束对话', '需求提出', '提及无关话题']:
        phase = '提及无关话题'
        function = PATIENT_PHASE[phase]

    # 3. 生成回复 (Chat)
    # 获取导诊人员最新一次输入
    last_nurse_input = "您好，有什么可以帮你的吗？"
    if messages and isinstance(messages[-1], AIMessage):
        last_nurse_input = messages[-1].content

    system_prompt = SYSTEM_PROMPT_P.format(**patient_profile, scene=state['patient_scene'],
                                           patient_disc=state['patient_disc'])
    input_prompt = f'''<导诊人员的最新一次输入>：{last_nurse_input}\n<你应采取的行动>：{phase}，需要{function}\n\n<你的沟通风格>：{state['patient_disc']}'''

    chat_response = llm.invoke(
        [SystemMessage(content=system_prompt)] + messages + [HumanMessage(content=input_prompt)]
    )
    response_text = chat_response.content

    input_token_inc += calculate_tokens(system_prompt + input_prompt)
    output_token_inc += calculate_tokens(response_text)
    for msg in messages:
        input_token_inc += calculate_tokens(msg.content)

    # 更新 chat_text
    new_chat_text = chat_text_list + [f"患者：{response_text}\n"]

    return {
        "messages": [HumanMessage(content=response_text)],
        "chat_text": new_chat_text,
        "current_phase": phase,
        "is_finished": phase == "结束对话",
        "input_token_p": state.get('input_token_p', 0) + input_token_inc,
        "output_token_p": state.get('output_token_p', 0) + output_token_inc
    }


# ==========================================
# Nurse Node 逻辑
# ==========================================

def nurse_node(state: AgentState) -> dict:
    """复刻原 Nurse 类的 phase_judge 和 chat 逻辑"""

    chat_text_list = state.get('chat_text', [])
    messages = state.get('messages', [])
    suggestion = state.get('next_step_suggestion')
    suggestion2 = state.get('monitor_suggestion')
    info_enough = state.get('info_enough', False)
    turn = state.get('nurse_turn_count', 1)

    input_token_inc = 0
    output_token_inc = 0

    llm = get_llm("Nurse", temperature=0.7)

    # 获取患者最新一次输入
    last_patient_input = ""
    if messages and isinstance(messages[-1], HumanMessage):
        last_patient_input = messages[-1].content

    # 1. 判断阶段
    chat_text_str = ''.join(chat_text_list)
    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT_J_D + "\n请严格以JSON格式输出，字段包含action。"),
            HumanMessage(content=chat_text_str)
        ])
        data = parse_json_response(response.content)
        phase = data.get('action', '其他问题回复')
    except Exception as e:
        print(f"Nurse phase_judge error: {e}")
        phase = '其他问题回复'
        response = None

    input_token_inc += calculate_tokens(chat_text_str + SYSTEM_PROMPT_J_D)
    if response:
        output_token_inc += calculate_tokens(response.content)

    function = NURSE_PHASE.get(phase, "回复患者问题")

    # 原代码逻辑：如果推荐科室但信息不足且 turn < 2，则强制使用 supervisor 的 action
    if phase == '推荐科室' and not info_enough and turn < 2:
        # 这里需要从 supervisor state 里获取 action，但当前 state 只存了 suggestion 字符串
        # 为了完美复刻，我们在 supervisor 里也把 action 存下来，或者这里强制转为 症状询问
        phase = state.get('supervisor_action', '症状询问')
        function = NURSE_PHASE.get(phase, "回复患者问题")
        # 强制 turn + 1 (在原代码中 self.turn += 1，这里不直接改 state 的 turn，只是逻辑上知道这是强制的)

    # 2. 生成回复
    system_prompt = SYSTEM_PROMPT_D
    input_prompt = f"<患者最新一次输入>：{last_patient_input}\n<你当前应该采取的行动>：{phase}，{function}"

    if phase in ['推荐科室', '提供快速帮助', '结束阶段']:
        system_prompt = SYSTEM_PROMPT_D_2.format(department=state.get('nurse_department', '全科医学科'))
    else:
        if suggestion2:
            input_prompt = f"<患者最新一次输入>：{last_patient_input}\n<你当前应该采取的行动>：{phase}，{function}\n<对导诊询问策略和语气的监督建议>：{suggestion2}。\n"
        if suggestion:
            input_prompt += f"\n<对下一步症状和病史询问的监督建议>：{suggestion}"

    chat_response = llm.invoke(
        [SystemMessage(content=system_prompt)] + messages + [HumanMessage(content=input_prompt)]
    )
    response_text = chat_response.content

    input_token_inc += calculate_tokens(system_prompt + input_prompt)
    output_token_inc += calculate_tokens(response_text)
    for msg in messages:
        input_token_inc += calculate_tokens(msg.content)

    new_chat_text = chat_text_list + [f"导诊人员：{response_text}\n"]

    return {
        "messages": [AIMessage(content=response_text)],
        "chat_text": new_chat_text,
        "nurse_turn_count": turn + 1,
        "input_token_n": state.get('input_token_n', 0) + input_token_inc,
        "output_token_n": state.get('output_token_n', 0) + output_token_inc,
        # 记录每轮对话结构，用于最终保存
        "current_nurse_phase": phase,
        "current_nurse_response": response_text
    }


# ==========================================
# Supervisor / DialogueLLM Node 逻辑
# ==========================================

def supervisor_node(state: AgentState) -> dict:
    """
    包含 DialogueLLM 的信息提取和 Supervisor 的评估逻辑
    对应原代码 one_chat 中的知识更新和比较逻辑
    """
    messages = state.get('messages', [])
    patient_profile = state['patient_profile']
    collected_knowledge = state.get('collected_knowledge', [])

    input_token_s_inc = 0
    output_token_s_inc = 0
    input_token_i_inc = 0
    output_token_i_inc = 0

    # 获取最新的对话 (最后两句：Doctor & Patient)
    # 如果是第一轮，可能只有一个 Patient
    temp_chat = []
    if len(messages) >= 2:
        # Nurse(AIMessage) -> Patient(HumanMessage)
        if isinstance(messages[-2], AIMessage) and isinstance(messages[-1], HumanMessage):
            temp_chat = [
                {"role": "doctor", "content": messages[-2].content},
                {"role": "patient", "content": messages[-1].content}
            ]
    elif len(messages) == 1 and isinstance(messages[-1], HumanMessage):
        temp_chat = [{"role": "patient", "content": messages[-1].content}]

    # 1. DialogueLLM 信息提取
    llm_info = get_llm("Supervisor-info", temperature=0.7)

    chat_process_input = f"已知信息：{str(collected_knowledge)}\n新对话：{str(temp_chat)}\n新信息："

    try:
        response_i = llm_info.invoke([
            SystemMessage(content=SYSTEM_PROMPT_DIALOGUE),
            HumanMessage(content=chat_process_input)
        ])
        data = parse_json_response(response_i.content)
        new_record = data.get('new_record', [])
        extracted_info = [{item.get('field', ''): item.get('record', '')} for item in new_record]
    except Exception as e:
        print(f"DialogueLLM chat_process error: {e}")
        extracted_info = []
        response_i = None

    input_token_i_inc += calculate_tokens(SYSTEM_PROMPT_DIALOGUE + chat_process_input)
    if response_i:
        output_token_i_inc += calculate_tokens(response_i.content)

    # 更新知识库
    new_knowledge = collected_knowledge + extracted_info

    # 2. Supervisor 比较评估
    llm_super = get_llm("Supervisor", temperature=0.1)

    real_info = {
        '主诉': patient_profile.get('chief_complaint'),
        '姓名': patient_profile.get('name'),
        '年龄': patient_profile.get('age'),
        '性别': patient_profile.get('gender'),
        '既往史': patient_profile.get('past_history'),
        '现病史': patient_profile.get('present_illness_history')
    }

    compare_input = f"<导诊人员收集到的信息>：{str(new_knowledge)}\n<患者的真实信息>：{str(real_info)}\n<患者的初步诊断>：{patient_profile.get('preliminary_diagnosis', '')}"

    # 原代码逻辑：如果 not enough，才重新 compare。这里每次都 compare 以保持状态最新
    try:
        response_s = llm_super.invoke([
            SystemMessage(content=SYSTEM_PROMPT_M),
            HumanMessage(content=compare_input)
        ])
        data = parse_json_response(response_s.content)
        enough = data.get('enough', False)
        suggestion = data.get('suggestion', '')
        action = data.get('action', '症状询问')
    except Exception as e:
        print(f"Supervisor compare error: {e}")
        enough = False
        suggestion = ""
        action = "症状询问"
        response_s = None

    input_token_s_inc += calculate_tokens(compare_input + SYSTEM_PROMPT_M)
    if response_s:
        output_token_s_inc += calculate_tokens(response_s.content)

    # 3. Supervisor 对话质量监控 (Monitor)
    flag = False
    monitor_suggestion = ""
    if not enough and state.get('nurse_turn_count', 1) > 1:  # 原代码是在 not end 且 turn 循环里
        chat_text_list = state.get('chat_text', [])
        monitor_input = ''.join(chat_text_list[-8:])  # 看最近8句
        try:
            response_m = llm_super.invoke([
                SystemMessage(content=SYSTEM_PROMPT_M_B + "\n请以JSON格式输出，包含flag, suggestion两个字段。"),
                HumanMessage(content=monitor_input)
            ])
            data = parse_json_response(response_m.content)
            flag = data.get('flag', False)
            monitor_suggestion = data.get('suggestion', '')

            input_token_s_inc += calculate_tokens(monitor_input + SYSTEM_PROMPT_M_B)
            output_token_s_inc += calculate_tokens(response_m.content)
        except Exception as e:
            print(f"Supervisor monitor error: {e}")

    # 构建 save_chat 建议列表
    save_chat = state.get('save_chat', {})
    if 'suggestion' not in save_chat:
        save_chat['suggestion'] = []

    turn = state.get('nurse_turn_count', 1)
    if not enough:
        save_chat['suggestion'].append({"monitor": "信息收集是否全面", "content": suggestion, "turn": turn})
    if flag:
        save_chat['suggestion'].append(
            {"monitor": "整体监督病人情绪和对话有效性", "content": monitor_suggestion, "turn": turn})

    return {
        "collected_knowledge": new_knowledge,
        "info_enough": enough,
        "next_step_suggestion": suggestion,
        "supervisor_action": action,  # 保存供 Nurse 使用
        "monitor_suggestion": monitor_suggestion if flag else None,
        "save_chat": save_chat,
        "input_token_i": state.get('input_token_i', 0) + input_token_i_inc,
        "output_token_i": state.get('output_token_i', 0) + output_token_i_inc,
        "input_token_s": state.get('input_token_s', 0) + input_token_s_inc,
        "output_token_s": state.get('output_token_s', 0) + output_token_s_inc
    }
