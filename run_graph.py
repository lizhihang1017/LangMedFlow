import sys
import os
import json
import random
from tqdm import tqdm
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from graph import build_graph
from nodes import get_llm, calculate_tokens
from data_process import read_data,patient_info_sample
import pandas as pd
from system_prompt import SYSTEM_PROMPT_P_C, SYSTEM_PROMPT_S_C
from langgraphics import watch
# 配置常量
FILE_PATH = "data/input/emr.json"
PATIENT_PATH = "data/patient_simulate/patient_setting.json"
PATIENT_PERSONALITY_PATH = "data/patient_simulate/bigfive_dataset.csv"
OUTPUT_PATH = "data/output/output_results.json"
MAX_NUM = 1  # 测试运行时生成几条数据


def setup_patient_profile(emr_data, p_info, p_data):
    """
    根据原项目逻辑，为 EMR 数据添加性格、财务等模拟设定，并调用 LLM 构建场景和沟通风格。
    """
    # 1. 采样患者背景信息
    patient_data = patient_info_sample(emr_data, p_info, p_data)

    # 2. 构建 profile 基础数据
    profile = {
        "chief_complaint": patient_data.get('chief_complaint', ''),
        "name": patient_data.get('name', ''),
        "age": patient_data.get('age', ''),
        "gender": patient_data.get('gender', ''),
        "past_history": patient_data.get('past_history', ''),
        "drug_allergy_history": patient_data.get('drug_allergy_history', ''),
        "present_illness_history": patient_data.get('present_illness_history', ''),
        "preliminary_diagnosis": patient_data.get('preliminary_diagnosis', ''),
        "department": patient_data.get('department', ''),
        "edu": patient_data.get('edu', ''),
        "personality": patient_data.get('personality', []),
        "bigfive": patient_data.get('bigfive', {}),
        "finance": patient_data.get('finance', ''),
        "visit_date": patient_data.get('visit_date', '')
    }

    # 获取 Patient LLM
    llm = get_llm("Patient", temperature=0.7)
    input_token_inc = 0
    output_token_inc = 0

    # 3. 构造沟通风格 (patient_disc)
    disc_input = f"性别：{profile['gender']}；年龄：{profile['age']}；受教育程度：{profile['edu']}；性格：{profile['personality']}；收入情况：{profile['finance']}"
    try:
        response_disc = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT_P_C),
            HumanMessage(content=disc_input)
        ])
        patient_disc = response_disc.content
        input_token_inc += calculate_tokens(SYSTEM_PROMPT_P_C + disc_input)
        output_token_inc += calculate_tokens(patient_disc)
    except Exception as e:
        print(f"Error constructing patient_disc: {e}")
        patient_disc = "沟通风格默认"

    # 4. 构造场景 (patient_scene)
    scene_input = f"<受教育程度>：{profile['edu']}；<年龄>：{profile['age']}；<主诉>：{profile['chief_complaint']}；<现病史>：{profile['present_illness_history']}；<既往史>：{profile['past_history']}；<就诊时间>：{profile['visit_date']}"
    try:
        response_scene = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT_S_C),
            HumanMessage(content=scene_input)
        ])
        patient_scene = response_scene.content
        input_token_inc += calculate_tokens(SYSTEM_PROMPT_S_C + scene_input)
        output_token_inc += calculate_tokens(patient_scene)
    except Exception as e:
        print(f"Error constructing patient_scene: {e}")
        patient_scene = "默认就诊场景"

    return profile, patient_disc, patient_scene, input_token_inc, output_token_inc


def run_simulation():
    print("=== 初始化数据 ===")
    emr_list = read_data(FILE_PATH)
    p_info = read_data(PATIENT_PATH)
    p_data = pd.read_csv(PATIENT_PERSONALITY_PATH)

    # 打乱并限制数量
    random.seed(42)
    random.shuffle(emr_list)
    emr_list = emr_list[:MAX_NUM]

    # 编译 Graph
    print("=== 编译 LangGraph ===")
    app = build_graph()

    results = []

    print(f"=== 开始模拟对话 (共 {len(emr_list)} 条) ===")
    for idx, emr in enumerate(tqdm(emr_list, desc="Simulation Progress")):
        try:
            # 1. 准备患者画像，并使用大模型生成 scene 和 disc
            profile, patient_disc, patient_scene, init_input_token, init_output_token = setup_patient_profile(emr,
                                                                                                              p_info,
                                                                                                              p_data)

            # 2. 初始化状态
            initial_state = {
                "messages": [AIMessage(content="您好，有什么可以帮你的吗？")],  # 第一句由 Nurse 发起
                "chat_text": ["导诊人员：您好，有什么可以帮你的吗？\n"],
                "patient_profile": profile,
                "patient_scene": patient_scene,
                "patient_disc": patient_disc,
                "nurse_department": profile['department'],
                "nurse_turn_count": 1,
                "collected_knowledge": [{'姓名': profile['name']}, {'年龄': profile['age']},
                                        {'性别': profile['gender']}],
                "is_finished": False,
                "save_chat": {
                    'id': emr.get("outpatient_number", f"ID_{idx}"),
                    'patient_setting': {
                        "education": profile['edu'],
                        "personality": profile['bigfive'],
                        "personality_details": profile['personality'],
                        "finance": profile['finance']
                    },
                    'scene': patient_scene,
                    'p_disc': patient_disc,
                    'dialogue': [],
                    'suggestion': []
                },
                "input_token_p": init_input_token, "output_token_p": init_output_token,
                "input_token_n": 0, "output_token_n": 0,
                "input_token_s": 0, "output_token_s": 0,
                "input_token_i": 0, "output_token_i": 0,
            }

            # 3. 运行图
            final_state = app.invoke(initial_state)

            # 4. 提取和整理结果
            save_chat = final_state['save_chat']
            messages = final_state['messages']

            # 构建 dialogue 列表 (从第二句开始，因为第一句是初始化的问候)
            dialogue_list = []
            turn = 1
            for msg in messages[1:]:
                role = "doctor" if isinstance(msg, AIMessage) else "patient"
                dialogue_list.append({
                    "role": role,
                    "content": msg.content,
                    "turn": turn // 2 + 1 if role == "patient" else turn // 2 + 1
                })
                turn += 1

            save_chat['dialogue'] = dialogue_list
            save_chat['token_usage'] = {
                "Patient": {"in": final_state['input_token_p'], "out": final_state['output_token_p']},
                "Nurse": {"in": final_state['input_token_n'], "out": final_state['output_token_n']},
                "Supervisor": {"in": final_state['input_token_s'], "out": final_state['output_token_s']},
                "DialogueLLM": {"in": final_state['input_token_i'], "out": final_state['output_token_i']}
            }

            results.append(save_chat)

        except Exception as e:
            print(f"\nError processing index {idx}: {e}")

    # 保存结果
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"\n=== 完成！结果已保存至 {OUTPUT_PATH} ===")


if __name__ == "__main__":
    run_simulation()
