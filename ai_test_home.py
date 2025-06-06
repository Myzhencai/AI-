import re
import subprocess
import time

import streamlit as st
from PIL import Image
import google.generativeai as genai
import docx
import PyPDF2
import pandas as pd
import os


count_script = 0

# 示例函数（请根据实际实现替换）
def generateprd(input_text):
    return f"（PRD分析结果）\n{input_text}"


def generatetestscripts(input_text):
    """
    使用 Gemini 模型根据自然语言输入生成 Linux Shell 脚本。
    """

    file_path = './test_function.sh'
    shell_save_dir = './temp'

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    prompt = f"""
你是一个熟练的 Linux Shell 脚本工程师，请根据以下自然语言描述生成一个完整的 Bash 脚本：

需求描述：
{content}这是一个函数调用库，请优先从函数库中选择测试方法，其中没用的到的方法不用写出来。如果没有就自动生成，但是不要使用“adb shell”关键字\n
{input_text}

请输出完整的脚本内容，要求包含解释性注释，脚本以 #!/bin/sh 开头。
"""
    prompt2 = f"""
你是一个熟练的 Linux Shell 脚本工程师，请根据以下自然语言描述生成一个完整的 Bash 脚本：

需求描述：
{input_text}

请输出修改后的脚本内容，仅提供代码就可以了。
"""

    if count_script == 0:
        response = st.session_state.chat.send_message(prompt, stream=True)
    else:
        response = st.session_state.chat.send_message(prompt2, stream=True)

    response.resolve()
    os.makedirs(shell_save_dir, exist_ok=True)
    shell_save_path = os.path.join(shell_save_dir, "ai_tmp.sh")
    shell_file_content = response.text.removeprefix("```bash").strip()
    shell_file_content = shell_file_content.removesuffix("```").strip()

    with open(shell_save_path, "w", newline='\n', encoding="utf-8") as f:
        f.write(shell_file_content)

    return response.text


def sleep_time(user_time):
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i in range(user_time):
        # 更新进度条
        progress_bar.progress((i + 1.0) / user_time)
        status_text.text(f"log抓取中还剩：{i + 1}/{user_time} 秒")
        time.sleep(1)

    status_text.text("log抓取完成！")
    progress_bar.empty()


def run_scripts():
    result = subprocess.run(["adb", "push", r"E:\py_project\AI-gemini\temp\ai_tmp.sh", "sdcard"], shell=True)
    print("push ai_tmp.sh success:", result.returncode)  # 0 表示成功
    if result.returncode == 0:
        subprocess.run(["adb", "root"], shell=True)
        process = subprocess.Popen("adb shell sh sdcard/ai_tmp.sh", shell=True, stdout=subprocess.PIPE,
                                encoding='utf-8', errors='ignore')
        # 实时读取输出（适用于长时间运行的命令）
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                st.chat_message("assistant").write(output.strip())

        # 获取最终返回码
        return_code = process.wait()
        if return_code == 0:
            exe_msg = "脚本执行成功，正在获取当前显示内容，请稍等。。。"
            st.chat_message("assistant").write(exe_msg)
        else:
            exe_msg = "脚本执行失败，请尝试修改脚本或者重新生成"
            st.chat_message("assistant").write(exe_msg)

        result = subprocess.run("adb shell screencap -p sdcard/cap.png", shell=True)
        print("get screen cap success:", result.returncode)
        result = subprocess.run(["adb", "pull", "sdcard/cap.png", r"E:\py_project\AI-gemini\screen"], shell=True)
        if result.returncode == 0:
            image = Image.open("./screen/cap.png")
            st.image(image, caption='设备当前显示内容', use_container_width=True)
    else:
        exe_msg = "脚本执行失败，请确认是否ADB连接上了设备"
        st.chat_message("assistant").write(exe_msg)


def debug_logcat_file(input_text):
    log_path = './log/system_log.txt'

    if os.path.exists(log_path):
        os.remove(log_path)

    match = re.search(r'(\d+)s', input_text)
    if match:
        use_time = int(match.group(1))
    else:
        match = re.search(r'(\d+)min', input_text)
        if match:
            use_time = int(match.group(1))
            use_time = 60 * use_time
        else:
            use_time = 15

    match = re.search(r'TAG=([a-zA-Z]+)', input_text)
    if match:
        tag = match.group(1)
    else:
        tag = "Runtime"

    with open('./temp/logcat.sh', 'r', encoding='utf-8') as f:
        content = f.read()
        modified_content = re.sub(r'sleep \d+', "sleep " + str(use_time), content)
        last_content = re.sub(r'LOG_TAG="([a-zA-Z]+)"', "LOG_TAG=" + '"' + tag + '"', modified_content)

    with open('./temp/logcat.sh', 'w', newline='\n', encoding='utf-8') as f:
        f.write(last_content)

    result = subprocess.run(["adb", "push", r"E:\py_project\AI-gemini\temp\logcat.sh", "sdcard"], shell=True)
    if result.returncode == 0:
        subprocess.run(["adb", "root"], shell=True)
        subprocess.run("adb shell sh sdcard/logcat.sh", shell=True)
        sleep_time(use_time)
        subprocess.run(["adb", "pull", r"sdcard/system_log.txt", r"E:\py_project\AI-gemini\log"], shell=True)
    else:
        return "设备没有连接上ADB，请连接后重试"

    try:
        with open(log_path, 'r', encoding='utf-8') as file:
            logcat_content = file.read()
    except FileNotFoundError:
        print(f"Error: The file '{log_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    if logcat_content.__len__() < 100:
        return "没有抓到错误日志信息"

    prompt = f"""
    你是一个熟练的Android系统工程师，请根据以下自然语言描述分析日志：

    需求描述：
    {logcat_content}这是抓取的系统log\n
    {input_text}

    请给出详细分析，并做出合适的建议。
    """

    response = st.session_state.chat.send_message(prompt, stream=True)
    response.resolve()
    return response.text



# PRD 模式系统提示
roleprompt = """
我是一个产品需求文档分析专家，请提供一个PRD文档草稿给我，我会按照下面的 PRD 规范对内容进行结构化填充。
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

4. 验收标准

请提供给我一个PRD文档吧
"""

st.set_page_config(page_title="Gemini Pro with Streamlit", page_icon="♊")
st.title("零缺陷Agent")

st.write("欢迎来到 Gemini Pro 聊天机器人。您可以通过提供您的 Google API 密钥来继续。")

with st.expander("提供您的 Google API 密钥"):
    google_api_key = st.text_input("Google API 密钥", key="google_api_key", type="password")

if not google_api_key:
    st.info("请输入 Google API 密钥以继续")
    st.stop()

genai.configure(api_key=google_api_key)

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
        "上传文档（支持 .docx, .pdf, .xls, .xlsx）",
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
        st.session_state.messages = [{"role": "system", "content": roleprompt}]
        st.session_state.chat_mode = "Prd"

# 初始化聊天状态
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": roleprompt}]
if "chat_mode" not in st.session_state:
    st.session_state["chat_mode"] = "Prd"

# 显示历史记录
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 处理用户输入
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # 切换模式
    if prompt.startswith("Prd@"):
        st.session_state["chat_mode"] = "Prd"
        user_input = prompt.removeprefix("Prd@").strip()
    elif prompt.startswith("Test@"):
        st.session_state["chat_mode"] = "Test"
        count_script = 0
        user_input = prompt.removeprefix("Test@").strip()
    elif prompt.startswith("Debug@"):
        st.session_state["chat_mode"] = "Debug"
        user_input = prompt.removeprefix("Debug@").strip()
    else:
        user_input = prompt
        count_script = 1

    # 根据模式处理输入
    if st.session_state["chat_mode"] == "Prd":
        if file_text and not st.session_state.get("file_processed", False):
            full_prompt = f"{roleprompt}\n\n以下是用户上传的 PRD 文档内容：\n{file_text}"
            response = st.session_state.chat.send_message(full_prompt, stream=True, generation_config=gen_config)
            st.session_state["file_processed"] = True
            response.resolve()
            msg = response.text
        else:
            msg = generateprd(user_input)

    elif st.session_state["chat_mode"] == "Test":
        msg = generatetestscripts(user_input)

    elif st.session_state["chat_mode"] == "Debug":
        msg = debug_logcat_file(user_input)

    st.session_state.messages.append({"role": "assistant", "content": msg})
    st.chat_message("assistant").write(msg)

# 保存 PRD 按钮
if st.session_state["chat_mode"] == "Prd":
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

if st.session_state["chat_mode"] == "Test":
    if st.button("执行脚本"):
        run_scripts()
