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


pypandoc.pandoc_path = r'C:\Users\Puture\AppData\Local\Pandoc\pandoc.exe'

st.set_page_config(page_title="Gemini Pro with Streamlit", page_icon="♊")

st.write("欢迎来到 Gemini Pro 聊天机器人。您可以通过提供您的 Google API 密钥来继续。")

# with st.expander("提供您的 Google API 密钥"):
#      google_api_key = st.text_input("Google API 密钥", key="", type="password")

# if not google_api_key:
#     st.info("请输入 Google API 密钥以继续")
#     st.stop()

genai.configure(api_key="")

st.title("Gemini Pro 与 Streamlit 聊天机器人")

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
        st.session_state.messages.clear()
        st.session_state["messages"] = [
            {"role": "assistant", "content": "你好。我可以帮助你吗？"}]

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


def render_export_button(md_text: str, button_label="导出", file_name=None, key=None):
    if st.download_button(
        label=button_label,
        data=markdown_to_docx_bytes(md_text),
        file_name="doc.docx",
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
    retry_prompt = st.session_state.messages[key]["content"] if key >= 0 else ""
    print(f"重试按钮点击，retry_prompt: {retry_prompt}")
    response = st.session_state.chat.send_message(
        retry_prompt, stream=True, generation_config=gen_config)
    response.resolve()
    retry_msg = response.text
    st.session_state.messages[key + 1]["content"] = retry_msg
    # st.rerun()


def render_btn(role, content: str, key: str):
    # 按钮区域
    col1, col2, col3, col4, col5, col6, col7 = st.columns([1]*7)

    # 导出按钮
    with col1:
        render_export_button(content, button_label="📥 导出", key=f"export_{key}")

    # 复制按钮
    with col2:
        st.button("📋 复制", key=f"copy_{key}", on_click=lambda: copy(content))

    # 重试按钮（仅限 assistant 消息）
    with col3:
        st.button("🔄 重试", key=f"retry_{key}",
                  on_click=lambda: retry(role, key, content))

    # 编辑按钮
    with col4:
        if st.button("✏️ 编辑", key=f"edit_{key}"):
            new_text = st.text_area(
                "编辑内容", value=content, key=f"edit_input_{key}")
            if st.button("✅ 保存修改", key=f"save_edit_{key}"):
                print(f"保存修改按钮点击，new_text: {new_text}")
                st.session_state.messages[key]["content"] = new_text
                st.rerun()

    # 删除按钮
    with col5:
        if st.button("❌ 删除", key=f"delete_{key}"):
            print(f"删除按钮点击，key1: {key}")
            st.session_state.messages.pop(key)
            st.rerun()


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
        response.resolve()
        msg = response.text
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.chat_message("assistant").write(msg)
        render_btn("assistant", msg, len(st.session_state.messages)-1)
