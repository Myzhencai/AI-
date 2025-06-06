import difflib
import streamlit as st
from PIL import Image
import google.generativeai as genai
import docx
import PyPDF2
import pandas as pd
import io
import os
import re
from docx import Document
import pypandoc
import tempfile
import streamlit.components.v1 as components
import pyperclip

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


def generatetestdemo(prompt_text=""):
    if not prompt_text.startswith("test："):
        return "无效的测试请求格式。请以 'test：' 开头。"

    query = prompt_text[len("test："):].strip()

    # 使用 difflib 查找最相近的脚本名称
    script_names = list(test_scripts.keys())
    best_match = difflib.get_close_matches(
        query, script_names, n=1, cutoff=0.4)

    if best_match:
        name = best_match[0]
        data = test_scripts[name]

        # 提取测试次数
        match = re.search(r"(\d+)\s*次", query)
        script = data["script"]
        if match:
            count = int(match.group(1))
            # 替换循环控制
            modified_script = re.sub(
                r"while\s+true", f"while [ $i -lt {count} ]", script)
            return f"【{name}】已生成测试 {count} 次的脚本：\n\n```sh\n{modified_script}\n```"
        else:
            return f"【{name}】的原始测试脚本如下：\n\n```sh\n{script}\n```"

    return "未识别到与输入内容语义相近的测试脚本。请检查输入内容是否正确描述了测试内容，例如“测试蓝牙音箱连接5次”等。"


# === roleprompt & Streamlit 页面设置 ===
roleprompt = f"""
我是一个投影仪产品需求文档分析专家，请提供一个PRD文档草稿给我，我会按照下面的 PRD 规范对内容进行结构化填充。
规范包括：

1. 前置条件
   - 背景介绍（非必要信息）
   - 产品目标
   - 名词解释（非必要信息）

2. 功能需求
   - 功能清单
   - 数据指标
   - 流程图（如 UI 框图）（非必要信息）
   - 应用场景
     - 使用场景
     - 场景规则
     - 边界判断
     - 中断处理（非必要信息）
     - 功能与 UI 交互
   - 结构图

3. 非功能说明
   - 性能指标
     - 速度
     - 可靠性
     - CPU/内存占用（非必要信息）
   - 兼容性
   - 安全和保密（非必要信息）

4. 测试方法
   - 测试描述

5. 验收标准

请上传 PRD 文档或给我一个产品名称，我根据以上 PRD 规范个你逐步完善 PRD 文档。
"""

st.set_page_config(page_title="Gemini Pro with Streamlit", page_icon="♊")

# st.write("欢迎来到 Gemini Pro 聊天机器人。您可以通过提供您的 Google API 密钥来继续。")

# with st.expander("提供您的 Google API 密钥"):
#     google_api_key = st.text_input("Google API 密钥", key="google_api_key", type="password")

# if not google_api_key:
#     st.info("请输入 Google API 密钥以继续")
#     st.stop()

genai.configure(api_key="AIzaSyCgrK41Y2zSc90zJf-Ba0E9sdLW74KHjA4")

st.title("零缺陷Agent")


def markdown_to_docx_bytes(md_text):
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmpfile:
        tmp_path = tmpfile.name
    pypandoc.convert_text(md_text, 'docx', format='md', outputfile=tmp_path)
    with open(tmp_path, 'rb') as f:
        return f.read()


def summarize_for_filename(text: str, model_name="gemini-2.0-flash-lite") -> str:
    if not text:
        return "document"
    model = genai.GenerativeModel(model_name)
    prompt = (
        "请将以下内容总结为5到10个词以内的短语，用于文件名。不要加标点，不要换行，只返回短语：\n\n" + text[:1000]
    )
    try:
        response = model.generate_content(prompt)
        title = response.text.strip()
        # 清理非法文件名字符
        title = re.sub(r'[\\/*?:"<>|]', '_', title)
        print(f"生成的文件名：{title}")
        return title or "document"
    except Exception as e:
        print(f"生成文件名出错：{e}")
        return "document"


def safe_filename(name: str, default="doc.docx") -> str:
    # 只保留字母数字和下划线，防止文件名非法
    safe_name = re.sub(r'[^\w\-_. ]', '', name)
    safe_name = safe_name.strip()
    if not safe_name:
        return default
    if not safe_name.lower().endswith(".docx"):
        safe_name += ".docx"
    return safe_name


def render_export_button(role, md_text: str, button_label="导出", key=None):
    file_name = "doc.docx"
    if role == "assistant":
        messages = st.session_state.get("messages", {})
        # print(f"{key} message: {messages}")
        try:
            match = re.search(r'\d+', key)  # 提取 key 中的数字部分
            if match:
                if role == "assistant":
                    index = int(match.group()) - 1
                else:
                    index = int(match.group())
                # print(f"index: {index}")
                if index >= 0 and index < len(messages):
                    content = messages[index].get("content", "")
                    # print(f"content: {content}")
                    file_name = safe_filename(
                        content.split("\n", 1)[0])  # 取首行作为文件名
                # else:
                #     print("索引越界")
            else:
                print("key 中不包含数字")
        except (ValueError, IndexError, KeyError) as e:
            # 任何异常都用默认文件名
            print(f"[导出异常] key={key}, 错误: {e}")
            pass

    # print(f"file_name: {file_name}")
    if st.download_button(
        label=button_label,
        data=markdown_to_docx_bytes(md_text),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=key
    ):
        st.toast("导出成功！")


def copy(content):
    try:
        pyperclip.copy(content)
    except Exception:
        st.toast("服务器繁忙，请稍后再试。")


def retry(role, key, content):
    if role != "user":
        st.toast("仅用户消息可重试。")
        return
    print(f"重试按钮点击，retry_prompt: {content}")
    response = st.session_state.chat.send_message(
        content, stream=True, generation_config=gen_config)
    response.resolve()
    retry_msg = response.text
    messages = st.session_state.messages
    if key + 1 < len(messages):
        messages[key + 1]["content"] = retry_msg
    else:
        print({"role": "assistant", "content": retry_msg})


def render_btn(role, content: str, key: str):
    # 按钮区域
    col1, col2, col3, col4, col5, col6, col7 = st.columns([1]*7)

    # 导出按钮
    with col1:
        render_export_button(
            role, content, button_label="📥 导出", key=f"export_{key}")

    # 复制按钮
    with col2:
        st.button("📋 复制", key=f"copy_{key}", on_click=lambda: copy(content))

    # 重试按钮（仅限 assistant 消息）
    with col3:
        # if role == "user":
        st.button("🔄 重试", key=f"retry_{key}",
                  on_click=lambda: retry(role, key, content))

    # 编辑按钮
    with col4:
        st.empty()
        # 初始化编辑状态
        # if f"is_editing_{key}" not in st.session_state:
        #     st.session_state[f"is_editing_{key}"] = False

        # if not st.session_state[f"is_editing_{key}"]:
        #     if st.button("✏️ 编辑", key=f"edit_{key}"):
        #         st.session_state[f"is_editing_{key}"] = True
        #         st.session_state[f"edit_input_{key}"] = content
        #         st.rerun()

    # 删除按钮
    with col5:
        st.empty()
        # if st.button("❌ 删除", key=f"delete_{key}"):
        #     # print(f"删除按钮点击，key1: {key}")
        #     if key == 0:
        #         st.toast("提示对话，不可删除")
        #         return
        #     if "messages" in st.session_state:
        #         messages = st.session_state.messages
        #         if isinstance(messages, list) and 0 <= key < len(messages):
        #             messages.pop(key)
        #             st.rerun()
        #         else:
        #             print(
        #                 f"无效的 key: {key}, 当前 messages 长度: {len(messages)}")

    with col6:
        st.empty()

    with col7:
        st.empty()

    # 把编辑框独立放在列外部，使其占整行宽度
    if st.session_state.get(f"is_editing_{key}", False):
        # 占整行的宽度
        st.text_area(
            "编辑内容",
            key=f"edit_input_{key}",
            height=200
        )

        col_save, col_cancel, col3, col4, col5 = st.columns([1]*5)
        with col_save:
            if st.button("✅ 保存修改", key=f"save_edit_{key}"):
                st.session_state.messages[key][
                    "content"] = st.session_state[f"edit_input_{key}"]
                st.session_state[f"is_editing_{key}"] = False
                st.rerun()

        with col_cancel:
            if st.button("❌ 取消", key=f"cancel_edit_{key}"):
                st.session_state[f"is_editing_{key}"] = False
                st.rerun()

        with col3:
            st.empty()

        with col4:
            st.empty()

        with col5:
            st.empty()


with st.sidebar:
    option = st.selectbox('选择您的模型', ('gemini-2.0-flash-lite',))

    if 'model' not in st.session_state or st.session_state.model != option:
        st.session_state.chat = genai.GenerativeModel(
            option).start_chat(history=[])
        st.session_state.model = option

    st.write("在此处调整您的参数:")
    temperature = st.number_input(
        "温度", min_value=0.0, max_value=1.0, value=0.5, step=0.01)
    max_token = st.number_input("最大输出令牌数", min_value=0, value=10000)
    gen_config = genai.types.GenerationConfig(
        max_output_tokens=max_token, temperature=temperature)
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
            file_text = "\n".join([page.extract_text()
                                  for page in reader.pages if page.extract_text()])

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

        if not st.session_state.get("file_processed", False):
            agent = "{\"PRD规范制定\":{\"前置条件\":{\"产品目标\":\"\"},\"功能需求\":{\"功能清单\":\"\",\"数据指标\":\"\",\"应用场景\":{\"使用场景\":\"场景规则\",\"边界判断\":\"\",\"功能\":\"\",\"UI交互\":\"\"},\"结构图\":\"\"},\"非功能说明\":{\"性能指标\":{\"速度\":\"\",\"可靠性\":\"\"},\"兼容性\":\"\"},\"验收标准\":\"\"}}"
            full_prompt = f"{agent}这个是一个prd规范模版，必须严格根据这个模版规范，逐小项检测用户上传的prd文档是否按规范模版完善，有内容的选项忽略，没有选项或选项为空逐项提问，然后根据用户输入去扩写完善这一项，然后显示完善后的完整文档，问用户是否满意，用户不满意，则根据用户输入重新AI生成这一项内容，用户满意，则再检查下一项，依次类推，直到全部完善以下是用户上传的 PRD 文档内容，最后然后输出一个完善后完整的PRD文档：\n{file_text}"
            response = st.session_state.chat.send_message(
                full_prompt, stream=True, generation_config=gen_config)
            st.session_state["file_processed"] = True
            response.resolve()
            msg = response.text
            st.session_state.messages.append(
                {"role": "assistant", "content": msg})
            st.chat_message("assistant").write(msg)
            # render_btn("assistant", msg, len(st.session_state.messages)-1)

    st.divider()

    if st.button("清除聊天历史"):
        st.session_state.messages.clear()
        st.session_state["messages"] = [
            {"role": "system", "content": roleprompt}]

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": roleprompt}]

for i, msg in enumerate(st.session_state.messages):
    content = msg["content"]
    role = msg["role"]
    st.chat_message(role).write(content)
    render_btn(role, content, i)

if prompt := st.chat_input():
    # st.session_state.messages.append({"role": "user", "content": prompt})
    # st.chat_message("user").write(prompt)

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
        render_btn(role, prompt, len(st.session_state.messages)-1)

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
                prompt = "test：WiFi 开关压力测试" + \
                    (f"{prompt}" if re.search(r"\d+\s*次", prompt) else "")
            elif is_related(normalized_prompt, bt_keywords):
                prompt = "test：蓝牙音箱压力测试" + \
                    (f"{prompt}" if re.search(r"\d+\s*次", prompt) else "")

        # 执行脚本生成
        if prompt.startswith("test："):
            result = generatetestdemo(prompt)
            st.session_state.messages.append(
                {"role": "assistant", "content": result})
            st.chat_message("assistant").write(result)
            st.stop()

    # =========== PRD 分析逻辑 ============
    # if file_text and not st.session_state.get("file_processed", False):
    #     full_prompt = f"{roleprompt}\n\n根据这个模版规范，逐项检测用户上传的prd文档是否按规范模版完善，如果有缺失内容的选项且不是标记为非必要信息的选项逐项提示用户输入，要逐项引导用户输入，然后根据用户输入去扩写完善这一项，然后显示完善后的完整文档，问用户是否满意，用户不满意，则根据用户输入重新AI生成这一项内容，用户满意，则再检查下一项，依次类推，直到全部完善以下是用户上传的 PRD 文档内容，：\n{file_text}"
    #     response = st.session_state.chat.send_message(
    #         full_prompt, stream=True, generation_config=gen_config)
    #     st.session_state["file_processed"] = True
    # elif not file_text:
    #     msg = "⚠️ 请先上传文档，我才能根据 PRD 规范进行分析。"
    #     st.session_state.messages.append({"role": "assistant", "content": msg})
    #     st.chat_message("assistant").write(msg)
    #     render_btn(role, msg, len(st.session_state.messages)-1)
    #     st.stop()
    # else:
    #     response = st.session_state.chat.send_message(
    #         prompt, stream=True, generation_config=gen_config)

    if file_text:
        if not st.session_state.get("file_processed", False):
            agent = "{\"PRD规范制定\":{\"前置条件\":{\"产品目标\":\"\"},\"功能需求\":{\"功能清单\":\"\",\"数据指标\":\"\",\"应用场景\":{\"使用场景\":\"场景规则\",\"边界判断\":\"\",\"功能\":\"\",\"UI交互\":\"\"},\"结构图\":\"\"},\"非功能说明\":{\"性能指标\":{\"速度\":\"\",\"可靠性\":\"\"},\"兼容性\":\"\"},\"验收标准\":\"\"}}"
            full_prompt = f"{agent}这个是一个prd规范模版，必须严格根据这个模版规范，逐小项检测用户上传的prd文档是否按规范模版完善，有内容的选项忽略，没有选项或选项为空逐项提问，然后根据用户输入去扩写完善这一项，然后显示完善后的完整文档，问用户是否满意，用户不满意，则根据用户输入重新AI生成这一项内容，用户满意，则再检查下一项，依次类推，直到全部完善以下是用户上传的 PRD 文档内容，最后然后输出一个完善后完整的PRD文档：\n{file_text}"
            response = st.session_state.chat.send_message(
                full_prompt, stream=True, generation_config=gen_config)
            st.session_state["file_processed"] = True
        else:
            response = st.session_state.chat.send_message(
                prompt, stream=True, generation_config=gen_config)
    else:
        if not st.session_state.get("text_processed", False):
            full_prompt = f"{roleprompt}\n\n根据这个模版规范，逐项完善用户的prd文档，如果有缺失内容的选项且不是标记为非必要信息的选项逐项提示用户输入，要逐项引导用户输入，然后根据用户输入去扩写完善这一项，然后显示完善后的完整文档，问用户是否满意，用户不满意，则根据用户输入重新AI生成这一项内容，用户满意，则再检查下一项，依次类推，直到全部完善以下是用户上传的 PRD 文档内容，这个是产品名称：{prompt}"
            response = st.session_state.chat.send_message(
                full_prompt, stream=True, generation_config=gen_config)
            st.session_state["text_processed"] = True
        else:
            response = st.session_state.chat.send_message(
                prompt, stream=True, generation_config=gen_config)

    response.resolve()
    msg = response.text
    # print(f"返回：{msg}")
    st.session_state.messages.append({"role": "assistant", "content": msg})
    st.chat_message("assistant").write(msg)
    render_btn(role, msg, len(st.session_state.messages)-1)

    # if st.button("保存修改的PRD到本地文件"):
    #     last_assistant_msg = None
    #     for message in reversed(st.session_state.messages):
    #         if message["role"] == "assistant":
    #             last_assistant_msg = message["content"]
    #             break

    #     if last_assistant_msg:
    #         save_dir = "D:/LLM_Gemini_Pro_Streamlit/"
    #         os.makedirs(save_dir, exist_ok=True)
    #         save_path = os.path.join(save_dir, "修改后的PRD.txt")

    #         with open(save_path, "w", encoding="utf-8") as f:
    #             f.write(last_assistant_msg)

    #         st.success(f"PRD 已保存到本地文件: {save_path}")
    #     else:
    #         st.warning("没有找到可以保存的回复内容。")
