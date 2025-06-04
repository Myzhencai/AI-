import streamlit as st
from PIL import Image
import google.generativeai as genai
import io
import docx
import PyPDF2
import markdown2
from docx import Document
from bs4 import BeautifulSoup
import pypandoc
import tempfile
from io import BytesIO
import base64
import streamlit.components.v1 as components
import re
import pyperclip
import os
from dotenv import load_dotenv
load_dotenv()


if "HTTP_PROXY" in os.environ and "HTTPS_PROXY" in os.environ:
    # 两个都存在，执行设置代理
    os.environ['http_proxy'] = os.getenv("HTTP_PROXY")
    os.environ['https_proxy'] = os.getenv("HTTPS_PROXY")
    print("代理设置完成")
else:
    print("HTTP_PROXY 或 HTTPS_PROXY 未配置，跳过代理设置")

# pypandoc.pandoc_path = r'C:\Users\Puture\AppData\Local\Pandoc\pandoc.exe'

st.set_page_config(page_title="Gemini Pro with Streamlit", page_icon="♊")

st.markdown("""
    <style>
    /* 鼠标悬停时红色边框，不管是否focus */
    button:hover {
        color: red !important;
        border-color: red !important;
    }

    /* 点击后（focus或active）默认灰色边框 */
    button:focus, button:active {
        outline: none !important;
        box-shadow: none !important;
        color: inherit !important;
        border-color: #d3d3d3 !important;
        background-color: initial !important;
    }

    /* 但是如果按钮focus且hover时，覆盖为红色边框 */
    button:focus:hover {
        color: red !important;
        border-color: red !important;
    }
    </style>
""", unsafe_allow_html=True)

st.write("欢迎来到 Gemini Pro 聊天机器人。您可以通过提供您的 Google API 密钥来继续。")

# with st.expander("提供您的 Google API 密钥"):
#      google_api_key = st.text_input("Google API 密钥", key="", type="password")

# if not google_api_key:
#     st.info("请输入 Google API 密钥以继续")
#     st.stop()

if "GEMINI_API_KEY" not in os.environ or not os.environ["GEMINI_API_KEY"]:
    print("未配置环境变量 GEMINI_API_KEY，请先在.evn文件中配置！")
else:
    print("GEMINI_API_KEY 已配置。")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

st.title("Gemini Pro 与 Streamlit 聊天机器人")


def clearHistory():
    st.session_state.messages.clear()
    st.session_state["messages"] = [
        {"role": "assistant", "content": "你好。我可以帮助你吗？"}]
    print("聊天历史已清除")


with st.sidebar:
    option = st.selectbox('选择您的模型', ('gemini-2.0-flash', 'gemini-1.5-flash'))

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

    # st.divider()
    # st.markdown("""<span ><font size=1>与我联系</font></span>""", unsafe_allow_html=True)
    # "[公众号](https://mp.weixin.qq.com/s/VCQrnC6mQJUIWDxXGdutag)"
    # "[GitHub](https://github.com/mcks2000/LLM_Gemini_Pro_Streamlit)"

    st.divider()
    uploaded_file = st.file_uploader(
        "上传文件（PDF, TXT, DOCX）", type=['pdf', 'txt', 'docx'])
    upload_image = st.file_uploader(
        "在此上传您的图片", accept_multiple_files=False, type=['jpg', 'png'])

    if upload_image:
        image = Image.open(upload_image)
    st.divider()

    if st.button("清除聊天历史"):
        clearHistory()

# 读取上传的文件内容
file_text = ""
if uploaded_file:
    file_type = uploaded_file.type
    if file_type == "application/pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        file_text = "\n".join(page.extract_text()
                              for page in reader.pages if page.extract_text())
    elif file_type == "text/plain":
        stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
        file_text = stringio.read()
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = docx.Document(uploaded_file)
        file_text = "\n".join([para.text for para in doc.paragraphs])
    else:
        st.warning("不支持的文件格式")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "你好。我可以帮助你吗？"}]


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
        print()
        try:
            match = re.search(r'\d+', key)  # 提取 key 中的数字部分
            if match:
                if role == "assistant":
                    index = int(match.group()) - 1
                else:
                    index = int(match.group())
                print(f"index: {index}")
                if index >= 0 and index < len(messages):
                    content = messages[index].get("content", "")
                    print(f"content: {content}")
                    file_name = safe_filename(
                        content.split("\n", 1)[0])  # 取首行作为文件名
                else:
                    print("索引越界")
            else:
                print("key 中不包含数字")
        except (ValueError, IndexError, KeyError) as e:
            # 任何异常都用默认文件名
            print(f"[导出异常] key={key}, 错误: {e}")
            pass

    print(f"file_name: {file_name}")
    if st.download_button(
        label=button_label,
        data=markdown_to_docx_bytes(md_text),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=key
    ):
        st.toast("导出成功！")


def copy(content):
    pyperclip.copy(content)


def retry(role, key, content):
    if role == "assistant":
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
        # 初始化编辑状态
        if f"is_editing_{key}" not in st.session_state:
            st.session_state[f"is_editing_{key}"] = False

        if not st.session_state[f"is_editing_{key}"]:
            if st.button("✏️ 编辑", key=f"edit_{key}"):
                st.session_state[f"is_editing_{key}"] = True
                st.session_state[f"edit_input_{key}"] = content
                st.rerun()

    # 删除按钮
    with col5:
        if st.button("❌ 删除", key=f"delete_{key}"):
            print(f"删除按钮点击，key1: {key}")
            if key == 0:
                st.toast("提示对话，不可删除")
                return
            if "messages" in st.session_state:
                messages = st.session_state.messages
                if isinstance(messages, list) and 0 <= key < len(messages):
                    messages.pop(key)
                    st.rerun()
                else:
                    print(
                        f"无效的 key: {key}, 当前 messages 长度: {len(messages)}")

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


# 展示聊天历史
for i, msg in enumerate(st.session_state.messages):
    content = msg["content"]
    role = msg["role"]
    st.chat_message(role).write(content)
    render_btn(role, content, i)

# 图片 + 提示输入
if upload_image:
    if option == "gemini-pro":
        st.info("请切换到 Gemini Pro Vision")
        st.stop()

    if prompt := st.chat_input():
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        render_btn("user", prompt, len(st.session_state.messages)-1)

        response = st.session_state.chat.send_message(
            [prompt, image], stream=True, generation_config=gen_config)
        response.resolve()
        msg = response.text

        st.session_state.chat = genai.GenerativeModel(
            option).start_chat(history=[])
        st.session_state.messages.append({"role": "assistant", "content": msg})

        st.image(image, width=300)
        st.chat_message("assistant").write(msg)
        render_btn("assistant", msg, len(st.session_state.messages)-1)

# 文件 + 提示输入
elif uploaded_file and file_text:
    if prompt := st.chat_input(placeholder="你想问关于上传文件的什么问题？"):
        combined_prompt = f"{prompt}\n\n以下是上传的文件内容：\n{file_text}"
        st.session_state.messages.append(
            {"role": "user", "content": combined_prompt})
        st.chat_message("user").write(prompt)
        render_btn("user", prompt, len(st.session_state.messages)-1)

        response = st.session_state.chat.send_message(
            combined_prompt, stream=True, generation_config=gen_config)
        response.resolve()

        msg = response.text
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.chat_message("assistant").write(msg)
        render_btn("assistant", msg, len(st.session_state.messages)-1)


# 纯文本对话
else:
    if prompt := st.chat_input():
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        render_btn("user", prompt, len(st.session_state.messages)-1)

        response = st.session_state.chat.send_message(
            prompt, stream=True, generation_config=gen_config)
        # print(f"结果: {response}")
        response.resolve()
        msg = response.text
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.chat_message("assistant").write(msg)
        render_btn("assistant", msg, len(st.session_state.messages)-1)
