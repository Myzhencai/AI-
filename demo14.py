import streamlit as st
from PIL import Image
import google.generativeai as genai
import docx
import PyPDF2
import pandas as pd
import io
import os
import re

# === 预设测试脚本 JSON ===
test_scripts = {
    "WiFi 开关压力测试脚本": {
        "script": """#!/system/bin/sh
function Wifi() {
    i=0
    while true
    do
        input keyevent 23
        let i++
        echo "$(date +%Y_%m%d_%H%M%S):Wifi test $i times"
        echo "$(date +%Y_%m%d_%H%M%S):Wifi test $i times" >> /sdcard/wifi_report.txt
        sleep 20
    done
}
Wifi &"""
    },
    "蓝牙音箱压力测试脚本": {
        "script": """#!/system/bin/sh
function power() {
    i=0
    while true
    do
        sleep 5
        input keyevent 26
        sleep 3
        input keyevent 22
        sleep 3
        input keyevent 22
        sleep 3
        input keyevent 23
        sleep 5
        input keyevent 4
        let i++
        echo "$(date +%Y_%m%d_%H%M%S):power test $i times" >> /sdcard/power_report.txt
    done
}
power &"""
    }
}


# === 生成测试代码逻辑 ===
# def generatetestdemo(prompt_text=""):
#     if not prompt_text.startswith("test："):
#         return "无效的测试请求格式。请以 'test：' 开头。"
#
#     query = prompt_text[len("test："):].strip()
#
#     for name, data in test_scripts.items():
#         # 尝试匹配脚本名中的关键词
#         keywords = name.replace("脚本", "").split()
#         if all(kw in query for kw in keywords):
#             # 提取次数
#             match = re.search(r"(\d+)\s*次", query)
#             script = data["script"]
#             if match:
#                 count = int(match.group(1))
#                 # 替换 while true -> while [ $i -lt COUNT ]
#                 modified_script = re.sub(r"while\s+true", f"while [ $i -lt {count} ]", script)
#                 return f"【{name}】已生成测试 {count} 次的脚本：\n\n```sh\n{modified_script}\n```"
#             else:
#                 return f"【{name}】的原始测试脚本如下：\n\n```sh\n{script}\n```"
#
#     return "未识别到与输入内容匹配的测试脚本。请检查输入内容是否包含关键词，例如“WiFi”、“蓝牙音箱”等。"

import re
import difflib

def generatetestdemo(prompt_text=""):
    if not prompt_text.startswith("test："):
        return "无效的测试请求格式。请以 'test：' 开头。"

    query = prompt_text[len("test："):].strip()

    # 使用 difflib 查找最相近的脚本名称
    script_names = list(test_scripts.keys())
    best_match = difflib.get_close_matches(query, script_names, n=1, cutoff=0.4)

    if best_match:
        name = best_match[0]
        data = test_scripts[name]

        # 提取测试次数
        match = re.search(r"(\d+)\s*次", query)
        script = data["script"]
        if match:
            count = int(match.group(1))
            # 替换循环控制
            modified_script = re.sub(r"while\s+true", f"while [ $i -lt {count} ]", script)
            return f"【{name}】已生成测试 {count} 次的脚本：\n\n```sh\n{modified_script}\n```"
        else:
            return f"【{name}】的原始测试脚本如下：\n\n```sh\n{script}\n```"

    return "未识别到与输入内容语义相近的测试脚本。请检查输入内容是否正确描述了测试内容，例如“测试蓝牙音箱连接5次”等。"



# === roleprompt & Streamlit 页面设置 ===
roleprompt = f"""
我是一个投影仪产品需求文档分析专家，请提供一个PRD文档草稿给我，我会按照下面的 PRD 规范对内容进行结构化填充。
规范包括：

1. 前置条件
   - 背景介绍
   - 产品类目
   - 名词解释

2. 功能需求
   - 功能清单
   - 数据指标
   - 流程图（如 UI 框图）
   - 应用场景（使用场景、场景规则、边界判断、中断处理、功能与 UI 交互）
   - 结构图

3. 非功能说明
   - 性能指标（速度、可靠性、CPU/内存占用等）
   - 兼容性
   - 安全和保密

4. 测试方法
   - 测试描述

5. 验收标准

请提供给我一个PRD文档吧
"""

st.set_page_config(page_title="Gemini Pro with Streamlit", page_icon="♊")

st.write("欢迎来到 Gemini Pro 聊天机器人。您可以通过提供您的 Google API 密钥来继续。")

with st.expander("提供您的 Google API 密钥"):
    google_api_key = st.text_input("Google API 密钥", key="google_api_key", type="password")

if not google_api_key:
    st.info("请输入 Google API 密钥以继续")
    st.stop()

genai.configure(api_key=google_api_key)

st.title("零缺陷Agent")

with st.sidebar:
    option = st.selectbox('选择您的模型', ('gemini-2.0-flash-lite',))

    if 'model' not in st.session_state or st.session_state.model != option:
        st.session_state.chat = genai.GenerativeModel(option).start_chat(history=[])
        st.session_state.model = option

    st.write("在此处调整您的参数:")
    temperature = st.number_input("温度", min_value=0.0, max_value=1.0, value=0.5, step=0.01)
    max_token = st.number_input("最大输出令牌数", min_value=0, value=10000)
    gen_config = genai.types.GenerationConfig(max_output_tokens=max_token, temperature=temperature)
    st.divider()

    upload_file = st.file_uploader(
        "在此上传您的文档（支持 .docx, .pdf, .xls, .xlsx）",
        accept_multiple_files=False,
        type=["docx", "pdf", "xls", "xlsx"]
    )

    file_text = ""
    if upload_file:
        file_details = {
            "filename": upload_file.name,
            "filetype": upload_file.type,
            "filesize": upload_file.size
        }
        st.write("文件信息：", file_details)

        if upload_file.type == "application/pdf":
            reader = PyPDF2.PdfReader(upload_file)
            file_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

        elif upload_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(upload_file)
            file_text = "\n".join([para.text for para in doc.paragraphs])

        elif upload_file.type in ["application/vnd.ms-excel",
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            df = pd.read_excel(upload_file)
            file_text = df.to_csv(index=False)

        if st.session_state.get("uploaded_filename") != upload_file.name:
            st.session_state["file_processed"] = False
            st.session_state["uploaded_filename"] = upload_file.name
    st.divider()

    if st.button("清除聊天历史"):
        st.session_state.messages.clear()
        st.session_state["messages"] = [{"role": "system", "content": roleprompt}]

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": roleprompt}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # =========== test：生成测试脚本逻辑 ============
    # if prompt.startswith("test："):
    #     result = generatetestdemo(prompt)
    #     st.session_state.messages.append({"role": "assistant", "content": result})
    #     st.chat_message("assistant").write(result)
    #     st.stop()

    import difflib

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # =========== test：生成测试脚本逻辑（增强版） ============
        normalized_prompt = prompt.lower()

        # 定义关键词集合
        wifi_keywords = ["wifi", "无线", "开关", "连接", "断开", "网络"]
        bt_keywords = ["蓝牙", "音箱", "speaker", "配对", "连接", "开关"]


        def is_related(prompt_text, keywords):
            return any(kw in prompt_text for kw in keywords)


        # 自动判断语义并补全为 test：xxx
        if not prompt.startswith("test："):
            if is_related(normalized_prompt, wifi_keywords):
                prompt = "test：WiFi 开关压力测试" + (f"{prompt}" if re.search(r"\d+\s*次", prompt) else "")
            elif is_related(normalized_prompt, bt_keywords):
                prompt = "test：蓝牙音箱压力测试" + (f"{prompt}" if re.search(r"\d+\s*次", prompt) else "")

        # 执行脚本生成
        if prompt.startswith("test："):
            result = generatetestdemo(prompt)
            st.session_state.messages.append({"role": "assistant", "content": result})
            st.chat_message("assistant").write(result)
            st.stop()

    # =========== PRD 分析逻辑 ============
    if file_text and not st.session_state.get("file_processed", False):
        full_prompt = f"{roleprompt}\n\n以下是用户上传的 PRD 文档内容：\n{file_text}"
        response = st.session_state.chat.send_message(full_prompt, stream=True, generation_config=gen_config)
        st.session_state["file_processed"] = True
    elif not file_text:
        msg = "⚠️ 请先上传文档，我才能根据 PRD 规范进行分析。"
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.chat_message("assistant").write(msg)
        st.stop()
    else:
        response = st.session_state.chat.send_message(prompt, stream=True, generation_config=gen_config)

    response.resolve()
    msg = response.text
    st.session_state.messages.append({"role": "assistant", "content": msg})
    st.chat_message("assistant").write(msg)

    if st.button("保存修改的PRD到本地文件"):
        last_assistant_msg = None
        for message in reversed(st.session_state.messages):
            if message["role"] == "assistant":
                last_assistant_msg = message["content"]
                break

        if last_assistant_msg:
            save_dir = "D:/LLM_Gemini_Pro_Streamlit/"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "修改后的PRD.txt")

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(last_assistant_msg)

            st.success(f"PRD 已保存到本地文件: {save_path}")
        else:
            st.warning("没有找到可以保存的回复内容。")
