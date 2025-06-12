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
import pypandoc
import tempfile
import json


count_script = 0

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
    test_cases = ["主页和dongle切换","设置键","关机","音量+","音量-","上键","下键","左键","右键","OK键","自动对焦键","FOCUS+","FOCUS-","mute键","返回键","主页键","进入蓝牙音响","息屏","进入老化","退出老化","打开wifi","关闭wifi","打开BT","关闭BT","root权限","恢复出厂","获取版本号","获取机器设备型号","获取有线mac","获取当前自动对焦状态","获取当前自动梯形状态","获取当前投影缩放比例","获取当前四点梯形坐标","获取wifi驱动加载状态","获取有线插入状态"]
    if file_text:
        if not st.session_state.get("file_processed", False):
            full_prompt = f"""你是一个专业的投影仪产品需求文档（PRD）助手。请严格按照以下 PRD 模板结构，**逐项核查用户上传的 PRD 文本内容是否完整**：

* 对于已填写的内容，**无需修改，直接跳过**；
* 对于缺失或为空的字段，**逐项向用户提问补充内容**；
* 用户补充后，你需要对该项内容进行**智能扩写与润色**，使其符合标准 PRD 写作规范；
* 每次扩写完成后，展示当前项的更新内容，并询问用户是否满意：

  * 用户满意 → 进入下一项检查；
  * 用户不满意 → 根据用户反馈重新扩写；
* 所有项完成后，生成并输出完整的 PRD 文档，**使用 Word 风格排版（非 Markdown）**。

---

### 📐 PRD 模板结构如下：

```
PRD规范制定
├─ 一、前置条件
│   └─ 产品目标
├─ 二、功能需求
│   ├─ 功能清单
│   ├─ 数据指标
│   ├─ 应用场景
│   │   ├─ 使用场景（含场景规则）
│   │   ├─ 边界判断
│   │   ├─ 功能
│   │   └─ UI交互
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

### ⚠️ 特别说明：测试方法字段

在校验 **“测试方法”** 字段时，请确保其内容中包含以下关键词列表中的**至少一个**，否则视为缺失：

{test_cases}

### 📄 输出格式要求（Word 文档风格）

最终请将 PRD 内容整理为清晰的 **Word 排版风格格式**，分级标题样式如下：

---

**PRD规范制定**

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

### ✅ 执行流程示例：

1. 你提问：“请补充【产品目标】部分的内容”
2. 用户回答：“目标是优化用户首页加载速度”
3. 你返回：

> **产品目标（已扩写）：**
> 本产品旨在优化用户首页的加载速度，提升页面响应效率与整体交互体验，确保在网络条件一般的环境下，首页加载时间控制在 2 秒以内，从而增强用户粘性和满意度。

4. 然后询问用户：“是否满意该内容？（是/否）”

   * 是 → 进入下一项
   * 否 → 询问意见并重新扩写

---

用户上传的 PRD 文本如下：{file_text}"""
            response = st.session_state.chat.send_message(
            full_prompt, stream=False, generation_config=gen_config)
            st.session_state["file_processed"] = True
        else:
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
│   ├─ 功能
│   └─ UI交互
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
            response = st.session_state.chat.send_message(
            full_prompt, stream=False, generation_config=gen_config)
            st.session_state["text_processed"] = True
        else:
            response = st.session_state.chat.send_message(
            prompt, stream=False, generation_config=gen_config)

    response.resolve()
    msg = response.text
    return msg

def generate_test_case_json(user_input):
    test_case_model = [{"moduleKey":"systemControl","moduleName":"系统控制","features":[{"featureKey":"homeDongleSwitch","featureName":"主页和dongle切换"},{"featureKey":"settingsKey","featureName":"设置键"},{"featureKey":"powerOff","featureName":"关机"},{"featureKey":"volumeUp","featureName":"音量+"},{"featureKey":"volumeDown","featureName":"音量-"},{"featureKey":"keyUp","featureName":"上键"},{"featureKey":"keyDown","featureName":"下键"},{"featureKey":"keyLeft","featureName":"左键"},{"featureKey":"keyRight","featureName":"右键"},{"featureKey":"okKey","featureName":"OK键"},{"featureKey":"autoFocusKey","featureName":"自动对焦键"},{"featureKey":"focusPlus","featureName":"FOCUS+"},{"featureKey":"focusMinus","featureName":"FOCUS-"},{"featureKey":"muteKey","featureName":"mute键"},{"featureKey":"backKey","featureName":"返回键"},{"featureKey":"homeKey","featureName":"主页键"}]},{"moduleKey":"audioBluetooth","moduleName":"音频与蓝牙","features":[{"featureKey":"enterBluetoothSpeaker","featureName":"进入蓝牙音响"},{"featureKey":"bluetoothOpen","featureName":"打开BT"},{"featureKey":"bluetoothClose","featureName":"关闭BT"}]},{"moduleKey":"powerScreen","moduleName":"电源与屏幕","features":[{"featureKey":"screenOff","featureName":"息屏"},{"featureKey":"enterAging","featureName":"进入老化"},{"featureKey":"exitAging","featureName":"退出老化"}]},{"moduleKey":"wifiTest","moduleName":"WiFi测试","features":[{"featureKey":"openWifi","featureName":"打开WiFi","cases":[{"caseKey":"openFromSettings","caseName":"从设置中打开WiFi","steps":["1、打开设置","2、选择WiFi选项","3、关闭WiFi开关按钮","4、等待5秒，测试网络是否可用","5、重新打开WiFi开关按钮","6、测试网络是否可用"],"expected":"WiFi关闭后网络不可用，开启后恢复连接"},{"caseKey":"openFromDropdown","caseName":"从下拉状态栏中打开"}]},{"featureKey":"closeWifi","featureName":"关闭WiFi","cases":[{"caseKey":"closeFromSettings","caseName":"从设置中关闭WiFi"},{"caseKey":"closeFromDropdown","caseName":"从下拉状态栏中关闭WiFi"}]},{"featureKey":"wifiStability","featureName":"WiFi稳定性测试","cases":[{"caseKey":"reconnectAfterDisconnection","caseName":"断网后自动重连测试","steps":["1、打开设置","2、选择 WiFi 选项","3、关闭 WiFi 开关按钮","4、等待 10 秒","5、打开 WiFi 开关按钮","6、等待 10 秒","7、重复步骤 3、4、5 共执行 10 次","8、最后确认网络是否可用"]}]}]},{"moduleKey":"bluetoothTest","moduleName":"蓝牙测试","features":[{"featureKey":"","featureName":"","cases":[{"caseKey":"","caseName":"","steps":["1、","2、"],"expected":""},{"caseKey":"","caseName":""}]},{"featureKey":"","featureName":"","cases":[{"caseKey":"","caseName":""},{"caseKey":"","caseName":""}]},{"featureKey":"","featureName":"","cases":[{"caseKey":"","caseName":"","steps":["1、","2、"]}]}]},{"moduleKey":"systemAccess","moduleName":"系统权限与恢复","features":[{"featureKey":"rootPermission","featureName":"root权限"},{"featureKey":"factoryReset","featureName":"恢复出厂"}]},{"moduleKey":"deviceInfo","moduleName":"设备信息获取","features":[{"featureKey":"getVersion","featureName":"获取版本号"},{"featureKey":"getDeviceModel","featureName":"获取机器设备型号"},{"featureKey":"getWiredMac","featureName":"获取有线mac"},{"featureKey":"getAutoFocusStatus","featureName":"获取当前自动对焦状态"},{"featureKey":"getTrapezoidStatus","featureName":"获取当前自动梯形状态"},{"featureKey":"getProjectionZoom","featureName":"获取当前投影缩放比例"},{"featureKey":"getTrapezoidCoordinates","featureName":"获取当前四点梯形坐标"},{"featureKey":"getWifiDriverStatus","featureName":"获取wifi驱动加载状态"},{"featureKey":"getWiredPlugStatus","featureName":"获取有线插入状态"}]}]
    if not st.session_state.get("test_case_processed", False):
        prompt = f"""请严格按照以下要求执行任务：

---

### 🎯 任务目标：

你需要**仅从下面我提供的完整 JSON 模板中**，选取与上方 PRD 测试方法相关的模块（通过 `moduleKey` 匹配），**原样输出所选模块的 JSON 内容**，用于后续测试代码生成。

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
            data = json.loads(json_str)
            st.session_state["test_case_processed"] = True
            st.session_state["test_case_json"] = data
            return data
        except json.JSONDecodeError as e:
            print(f"解析 JSON 失败: {e}")
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
    except Exception as e:
        print(f"An error occurred: {e}")

    if st.session_state.get("test_case_processed"):
        data = st.session_state["test_case_json"]
        for item in data:
            features = item.get("features", [])
            for feature in features:
                cases = feature.get("cases", [])
                for case in cases:
                    steps = case.get("steps", [])
                    test_case_str = ';'.join(map(str, steps))
                    print(test_case_str)


    prompt = f"""
你是一个熟练的 Linux Shell 脚本工程师，请根据以下自然语言描述生成一个完整的 Bash 脚本：

需求描述：
{content}这是一个函数调用库，请优先从函数库中选择测试使用的函数，如果没有就自动生成，但是不要使用“adb shell”关键字\n
{test_case_str}
{input_text}

请输出正确调用函数的脚本内容，当前测试中没有用到的函数不用显示出来，简洁易懂，脚本以 #!/bin/sh 开头。
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
            use_time = 0

    match = re.search(r'TAG=([a-zA-Z]+)', input_text)
    if match:
        tag = match.group(1)
    else:
        tag = "null"

    with open('./temp/logcat.sh', 'r', encoding='utf-8') as f:
        content = f.read()
        if use_time != 0:
            modified_content = re.sub(r'sleep \d+', "sleep " + str(use_time), content)
        else:
            use_time = 5
            first_content = re.sub(r'logcat -c', "", content)
            modified_content = re.sub(r'sleep \d+', "sleep " + str(use_time), first_content)

        if tag != "null":
            last_content = re.sub(r'LOG_TAG="([a-zA-Z]+)"', "LOG_TAG=" + '"' + tag + '"', modified_content)

    with open('./temp/logcat.sh', 'w', newline='\n', encoding='utf-8') as f:
        if tag != "null":
            f.write(last_content)
        else:
            f.write(modified_content)

    result = subprocess.run(["adb", "push", r"E:\py_project\AI-gemini\temp\logcat.sh", "sdcard"], shell=True)
    if result.returncode == 0:
        result = subprocess.run('adb shell "nohup sh sdcard/logcat.sh > /dev/null 2>&1 &"', shell=True)
        if result.returncode == 0:
            print("logcat.sh 脚本执行中。。。")
            sleep_time(use_time)
            print("logcat.sh 脚本执行结束")
            result = subprocess.run(["adb", "pull", r"sdcard/system_log.txt", r"E:\py_project\AI-gemini\log"], shell=True)
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
请在输入任务前加以下前缀来开启任务：\n
PRD@：生成PRD测试文档 \n
TestCase@：生成测试用例 \n
Test@：写测试shell脚本 \n
Debug@：日志分析 \n

例如：Test@请写一个测试按音量加键5次的shell脚本 \n
PRD@请生成一个测试按音量加键5次的测试文档 \n
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

            if st.session_state["chat_mode"] == "Prd":
                msg = generateprd("", file_text)
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.chat_message("assistant").write(msg)

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
    prompt_lower = prompt.lower()
    if prompt_lower.startswith("prd@"):
        st.session_state["chat_mode"] = "Prd"
        st.session_state["file_processed"] = False
        st.session_state["text_processed"] = False
        user_input = prompt.removeprefix("Prd@").strip()
    elif prompt_lower.startswith("testcase@"):
        st.session_state["chat_mode"] = "TestCase"
        st.session_state["test_case_processed"] = False
        user_input = prompt.removeprefix("TestCase@").strip()
    elif prompt_lower.startswith("test@"):
        st.session_state["chat_mode"] = "Test"
        count_script = 0
        user_input = prompt.removeprefix("Test@").strip()
    elif prompt_lower.startswith("debug@"):
        st.session_state["chat_mode"] = "Debug"
        user_input = prompt.removeprefix("Debug@").strip()
    else:
        user_input = prompt
        count_script = 1

    # 根据模式处理输入
    if st.session_state["chat_mode"] == "Prd":
        msg = generateprd(user_input, file_text)

    elif st.session_state["chat_mode"] == "TestCase":
        msg = generate_test_case_json(user_input)

    elif st.session_state["chat_mode"] == "Test":
        msg = generatetestscripts(user_input)

    elif st.session_state["chat_mode"] == "Debug":
        msg = debug_logcat_file(user_input)

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

if st.session_state["chat_mode"] == "Test":
    if st.button("执行脚本"):
        run_scripts()
elif st.session_state["chat_mode"] == "Prd":
    messages = st.session_state.messages
    if len(messages) > 0 and messages[len(messages) - 1]["role"] == "assistant":
        render_export_button(messages[len(messages) - 1]["content"], "export_doc")