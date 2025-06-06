#!/bin/sh

# --- 配置参数 ---
LOG_FILE="/sdcard/keypad_test.log"

# --- 变量初始化 ---
TEST_START_TIME=$(date +"%Y-%m-%d_%H-%M-%S")

# --- 函数定义 ---

# 按确认键
enter_keypad_ok() {
  echo "模拟按下确认键..." | tee -a "$LOG_FILE"
  input keyevent 23
}

# --- 主程序 ---

# 记录测试开始时间
echo "测试开始时间: $TEST_START_TIME" | tee -a "$LOG_FILE"

# 循环按确认键5次
for i in $(seq 1 5); do
    echo "第 $i 次按下确认键..." | tee -a "$LOG_FILE"
    enter_keypad_ok
    sleep 1 # 每次按键后等待1秒
done

# 记录测试结束时间
TEST_END_TIME=$(date +"%Y-%m-%d_%H-%M-%S")
echo "测试结束时间: $TEST_END_TIME" | tee -a "$LOG_FILE"
echo "测试已完成." | tee -a "$LOG_FILE"