#!/bin/sh

# --- 配置参数 ---
PING_TARGET="8.8.8.8" # 用于验证网络连接的IP地址
LOG_FILE="/sdcard/wifi_stability_test.log"

# --- 变量初始化 ---
TEST_START_TIME=$(date +"%Y-%m-%d_%H-%M-%S")

# --- 函数定义 ---

# 获取WiFi状态
get_wifi_state() {
    # Android 10+ command
    adb shell cmd -X wifi get-wifi-state | grep -oE "\[(ENABLED|DISABLED)\]"
    # Older Android versions
    # adb shell settings get global wifi_on
}

# 开启WiFi
enable_wifi() {
    echo "尝试开启WiFi..." | tee -a "$LOG_FILE"
    # Android 10+ command
    adb shell cmd -X wifi enable
    # Older Android versions
    # adb shell settings put global wifi_on 1
    sleep 1 # Give some time for the command to register
}

# 关闭WiFi
disable_wifi() {
    echo "尝试关闭WiFi..." | tee -a "$LOG_FILE"
    # Android 10+ command
    adb shell cmd -X wifi disable
    # Older Android versions
    # adb shell settings put global wifi_on 0
    sleep 1 # Give some time for the command to register
}

# 验证网络连接
check_network_connection() {
    adb shell ping -c 3 "$PING_TARGET" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        return 0 # 成功
    else
        return 1 # 失败
    fi
}

# 回到主界面
return_to_home() {
  input keyevent 3
}

# 按方向键上键
enter_keypad_up() {
  input keyevent 19;
}

# 按方向键下键
enter_keypad_down() {
  input keyevent 20;
}

# 按方向键左键
enter_keypad_left() {
  input keyevent 21;
}

# 按方向键右键
enter_keypad_right() {
  input keyevent 22;
}

# 按确认键
enter_keypad_ok() {
  input keyevent 23;
}