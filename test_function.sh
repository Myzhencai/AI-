#!/bin/sh

# --- 配置参数 ---
PING_TARGET="183.2.172.177" # 用于验证网络连接的IP地址
LOG_FILE="/sdcard/wifi_stability_test.log"
TEST_COUNTS=5

# --- 函数定义 ---

# 获取WiFi状态
get_wifi_state() {
    return "$(settings get global wifi_on)"
}

# 开启WiFi
enable_wifi() {
    echo "尝试开启WiFi..." | tee -a "$LOG_FILE"
    settings put global wifi_on 1
}

# 关闭WiFi
disable_wifi() {
    echo "尝试关闭WiFi..." | tee -a "$LOG_FILE"
    settings put global wifi_on 0
}

# 验证网络连接
check_network_connection() {
    ret=$(ping -c 3 "$PING_TARGET")
    if [[ $(echo "$ret" | grep "3 received") != "" ]]; then
        return 0 # 成功
    else
        return 1 # 失败
    fi
}

# 回到主界面
return_to_home() {
  input keyevent KEYCODE_HOME
}

# 按方向键上键
enter_keypad_up() {
  input keyevent KEYCODE_DPAD_UP
}

# 按方向键下键
enter_keypad_down() {
  input keyevent KEYCODE_DPAD_DOWN
}

# 按方向键左键
enter_keypad_left() {
  input keyevent KEYCODE_DPAD_LEFT
}

# 按方向键右键
enter_keypad_right() {
  input keyevent KEYCODE_DPAD_RIGHT
}

# 按确认键
enter_keypad_ok() {
  input keyevent KEYCODE_DPAD_CENTER
}

# 打开系统设置
open_system_settings() {
  input keyevent KEYCODE_SETTINGS
}

# 设置中选择WiFi设置选项
settings_select_wifi_option() {
  open_system_settings

  enter_keypad_right
  sleep 1
}

# 开关WiFi测试
settings_open_and_close_wifi_test() {
  settings_select_wifi_option

  get_wifi_state
  if [ $? -eq 0 ]; then
    echo "当前WiFi是关闭状态"
  else
    echo "当前WiFi是开启状态"
  fi
  for i in $(seq 1 $TEST_COUNTS); do
    enter_keypad_ok
    sleep 10
    check_network_connection
    if [ $? -eq 0 ]; then
        echo "第 $i 次，wifi已打开，网络正常"
    else
        echo "第 $i 次，wifi已关闭，网络异常"
    fi
    sleep 1
  done

}

# 获取自动对焦开关状态
get_autoFocus_status() {
  return "$(getprop persist.sys.puture.autofocus)"
}

# 获取自动梯形开关状态
get_autoKeystone_status() {
  return "$(getprop persist.sys.puture.autokeystone)"
}

# 设置中，选择自动梯形开关选项
settings_select_autoKeystone_option() {
  open_system_settings

  for i in $(seq 1 3) ; do
    enter_keypad_down
    sleep 1
  done
  enter_keypad_right
  sleep 1
  enter_keypad_down
  sleep 1
}

# 设置中，选择自动对焦开关选项
settings_select_autofocus_option() {
  open_system_settings

  for i in $(seq 1 3) ; do
    enter_keypad_down
    sleep 1
  done
  enter_keypad_right
  sleep 1
  for i in $(seq 1 3) ; do
    enter_keypad_down
    sleep 1
  done
}

# 自动梯形开关测试
settings_open_and_close_autoKeystone_test() {
  settings_select_autoKeystone_option

  get_autoKeystone_status
  if [ $? -eq 0 ]; then
    echo "当前自动梯形是关闭状态"
  else
    echo "当前自动梯形是开启状态"
  fi

  for i in $(seq 1 $TEST_COUNTS) ; do
    enter_keypad_ok
    sleep 1
    get_autoKeystone_status
    if [ $? -eq 1 ]; then
        echo "第 $i 次, 打开自动梯形"
    else
      echo "第 $i 次, 关闭自动梯形"
    fi
    sleep 1
  done
}

# 自动对焦开关测试
settings_open_and_close_autofocus_test() {
  settings_select_autofocus_option

  get_autoFocus_status
  if [ $? -eq 0 ]; then
    echo "当前自动对焦是关闭状态"
  else
    echo "当前自动对焦是开启状态"
  fi

  for i in $(seq 1 $TEST_COUNTS) ; do
    enter_keypad_ok
    sleep 1
    get_autoFocus_status
    if [ $? -eq 1 ]; then
        echo "第 $i 次, 打开自动对焦"
    else
      echo "第 $i 次, 关闭自动对焦"
    fi
    sleep 1
  done
}

# 获取投影模式
get_projector_mode() {
  return "$(getprop persist.sys.puture.mirrorMode)"
}

# 在设置中，选择投影模式设置选项
settings_select_projector_mode_option() {
  open_system_settings

  for i in $(seq 1 3) ; do
    enter_keypad_down
    sleep 1
  done
  enter_keypad_right
  sleep 1
  enter_keypad_ok
  sleep 1
}

# 投影模式设置测试
settings_projector_mode_test() {
  settings_select_projector_mode_option
  get_projector_mode
  if [ $? -eq 0 ]; then
    echo "当前是正装正投模式"
  else
    echo "请调整当前投影模式为正装正投模式再重试"
    return
  fi

  for i in $(seq 1 3) ; do
    enter_keypad_down
    sleep 1
    enter_keypad_ok
    sleep 1
    get_projector_mode
    case $? in
    2)
      echo "当前是正装背投模式"
      ;;
    3)
      echo "当前是吊装正投模式"
      ;;
    1)
      echo "当前是吊装背投模式"
      ;;
    esac
  done
}