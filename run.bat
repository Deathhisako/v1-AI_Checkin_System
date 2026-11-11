@echo off
REM AI辅助自动化生活类签到系统 - Windows 启动脚本
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo  AI辅助自动化生活类签到系统 (v0.6.8)
echo ==========================================
echo  [1] 单轮签到 (演示模式)
echo  [2] 连续演示 20 轮 (观察自愈闭环)
echo  [3] 对比实验 (AI方案 vs 传统脚本)
echo  [4] 运行单元测试
echo  [5] 退出
echo ==========================================
set /p choice=请输入选项 (1-5): 

if "%choice%"=="1" python main.py
if "%choice%"=="2" python main.py --demo 20
if "%choice%"=="3" python main.py --compare 100
if "%choice%"=="4" python -m unittest discover -s tests -v
if "%choice%"=="5" exit /b 0
pause
