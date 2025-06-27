import re
import subprocess
import time
from pathlib import Path

import streamlit as st
from PIL import Image
import google.generativeai as genai
import docx
import PyPDF2
import pandas as pd
import os
import pypandoc
import tempfile
import json
import jsonpath
import ast
import multiprocessing


# 子进程执行函数：发送 prompt，并保留历史
def chat_worker(pipe_conn, model_name, prompt_text, api_key, history, gen_config=None):
    try:
        genai.configure(api_key=api_key)
        chat = genai.GenerativeModel(model_name).start_chat(history=history)
        response = chat.send_message(prompt_text, stream=False, generation_config=gen_config)
        response.resolve()
        pipe_conn.send({
            "text": response.text,
            "history": chat.history
        })
    except Exception as e:
        pipe_conn.send({
            "text": f"错误：{str(e)}",
            "history": history
        })
    finally:
        pipe_conn.close()

# 主进程调用：带超时、安全返回结果+历史
def safe_send_message_mp(model_name, prompt, api_key, history, gen_config=None, timeout=30):
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(
        target=chat_worker,
        args=(child_conn, model_name, prompt, api_key, history, gen_config)
    )
    p.start()
    if parent_conn.poll(timeout):
        result = parent_conn.recv()
        p.join()
        return result["text"], result["history"]
    else:
        p.terminate()
        return f"请检查网络或稍后再试。", history

def send_prompt_with_timeout(prompt, timeout=30):
    response_text, updated_history = safe_send_message_mp(
        model_name=st.session_state.model,
        prompt=prompt,
        api_key=st.session_state.google_api_key,
        history=st.session_state.chat_history if "chat_history" in st.session_state else [],
        gen_config=gen_config,
        timeout=timeout
    )
    st.session_state.chat_history = updated_history
    return response_text

def markdown_to_docx_bytes(md_text):
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmpfile:
        tmp_path = tmpfile.name
    pypandoc.convert_text(md_text, 'docx', format='md', outputfile=tmp_path)
    with open(tmp_path, 'rb') as f:
        return f.read()


def safe_filename(name: str, default="doc.docx") -> str:
    # 只保留字母数字和下划线，防止文件名非法
    safe_name = re.sub(r'[^\w\-_. ]', '', name)
    safe_name = safe_name.strip()
    if not safe_name:
        return default
    if not safe_name.lower().endswith(".docx"):
        safe_name += ".docx"
    return safe_name


def render_export_button(md_text: str, key=None):
    file_name = "PRD.docx"
    if "uploaded_filename" in st.session_state and st.session_state["uploaded_filename"]:
        file_name = st.session_state["uploaded_filename"]
    if st.download_button(
        label="导出",
        data=markdown_to_docx_bytes(md_text),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key=key
    ):
        st.toast("导出成功！")


# 示例函数（请根据实际实现替换）
def generateprd(prompt, file_text):
    test_cases = ["主页和dongle切换","关机","音量+","音量-","上键","下键","左键","右键","OK键","自动对焦键","mute键","返回键","主页键","息屏","打开wifi","关闭wifi","打开BT","关闭BT","获取当前自动对焦状态","获取当前自动梯形状态","获取当前投影缩放比例","获取当前四点梯形坐标"]
    if file_text:
        if not st.session_state.get("file_processed", False):
            full_prompt = f"""你是一个专业的投影仪产品需求文档（PRD）助手，请严格按照以下规则，逐项逐子项对用户上传的 PRD 文档进行结构完整性检测、缺失内容提问与智能补全，确保内容完整且专业。

---

🚦 执行流程：

1. 请严格按照以下 PRD 模板结构中每一项及其子项的顺序，逐项逐子项检查用户上传的 PRD 内容；
2. 每次仅处理一个子项，不得一次性提问多个缺失内容，这个很重要；
3. 对每个子项内容判断标准如下：

   * ✅ 若该子项存在且包含有效内容（非空、非占位、非仅标题），请跳过，不提问、不修改、不扩写；
   * ❌ 若该子项缺失，或内容为空、仅有标题、或为占位词（如“无”“待补充”等），请提示用户补充；
   * 提示用户补充的时候要带上子项的标题，子项为每一项的最小项标题；

4. 对用户补充的内容，执行：

   * ✨ 智能扩写：补全上下文背景、细节与技术逻辑，多写点；
   * 💅 专业润色：符合 PRD 写作规范，表达清晰、结构严谨；

5. 展示扩写结果，并询问用户：“是否满意该内容？（是/否）”

   * 是 → **无需回复保存提示，立即检测下一个缺失的子项，继续提问；**
   * 否 → 根据用户反馈重新扩写该子项；

6. 全部子项完成后，且没有缺失项，则直接输出完整的 PRD 文档内容，不用回复其他。

---

📐 PRD 模板结构（必须逐项逐子项核查）：

```

├─ 一、前置条件
│   └─ 产品目标
├─ 二、功能需求
│   ├─ 功能清单
│   ├─ 数据指标
│   ├─ 应用场景
│   │   ├─ 使用场景（含场景规则）
│   │   ├─ 边界判断
│   │   └─ 功能与UI交互
│   └─ 结构图
├─ 三、非功能说明
│   ├─ 性能指标
│   │   ├─ 速度
│   │   └─ 可靠性
│   └─ 兼容性
├─ 四、测试方法
└─ 五、验收标准

```

---

⚠️ 内容有效性判定标准：

1. **仅有标题（例如“速度：”）但无正文内容，视为无效内容，必须提示用户补充；**

2. **内容仅包含以下占位词，视为无效：**

```

\['无', '待补充', '无内容', 'N/A', '暂无', '空', '空白', '-', '无标题']

```

3. **内容长度小于1字，且不构成完整句子，视为无效；**

4. **有效内容必须包含完整的描述性语句，能够明确表达该子项的内容或目标；**

5. **测试方法字段除了上述判断外，还必须包含下列关键词为功能点生成对应的测试用例，每一个测试用例都按TestCase001、标题、前置条件、测试步骤、期望结果列出来：**

```

\['主页和dongle切换', '关机', '音量+', '音量-', '上键', '下键', '左键', '右键', 'OK键',
'自动对焦键', 'mute键', '返回键', '主页键', '息屏', '打开wifi', '关闭wifi', '打开BT', '关闭BT', 
'获取当前自动对焦状态', '获取当前自动梯形状态', '获取当前投影缩放比例', '获取当前四点梯形坐标']

```

📌 保留用户自定义子项规则：

在处理用户提供的 PRD 文档时，可能出现非模板定义的自定义字段，请保留，例如：

- “背景介绍（可选）”
- “名词解释”
- “流程图”

```

最终请将 PRD 内容整理为清晰的 **Word 排版风格格式**，分级标题样式如下：

---

**一、前置条件**

* **产品目标：** xxx

---

**二、功能需求**

* **功能清单：** xxx
* **数据指标：** xxx

**应用场景：**

* **使用场景（含场景规则）：** xxx

* **边界判断：** xxx

* **功能：** xxx

* **UI交互：** xxx

* **结构图：** xxx

---

**三、非功能说明**

* **性能指标：**

  * **速度：** xxx
  * **可靠性：** xxx
* **兼容性：** xxx

---

**四、测试方法：**

* xxx（包含至少一个关键词）

---

**五、验收标准：**

* xxx

---

🧪 示例（仅供理解，不为提示词正文）：

- “速度：” → 无效（仅标题无内容）需补充；

- “速度：3秒内开机” → 有效，跳过；

- “测试方法：无” → 无效，需补充；

- “测试方法：包含‘关机’步骤” → 有效，跳过。

---

请严格按照以上规则执行，逐项逐子项完成 PRD 检查与补充，确保内容完整且符合专业规范。
```

用户上传的 PRD 文本如下：{file_text}"""
            # msg = send_prompt_with_timeout(full_prompt)
            response = st.session_state.chat.send_message(
            full_prompt, stream=False, generation_config=gen_config)
            st.session_state["file_processed"] = True
        else:
            # msg = send_prompt_with_timeout(prompt)
            response = st.session_state.chat.send_message(
            prompt, stream=False, generation_config=gen_config)
    else:
        if not st.session_state.get("text_processed", False):
            full_prompt = f"""你是一个专业的**投影仪产品需求文档（PRD）助手**，请根据用户提供的【产品名称】，逐项引导用户填写 PRD 内容，具体要求如下：

---

### 📋 执行规则：

1. 严格按照以下 PRD 模板结构逐项引导用户输入；
2. 用户输入后，你需对该项内容进行**扩写和润色**，使其符合专业 PRD 写作规范；
3. 扩写后，展示该项内容并询问用户是否满意：

   * 若满意，继续下一项；
   * 若不满意，根据用户反馈重新扩写，直到满意；
4. 所有项填写完毕后，生成并输出完整的 PRD 文档，排版需遵循 Word 风格结构。

---

### 📂 PRD 模板结构如下：

```
一、前置条件
└─ 产品目标

二、功能需求
├─ 功能清单
├─ 数据指标
├─ 应用场景
│   ├─ 使用场景（含场景规则）
│   ├─ 边界判断
│   └─ 功能与UI交互
└─ 结构图

三、非功能说明
├─ 性能指标
│   ├─ 速度
│   └─ 可靠性
└─ 兼容性

四、测试方法

五、验收标准
```

### ⚠️ 特别说明：测试方法字段

在校验 **“测试方法”** 字段时，请确保其内容中包含以下关键词列表中的**至少一个**，否则视为缺失：

{test_cases}

### 🧭 工作流程：

* 当前产品名称：**（由用户填写）**
* 当前模块：逐项提问 → 用户补充 → 自动扩写 → 用户确认 → 继续下一项
* 所有模块填写完毕后，输出完整 Word 风格的 PRD 文档

---

### 📄 输出排版风格要求（模拟 Word 样式）：

---

**产品名称：XXX**

---

**一、前置条件**

* **产品目标：** xxx（自动扩写后的内容）

---

**二、功能需求**

* **功能清单：** xxx
* **数据指标：** xxx

**应用场景：**

* **使用场景（含场景规则）：** xxx

* **边界判断：** xxx

* **功能：** xxx

* **UI交互：** xxx

* **结构图：** xxx

---

**三、非功能说明**

* **性能指标：**

  * **速度：** xxx
  * **可靠性：** xxx
* **兼容性：** xxx

---

**四、测试方法：**

* xxx（确保含有至少一个关键测试关键词）

---

**五、验收标准：**

* xxx

---

请根据上方逻辑，与用户开始交互，这个是产品名称：{prompt}"""
            # msg = send_prompt_with_timeout(full_prompt)
            response = st.session_state.chat.send_message(
            full_prompt, stream=False, generation_config=gen_config)
            st.session_state["text_processed"] = True
        else:
            # msg = send_prompt_with_timeout(prompt)
            response = st.session_state.chat.send_message(
            prompt, stream=False, generation_config=gen_config)

    msg = response.text
    return msg


def generate_test_case_json(user_input):
    test_case_model_path = './test_case_model.json'
    test_case_model = ""

    try:
        with open(test_case_model_path, 'r', encoding='utf-8') as file:
            test_case_model = file.read()
    except FileNotFoundError:
        print(f"Error: The file '{test_case_model_path}' was not found.")
        st.toast(f"Error: The file '{test_case_model_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
        st.toast(f"An error occurred: {e}")

    if test_case_model:
        if not st.session_state.get("test_case_processed", False):
            prompt = f"""请严格按照以下要求执行任务：

    ---

    ### 🎯 任务目标：

    你需要**仅从下面我提供的完整 JSON 模板中**，根据上方 PRD 测试方法相关的模块（通过 `moduleKey` 匹配），如果上面没有PRD测试方法，则按下面JSON模版完整输出，**原样输出所选模块的 JSON 内容**，用于后续测试代码生成。

    ---

    ### ⚠️ 严格限制：

    * **不能修改** JSON 模板中的字段名、字段值、字段顺序、嵌套结构；
    * **不能新增、删除或补全**模块、字段或案例；
    * **只能从模板中选取模块，并输出原始 JSON 内容，其他全部忽略**；
    * **输出的JSON必须为双引号的JSON；
    * **输出结果只能为 JSON 内容本身，禁止输出任何解释说明、额外文字、标点、前后缀、注释等**。

    ---

    ### ✅ 输出示例：

    仅当选中模块为 `systemControl` 与 `wifiTest` 时，应输出如下内容：

    ```json
    {[
    {
        "moduleKey": "systemControl",
        "moduleName": "系统控制",
        "features": [
        ...
        ]
    },
    {
        "moduleKey": "wifiTest",
        "moduleName": "WiFi测试",
        "features": [
        ...
        ]
    }
    ]}
    ```

    ---

    ### 📌 模板如下（只允许从此模板中选取模块，无任何改动）：

    {test_case_model}

    ---

    {user_input}

    """
            response = st.session_state.chat.send_message(
                    prompt, stream=False, generation_config=gen_config)
        else:
            # prompt = f"根据{user_input}，安照这个模版{test_case_model}选出对应的JSON测试代码"
            response = st.session_state.chat.send_message(
                user_input, stream=False, generation_config=gen_config)
        response.resolve()
        msg = response.text
        match = re.search(r'\[\s*{.*}\s*\]', msg, re.DOTALL)
        if match:
            json_str = match.group(0)  # 提取匹配到的 JSON 字符串
            try:
                # 优先尝试标准 JSON
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"解析 JSON 失败: {e}")
                try:
                    # 回退使用 ast.literal_eval 处理类 Python 格式（单引号）
                    data = ast.literal_eval(json_str)
                except Exception as e:
                    print(f"解析失败: {e}")
                    return msg
            st.session_state["test_case_processed"] = True
            st.session_state["test_case_json"] = data
            return data
    else:
        msg = "请将测试用例模版文件：test_case_model.json放到当前目录"
    return msg


def generatetestscripts(input_text):
    """
    使用 Gemini 模型根据自然语言输入生成 Linux Shell 脚本。
    """

    file_path = './test_function.sh'
    shell_save_dir = './temp'
    test_case_str = ""

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return f"Error: The file '{file_path}' was not found."
    except Exception as e:
        print(f"An error occurred: {e}")
        return f"An error occurred: {e}"

    if st.session_state.get("test_case_processed"):
        st.session_state["test_case_processed"] = False
        data = st.session_state["test_case_json"]
        step_list = jsonpath.jsonpath(data, '$..steps') or []
        if step_list:
            for step in step_list:
                test_case_str = ';'.join(map(str, step))

    print(test_case_str)

    prompt = f"""
你是一个熟练的 Linux Shell 脚本工程师，请根据以下自然语言描述生成一个完整的 Bash 脚本：

执行规则：
    1、优先从函数库中选择测试函数：如果函数库中存在可直接用于测试的函数，优先调用这些函数，不要修改函数的任何逻辑，直接调用即可。
    2、若库中无合适函数，则自动生成测试用例：生成的测试用例应独立、可执行。
    3、禁止使用 adb shell 关键字，没有用到的函数不用显示出来，简洁易懂。
    4、输出格式（根据需求选择）：脚本以 #!/bin/sh 开头。
    5、函数库如下：
{content}

需求描述：
{test_case_str}\n
{input_text}

请输出正确调用函数的脚本内容。
"""
    prompt2 = f"""
你是一个熟练的 Linux Shell 脚本工程师，请根据以下自然语言描述生成一个完整的 Bash 脚本：

需求描述：
{input_text}

请输出修改后的脚本内容，仅提供代码就可以了。
"""

    if not st.session_state.get("shell_processed", False):
        response = st.session_state.chat.send_message(prompt, stream=True)
        st.session_state["shell_processed"] = True
    else:
        response = st.session_state.chat.send_message(prompt2, stream=True)

    response.resolve()
    os.makedirs(shell_save_dir, exist_ok=True)
    shell_save_path = os.path.join(shell_save_dir, "ai_tmp.sh")
    shell_file_content = response.text.removeprefix("```bash").strip()
    backtick_pos = shell_file_content.find('```')
    if backtick_pos != -1:
        last_file_content = shell_file_content[:backtick_pos]
        with open(shell_save_path, "w", newline='\n', encoding="utf-8") as f:
            f.write(last_file_content)

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
    tmp_shell_path = Path('./temp/ai_tmp.sh').resolve()
    result = subprocess.run(["adb", "push", tmp_shell_path, "sdcard"], shell=True)
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
        save_dir = "screen"
        os.makedirs(save_dir, exist_ok=True)
        tmp_cap_path = Path('./screen/').resolve()
        result = subprocess.run(["adb", "pull", "sdcard/cap.png", tmp_cap_path], shell=True)
        if result.returncode == 0:
            image = Image.open("./screen/cap.png")
            st.image(image, caption='设备当前显示内容', use_container_width=True)
    else:
        exe_msg = "脚本执行失败，请确认是否ADB连接上了设备"
        st.chat_message("assistant").write(exe_msg)


def debug_logcat_file(input_text):
    log_path = './log/system_log.txt'
    logcat_sh_path = os.path.join(os.path.dirname(__file__), "logcat.sh")

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
            use_time = 0

    match = re.search(r'TAG=([a-zA-Z]+)', input_text)
    if match:
        tag = match.group(1)
    else:
        tag = "null"

    with open(logcat_sh_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if use_time != 0:
            modified_content = re.sub(r'sleep \d+', "sleep " + str(use_time), content)
        else:
            use_time = 5
            first_content = re.sub(r'logcat -c', "", content)
            modified_content = re.sub(r'sleep \d+', "sleep " + str(use_time), first_content)

        if tag != "null":
            last_content = re.sub(r'LOG_TAG="([a-zA-Z]+)"', "LOG_TAG=" + '"' + tag + '"', modified_content)
        else:
            last_content = re.sub(r'LOG_TAG="([a-zA-Z]+)"', 'LOG_TAG="AndroidRuntime | DEBUG"', modified_content)

    with open(logcat_sh_path, 'w', newline='\n', encoding='utf-8') as f:
        if tag != "null":
            f.write(last_content)
        else:
            f.write(modified_content)

    result = subprocess.run(["adb", "push", logcat_sh_path, "sdcard"], shell=True)
    if result.returncode == 0:
        result = subprocess.run('adb shell "nohup sh sdcard/logcat.sh > /dev/null 2>&1 &"', shell=True)
        if result.returncode == 0:
            sleep_time(use_time)
            save_dir = "log"
            os.makedirs(save_dir, exist_ok=True)
            tmp_log_path = Path('./log/').resolve()
            result = subprocess.run(["adb", "pull", r"sdcard/system_log.txt", tmp_log_path], shell=True)
            if result.returncode == 0:
                print("system_log.txt pull success")
            else:
                print("system_log.txt pull failed")
        else:
            print("logcat.sh run failed")
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
    
    """

    response = st.session_state.chat.send_message(prompt, stream=True)
    response.resolve()
    return response.text



# PRD 模式系统提示
roleprompt = """
你好，我可以帮你，生成PRD测试文档，生成测试用例，写测试shell脚本，Debug日志分析:\n
请在左侧栏中选择对应的输入模式：\n
PRD模式：生成PRD测试文档 \n
TestCase模式：生成测试用例 \n
Shell模式：写测试shell脚本 \n
Debug：日志分析 \n

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


def reset_select_options():
    st.session_state.select_option = "Auto"


with st.sidebar:
    option = st.selectbox('选择您的模型', ('gemini-2.0-flash', 'gemini-2.0-flash-lite'))

    if 'model' not in st.session_state or st.session_state.model != option:
        st.session_state.chat = genai.GenerativeModel(option).start_chat(history=[])
        st.session_state.model = option

    st.write("在此处调整您的参数:")
    temperature = st.number_input("温度", min_value=0.0, max_value=1.0, value=0.5, step=0.01)
    max_token = st.number_input("最大输出令牌数", min_value=0, value=10000)
    gen_config = genai.types.GenerationConfig(max_output_tokens=max_token, temperature=temperature)
    if 'select_option' not in st.session_state:
        st.session_state.select_option = "Auto"
    input_mode = st.selectbox(
        label='请选择输入模式：',
        options=('Auto', 'Prd', 'TestCase', 'Shell', 'Debug'),
        index=0,
        format_func=str,
        key='select_option'
    )
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

            if input_mode == "Prd":
                st.session_state.chat_mode = input_mode
                msg = generateprd("", file_text)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.chat_message("assistant").write(msg)

    st.divider()

    if st.button("清除聊天历史", on_click=reset_select_options):
        st.session_state.messages = [{"role": "system", "content": roleprompt}]
        st.session_state.chat_mode = "Auto"
        st.session_state["uploaded_filename"] = ""

# 初始化聊天状态
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": roleprompt}]
if "chat_mode" not in st.session_state:
    st.session_state["chat_mode"] = "Auto"

# 显示历史记录
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 处理用户输入
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # 切换模式
    # prompt_lower = prompt.lower()
    # if prompt_lower.startswith("prd@"):
    #     st.session_state["chat_mode"] = "Prd"
    #     st.session_state["file_processed"] = False
    #     st.session_state["text_processed"] = False
    #     user_input = prompt.removeprefix("Prd@").strip()
    # elif prompt_lower.startswith("testcase@"):
    #     st.session_state["chat_mode"] = "TestCase"
    #     st.session_state["test_case_processed"] = False
    #     user_input = prompt.removeprefix("TestCase@").strip()
    # elif prompt_lower.startswith("test@"):
    #     st.session_state["chat_mode"] = "Test"
    #     count_script = 0
    #     user_input = prompt.removeprefix("Test@").strip()
    # elif prompt_lower.startswith("debug@"):
    #     st.session_state["chat_mode"] = "Debug"
    #     user_input = prompt.removeprefix("Debug@").strip()
    # else:
    #     user_input = prompt
    #     count_script = 1

    if input_mode != st.session_state.chat_mode:
        st.session_state.chat_mode = input_mode
        if input_mode == "Prd":
            st.session_state["file_processed"] = False
            st.session_state["text_processed"] = False
        elif input_mode == "TestCase":
            st.session_state["test_case_processed"] = False
        elif input_mode == "Shell":
            st.session_state["shell_processed"] = False
        elif input_mode == "Debug":
            st.session_state["debug_processed"] = False

    # 根据模式处理输入
    if st.session_state["chat_mode"] == "Prd":
        msg = generateprd(prompt, file_text)

    elif st.session_state["chat_mode"] == "TestCase":
        msg = generate_test_case_json(prompt)

    elif st.session_state["chat_mode"] == "Shell":
        msg = generatetestscripts(prompt)

    elif st.session_state["chat_mode"] == "Debug":
        msg = debug_logcat_file(prompt)
    else:
        response = st.session_state.chat.send_message(prompt, stream=True)
        response.resolve()
        msg = response.text

    st.session_state.messages.append({"role": "assistant", "content": msg})
    st.chat_message("assistant").write(msg)

# 保存 PRD 按钮
# if st.session_state["chat_mode"] == "Prd":
#     if st.button("保存修改的PRD到本地文件"):
#         last_assistant_msg = None
#         for message in reversed(st.session_state.messages):
#             if message["role"] == "assistant":
#                 last_assistant_msg = message["content"]
#                 break

#         if last_assistant_msg:
#             save_dir = "D:/LLM_Gemini_Pro_Streamlit/"
#             os.makedirs(save_dir, exist_ok=True)
#             save_path = os.path.join(save_dir, "修改后的PRD.txt")

#             with open(save_path, "w", encoding="utf-8") as f:
#                 f.write(last_assistant_msg)

#             st.success(f"PRD 已保存到本地文件: {save_path}")
#         else:
#             st.warning("没有找到可以保存的回复内容。")

if st.session_state["chat_mode"] == "Shell":
    if st.button("执行脚本"):
        run_scripts()
elif st.session_state["chat_mode"] == "Prd":
    messages = st.session_state.messages
    if len(messages) > 0 and messages[len(messages) - 1]["role"] == "assistant":
        render_export_button(messages[len(messages) - 1]["content"], "export_doc")