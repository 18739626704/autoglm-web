# -*- coding: utf-8 -*-
"""
AutoGLM Web服务器
提供环境检测、API Key管理和Agent执行功能
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# 获取项目根目录（所有资源都在同一目录下）
BASE_DIR = Path(__file__).parent.absolute()
OPEN_AUTOGLM_DIR = BASE_DIR / "Open-AutoGLM"
PLATFORM_TOOLS_DIR = BASE_DIR / "platform-tools"
APK_DIR = BASE_DIR / "apk"
CONFIG_FILE = BASE_DIR / "config.json"

app = Flask(__name__, static_folder='static')
CORS(app)

# 全局变量存储当前任务状态
current_task = {
    "running": False,
    "logs": [],
    "result": None
}


def get_default_config():
    """获取默认配置"""
    return {
        "current_provider": "bigmodel",
        "providers": {
            "bigmodel": {
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "autoglm-phone",
                "api_key": ""
            },
            "modelscope": {
                "base_url": "https://api-inference.modelscope.cn/v1",
                "model": "ZhipuAI/AutoGLM-Phone-9B",
                "api_key": ""
            },
            "custom": {
                "base_url": "http://localhost:8000/v1",
                "model": "autoglm-phone-9b",
                "api_key": ""
            }
        }
    }


def load_config():
    """加载配置文件"""
    default = get_default_config()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 兼容旧版本配置格式
            if 'providers' not in config:
                # 将旧配置迁移到新格式
                old_key = config.get('api_key', '')
                old_base_url = config.get('base_url', '')
                old_model = config.get('model', '')
                config = default.copy()
                if old_key:
                    config['providers']['bigmodel']['api_key'] = old_key
                if old_base_url:
                    config['providers']['bigmodel']['base_url'] = old_base_url
                if old_model:
                    config['providers']['bigmodel']['model'] = old_model
            else:
                # 确保所有服务商都存在
                for provider in default['providers']:
                    if provider not in config['providers']:
                        config['providers'][provider] = default['providers'][provider]
            return config
    return default


def get_current_provider_config():
    """获取当前服务商的配置"""
    config = load_config()
    provider = config.get('current_provider', 'bigmodel')
    return config['providers'].get(provider, config['providers']['bigmodel'])


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_adb_path():
    """获取ADB路径"""
    adb_exe = PLATFORM_TOOLS_DIR / "adb.exe"
    if adb_exe.exists():
        return str(adb_exe)
    return "adb"  # 尝试系统PATH中的adb


def restart_adb_server():
    """重启ADB服务器，解决版本冲突问题"""
    adb = get_adb_path()
    
    # 使用我们的ADB重启服务器（不再用taskkill，因为用户已修复冲突问题）
    run_command(f'"{adb}" kill-server', timeout=10)
    time.sleep(1)
    result = run_command(f'"{adb}" start-server', timeout=15)
    time.sleep(1)
    
    # 触发设备检测
    run_command(f'"{adb}" devices', timeout=10)
    
    return result


def run_command(cmd, timeout=30):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
            encoding='utf-8',
            errors='replace'
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== 静态文件 ====================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


# ==================== 环境检测API ====================

@app.route('/api/check/python', methods=['GET'])
def check_python():
    """检测Python环境"""
    result = run_command('python --version')
    if result.get('success'):
        version = result['stdout'] or result['stderr']
        return jsonify({
            "installed": True,
            "version": version,
            "message": f"Python已安装: {version}"
        })
    return jsonify({
        "installed": False,
        "message": "Python未安装",
        "help": "请访问 https://www.python.org/downloads/ 下载安装Python 3.10+，安装时请勾选 'Add Python to PATH'"
    })


@app.route('/api/check/dependencies', methods=['GET'])
def check_dependencies():
    """检测Python依赖"""
    required = ['flask', 'flask_cors', 'PIL', 'openai', 'requests']
    missing = []
    installed = []
    
    for pkg in required:
        try:
            if pkg == 'PIL':
                __import__('PIL')
            else:
                __import__(pkg)
            installed.append(pkg)
        except ImportError:
            missing.append(pkg)
    
    return jsonify({
        "installed": installed,
        "missing": missing,
        "all_installed": len(missing) == 0,
        "message": "所有依赖已安装" if len(missing) == 0 else f"缺少依赖: {', '.join(missing)}"
    })


@app.route('/api/install/dependencies', methods=['POST'])
def install_dependencies():
    """安装Python依赖"""
    requirements_file = BASE_DIR / "requirements.txt"
    if not requirements_file.exists():
        return jsonify({"success": False, "error": "requirements.txt不存在"})
    
    result = run_command(f'pip install -r "{requirements_file}"', timeout=300)
    return jsonify({
        "success": result.get('success', False),
        "output": result.get('stdout', '') + '\n' + result.get('stderr', ''),
        "error": result.get('error')
    })


@app.route('/api/check/open-autoglm', methods=['GET'])
def check_open_autoglm():
    """检测Open-AutoGLM"""
    main_py = OPEN_AUTOGLM_DIR / "main.py"
    phone_agent = OPEN_AUTOGLM_DIR / "phone_agent"
    
    return jsonify({
        "installed": main_py.exists() and phone_agent.exists(),
        "path": str(OPEN_AUTOGLM_DIR),
        "message": "Open-AutoGLM已就绪" if main_py.exists() else "Open-AutoGLM未找到"
    })


@app.route('/api/check/platform-tools', methods=['GET'])
def check_platform_tools():
    """检测platform-tools (ADB)"""
    adb_exe = PLATFORM_TOOLS_DIR / "adb.exe"
    
    if adb_exe.exists():
        result = run_command(f'"{adb_exe}" version')
        version = result.get('stdout', '').split('\n')[0] if result.get('success') else ''
        return jsonify({
            "installed": True,
            "path": str(PLATFORM_TOOLS_DIR),
            "version": version,
            "message": f"ADB已就绪: {version}"
        })
    
    return jsonify({
        "installed": False,
        "message": "platform-tools未找到"
    })


@app.route('/api/adb/restart', methods=['POST'])
def api_restart_adb():
    """重启ADB服务器"""
    result = restart_adb_server()
    return jsonify({
        "success": True,
        "message": "ADB服务器已重启",
        "output": result.get('stdout', '') + result.get('stderr', '')
    })


@app.route('/api/adb/scan', methods=['GET'])
def scan_adb_files():
    """扫描系统中的所有adb.exe文件"""
    
    # 我们使用的ADB路径（规范化为小写用于比较）
    our_adb = str(PLATFORM_TOOLS_DIR / "adb.exe")
    our_adb_normalized = os.path.normcase(os.path.normpath(our_adb))
    
    # 搜索常见位置
    search_paths = [
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Downloads"),
        os.path.expanduser("~\\AppData\\Local"),
        "C:\\Program Files",
        "C:\\Program Files (x86)",
    ]
    
    found_adbs = []
    seen_paths = set()  # 用于去重（规范化路径）
    
    # 添加我们的ADB
    if os.path.exists(our_adb):
        result = run_command(f'"{our_adb}" version')
        version = result.get('stdout', '').split('\n')[0] if result.get('success') else '未知版本'
        found_adbs.append({
            "path": our_adb,
            "version": version,
            "is_ours": True
        })
        seen_paths.add(our_adb_normalized)
    
    # 搜索其他ADB
    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue
        try:
            for root, dirs, files in os.walk(base_path):
                # 跳过一些不需要搜索的目录
                dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', '__pycache__', 'venv']]
                
                if 'adb.exe' in files:
                    adb_path = os.path.join(root, 'adb.exe')
                    # 规范化路径用于比较（Windows不区分大小写）
                    adb_path_normalized = os.path.normcase(os.path.normpath(adb_path))
                    
                    # 跳过已经添加的路径
                    if adb_path_normalized in seen_paths:
                        continue
                    
                    seen_paths.add(adb_path_normalized)
                    
                    # 获取版本信息
                    result = run_command(f'"{adb_path}" version', timeout=5)
                    version = result.get('stdout', '').split('\n')[0] if result.get('success') else '未知版本'
                    found_adbs.append({
                        "path": adb_path,
                        "version": version,
                        "is_ours": False
                    })
        except PermissionError:
            continue
        except Exception:
            continue
    
    return jsonify({
        "our_adb": our_adb,
        "found": found_adbs,
        "has_conflict": len([a for a in found_adbs if not a['is_ours']]) > 0
    })


@app.route('/api/adb/status', methods=['GET'])
def adb_status():
    """获取ADB详细状态，用于诊断"""
    adb = get_adb_path()
    
    status = {
        "adb_path": str(adb),
        "adb_exists": os.path.exists(adb),
        "server_running": False,
        "devices": [],
        "adb_keyboard": {
            "installed": False,
            "enabled": False
        }
    }
    
    # 检查 ADB 版本
    result = run_command(f'"{adb}" version')
    status["adb_version"] = result.get('stdout', '').split('\n')[0] if result.get('success') else "未知"
    
    # 检查设备
    result = run_command(f'"{adb}" devices')
    if result.get('success'):
        status["server_running"] = True
        lines = result['stdout'].strip().split('\n')
        for line in lines[1:]:
            if '\t' in line:
                parts = line.split('\t')
                status["devices"].append({
                    "id": parts[0],
                    "status": parts[1] if len(parts) > 1 else "unknown"
                })
    
    # 如果有设备，检查 ADB Keyboard
    if status["devices"]:
        # 检查是否安装
        result = run_command(f'"{adb}" shell pm path com.android.adbkeyboard')
        status["adb_keyboard"]["installed"] = 'package:' in result.get('stdout', '').lower()
        
        # 检查是否启用
        result = run_command(f'"{adb}" shell ime list -s')
        ime_list = result.get('stdout', '')
        status["adb_keyboard"]["enabled"] = 'com.android.adbkeyboard/.AdbIME' in ime_list
        status["adb_keyboard"]["ime_list"] = ime_list.strip().split('\n') if ime_list.strip() else []
    
    return jsonify(status)


@app.route('/api/check/device', methods=['GET'])
def check_device():
    """检测已连接的设备"""
    adb = get_adb_path()
    
    # 确保ADB服务器已启动（重启电脑后可能未启动）
    run_command(f'"{adb}" start-server')
    time.sleep(0.5)  # 等待服务器启动
    
    result = run_command(f'"{adb}" devices')
    
    # 检查是否有版本冲突
    stderr = result.get('stderr', '')
    if "doesn't match" in stderr or 'version' in stderr.lower():
        # ADB版本冲突，自动重启ADB服务器
        restart_adb_server()
        # 重试
        result = run_command(f'"{adb}" devices')
    
    if not result.get('success'):
        return jsonify({
            "connected": False,
            "devices": [],
            "message": "无法执行ADB命令",
            "error": result.get('error') or result.get('stderr'),
            "help": ["可能存在ADB版本冲突，请点击重新检测"]
        })
    
    lines = result['stdout'].strip().split('\n')
    devices = []
    
    for line in lines[1:]:  # 跳过第一行 "List of devices attached"
        if '\tdevice' in line:
            device_id = line.split('\t')[0]
            devices.append({
                "id": device_id,
                "status": "device"
            })
        elif '\tunauthorized' in line:
            device_id = line.split('\t')[0]
            devices.append({
                "id": device_id,
                "status": "unauthorized"
            })
    
    if not devices:
        return jsonify({
            "connected": False,
            "devices": [],
            "message": "未检测到设备",
            "help": [
                "1. 确保手机通过USB线连接到电脑",
                "2. 打开手机设置 → 关于手机 → 连续点击版本号7次 开启开发者模式",
                "3. 进入 设置 → 开发者选项 → 开启USB调试",
                "4. 手机上弹出授权提示时，请点击'允许'"
            ]
        })
    
    # 检查是否有未授权的设备
    unauthorized = [d for d in devices if d['status'] == 'unauthorized']
    if unauthorized:
        return jsonify({
            "connected": True,
            "authorized": False,
            "devices": devices,
            "message": "设备已连接但未授权",
            "help": ["请在手机上点击'允许USB调试'，并勾选'始终允许'"]
        })
    
    return jsonify({
        "connected": True,
        "authorized": True,
        "devices": devices,
        "message": f"已连接 {len(devices)} 个设备"
    })


@app.route('/api/check/adbkeyboard', methods=['GET'])
def check_adbkeyboard():
    """检测ADBKeyboard是否已安装"""
    adb = get_adb_path()
    
    # 检查APK文件是否存在
    apk_path = APK_DIR / "ADBKeyboard.apk"
    apk_exists = apk_path.exists()
    
    # 首先确保ADB服务器已启动
    run_command(f'"{adb}" start-server')
    
    # 第一步：用adb shell pm path检查ADBKeyboard是否安装（带重试）
    result_pkg = None
    for attempt in range(3):
        result_pkg = run_command(f'"{adb}" shell pm path com.android.adbkeyboard', timeout=10)
        
        # 检查是否有版本冲突
        stderr = result_pkg.get('stderr', '')
        if "doesn't match" in stderr or 'version' in stderr.lower():
            restart_adb_server()
            time.sleep(2)
            continue
        
        # 检查是否成功执行（有输出或明确的失败）
        stdout = result_pkg.get('stdout', '')
        if stdout or result_pkg.get('success'):
            break
        
        # 如果是连接问题，等待后重试
        if 'no devices' in stderr.lower() or 'error' in stderr.lower():
            time.sleep(1)
            continue
        
        break
    
    # 检查输出
    stdout = result_pkg.get('stdout', '') if result_pkg else ''
    stderr = (result_pkg.get('stderr', '') + result_pkg.get('error', '')) if result_pkg else ''
    
    # 判断设备是否连接
    if 'no devices' in stderr.lower() or 'device not found' in stderr.lower() or 'offline' in stderr.lower():
        return jsonify({
            "installed": False,
            "enabled": False,
            "device_connected": False,
            "apk_exists": apk_exists,
            "apk_path": str(apk_path),
            "message": "请先连接手机"
        })
    
    # 检查是否安装：如果输出包含"package:"则表示已安装
    pkg_installed = 'package:' in stdout.lower()
    
    # 如果未安装
    if not pkg_installed:
        return jsonify({
            "installed": False,
            "enabled": False,
            "device_connected": True,
            "apk_exists": apk_exists,
            "apk_path": str(apk_path),
            "message": "手机上未安装ADBKeyboard"
        })
    
    # 第二步：已安装，检查是否启用（必须检测完整的输入法ID，与Open-AutoGLM一致）
    result_ime = run_command(f'"{adb}" shell ime list -s')
    ime_list = result_ime.get('stdout', '')
    
    # 必须检测完整的输入法ID: com.android.adbkeyboard/.AdbIME
    if 'com.android.adbkeyboard/.AdbIME' in ime_list:
        return jsonify({
            "installed": True,
            "enabled": True,
            "device_connected": True,
            "apk_exists": apk_exists,
            "message": "ADBKeyboard已安装并启用"
        })
    else:
        return jsonify({
            "installed": True,
            "enabled": False,
            "device_connected": True,
            "apk_exists": apk_exists,
            "can_enable": True,  # 标记可以通过ADB启用
            "message": "ADBKeyboard已安装但未启用",
            "help": [
                "请点击下方按钮启用ADBKeyboard，",
                "或在手机上手动启用：",
                "设置 → 系统 → 语言和输入法 → 虚拟键盘 → 管理键盘 → 开启ADB Keyboard"
            ]
        })


@app.route('/api/enable/adbkeyboard', methods=['POST'])
def enable_adbkeyboard():
    """启用ADBKeyboard输入法"""
    adb = get_adb_path()
    
    # 步骤1：先启用ADBKeyboard输入法
    enable_result = run_command(f'"{adb}" shell ime enable com.android.adbkeyboard/.AdbIME')
    
    if not enable_result.get('success') and 'error' in enable_result.get('stderr', '').lower():
        return jsonify({
            "success": False,
            "error": "启用失败：" + enable_result.get('stderr', ''),
            "help": "请在手机上手动启用：设置 → 语言和输入法 → 虚拟键盘 → 管理键盘 → 开启ADB Keyboard"
        })
    
    # 步骤2：设置为当前输入法
    set_result = run_command(f'"{adb}" shell ime set com.android.adbkeyboard/.AdbIME')
    
    if set_result.get('success') or 'selected' in set_result.get('stdout', '').lower():
        return jsonify({
            "success": True,
            "message": "ADBKeyboard已成功启用并设置为当前输入法！"
        })
    else:
        # 可能启用成功但设置失败，检查是否在列表中
        check_result = run_command(f'"{adb}" shell ime list -s')
        if 'com.android.adbkeyboard' in check_result.get('stdout', ''):
            return jsonify({
                "success": True,
                "message": "ADBKeyboard已启用！"
            })
        else:
            return jsonify({
                "success": False,
                "error": "启用可能需要手机上确认",
                "help": "请在手机上手动启用：设置 → 语言和输入法 → 虚拟键盘 → 管理键盘 → 开启ADB Keyboard"
            })


@app.route('/api/install/adbkeyboard', methods=['POST'])
def install_adbkeyboard():
    """安装ADBKeyboard"""
    apk_path = APK_DIR / "ADBKeyboard.apk"
    
    if not apk_path.exists():
        return jsonify({
            "success": False,
            "error": f"APK文件不存在: {apk_path}"
        })
    
    adb = get_adb_path()
    
    # 先尝试安装
    result = run_command(f'"{adb}" install -r "{apk_path}"', timeout=120)
    
    # 如果遇到版本冲突或设备未找到，重启ADB后重试
    stderr = result.get('stderr', '') + result.get('stdout', '')
    if "doesn't match" in stderr or 'no devices' in stderr.lower():
        restart_adb_server()
        result = run_command(f'"{adb}" install -r "{apk_path}"', timeout=120)
    
    if result.get('success') or 'Success' in result.get('stdout', ''):
        return jsonify({
            "success": True,
            "message": "ADBKeyboard安装成功！请在手机上启用它",
            "next_steps": [
                "1. 打开手机 设置",
                "2. 进入 系统 → 语言和输入法 → 虚拟键盘",
                "3. 点击 管理键盘",
                "4. 开启 ADB Keyboard"
            ]
        })
    
    return jsonify({
        "success": False,
        "error": result.get('stderr') or result.get('error') or "安装失败",
        "output": result.get('stdout', '')
    })


# ==================== API Key管理 ====================

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置（包含所有服务商的配置）"""
    config = load_config()
    
    # 构建安全的配置（隐藏完整的 API Key）
    safe_config = {
        "current_provider": config.get('current_provider', 'bigmodel'),
        "providers": {}
    }
    
    for provider, provider_config in config.get('providers', {}).items():
        key = provider_config.get('api_key', '')
        if key and len(key) > 8:
            key_display = key[:4] + '*' * (len(key) - 8) + key[-4:]
        elif key:
            key_display = '****'
        else:
            key_display = ''
        
        safe_config['providers'][provider] = {
            "base_url": provider_config.get('base_url', ''),
            "model": provider_config.get('model', ''),
            "has_api_key": bool(key),
            "api_key_display": key_display
        }
    
    return jsonify(safe_config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    data = request.json
    config = load_config()
    
    provider = data.get('provider', config.get('current_provider', 'bigmodel'))
    
    # 更新当前服务商
    if 'provider' in data:
        config['current_provider'] = provider
    
    # 确保该服务商配置存在
    if provider not in config['providers']:
        config['providers'][provider] = get_default_config()['providers'].get(provider, {
            "base_url": "",
            "model": "",
            "api_key": ""
        })
    
    # 更新服务商的配置
    if 'api_key' in data:
        config['providers'][provider]['api_key'] = data['api_key']
    if 'base_url' in data:
        config['providers'][provider]['base_url'] = data['base_url']
    if 'model' in data:
        config['providers'][provider]['model'] = data['model']
    
    save_config(config)
    return jsonify({"success": True, "message": "配置已保存"})


@app.route('/api/config/delete-key', methods=['POST'])
def delete_api_key():
    """删除当前服务商的 API Key"""
    data = request.json or {}
    provider = data.get('provider')
    
    config = load_config()
    if not provider:
        provider = config.get('current_provider', 'bigmodel')
    
    if provider in config['providers']:
        config['providers'][provider]['api_key'] = ''
    
    save_config(config)
    return jsonify({"success": True, "message": "API Key已删除"})


@app.route('/api/verify-key', methods=['POST'])
def verify_api_key():
    """验证API Key是否可用"""
    data = request.json
    api_key = data.get('api_key', '')
    base_url = data.get('base_url', 'https://open.bigmodel.cn/api/paas/v4')
    model = data.get('model', 'autoglm-phone')
    provider = data.get('provider', 'bigmodel')
    skip_verify = data.get('skip_verify', False)
    
    # 自部署场景：允许不填 API Key，跳过验证直接保存
    if skip_verify or (provider == 'custom' and not api_key):
        # 直接保存配置，不验证
        config = load_config()
        config['current_provider'] = provider
        if provider not in config['providers']:
            config['providers'][provider] = {}
        config['providers'][provider]['base_url'] = base_url
        config['providers'][provider]['model'] = model
        config['providers'][provider]['api_key'] = api_key
        save_config(config)
        
        return jsonify({
            "valid": True,
            "message": "配置已保存（未验证API）",
            "skipped_verify": True
        })
    
    if not api_key:
        return jsonify({"valid": False, "error": "请输入API Key"})
    
    try:
        from openai import OpenAI
        # 对于自部署服务，使用一个占位符 key
        actual_key = api_key if api_key else "sk-placeholder"
        client = OpenAI(base_url=base_url, api_key=actual_key, timeout=30.0)
        
        # 简单测试API是否可用
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
            temperature=0.0,
        )
        
        if response.choices and len(response.choices) > 0:
            return jsonify({
                "valid": True,
                "message": "API验证成功！"
            })
        else:
            return jsonify({
                "valid": False,
                "error": "API返回异常响应"
            })
            
    except Exception as e:
        error_msg = str(e)
        if 'authentication' in error_msg.lower() or 'api key' in error_msg.lower():
            return jsonify({"valid": False, "error": "API Key无效或已过期"})
        elif 'connection' in error_msg.lower():
            return jsonify({"valid": False, "error": "网络连接失败，请检查网络"})
        else:
            return jsonify({"valid": False, "error": f"验证失败: {error_msg}"})


# ==================== Agent执行 ====================

@app.route('/api/task/run', methods=['POST'])
def run_task():
    """执行Agent任务"""
    global current_task
    
    if current_task["running"]:
        return jsonify({"success": False, "error": "已有任务正在执行"})
    
    data = request.json
    task_text = data.get('task', '')
    
    if not task_text:
        return jsonify({"success": False, "error": "请输入任务内容"})
    
    config = load_config()
    current_provider = config.get('current_provider', 'bigmodel')
    provider_config = config.get('providers', {}).get(current_provider, {})
    api_key = provider_config.get('api_key', '')
    
    # 自定义服务商允许不填 Key
    if not api_key and current_provider != 'custom':
        return jsonify({"success": False, "error": "请先配置API Key"})
    
    # 在后台线程执行任务
    def execute_task():
        global current_task
        current_task = {"running": True, "logs": [], "result": None}
        
        try:
            adb = get_adb_path()
            main_py = OPEN_AUTOGLM_DIR / "main.py"
            
            # 预检查：确保 ADB 连接稳定
            current_task["logs"].append("正在初始化 ADB 连接...")
            
            # 启动 ADB 服务器
            run_command(f'"{adb}" start-server')
            time.sleep(1)
            
            # 检查设备连接
            for attempt in range(3):
                result = run_command(f'"{adb}" devices')
                if result.get('success') and 'device' in result.get('stdout', ''):
                    # 检查是否有真正连接的设备（不只是header）
                    lines = result['stdout'].strip().split('\n')
                    connected = any('\tdevice' in line for line in lines[1:])
                    if connected:
                        current_task["logs"].append("✓ ADB 设备已连接")
                        break
                current_task["logs"].append(f"等待设备连接... (尝试 {attempt + 1}/3)")
                time.sleep(2)
            else:
                current_task["logs"].append("⚠ 未检测到设备，继续尝试执行...")
            
            # 检查 ADB Keyboard
            result_ime = run_command(f'"{adb}" shell ime list -s')
            if 'com.android.adbkeyboard/.AdbIME' in result_ime.get('stdout', ''):
                current_task["logs"].append("✓ ADB Keyboard 已启用")
            else:
                current_task["logs"].append("⚠ ADB Keyboard 可能未启用，尝试自动启用...")
                # 尝试自动启用
                run_command(f'"{adb}" shell ime enable com.android.adbkeyboard/.AdbIME')
                run_command(f'"{adb}" shell ime set com.android.adbkeyboard/.AdbIME')
                time.sleep(0.5)
            
            # 设置环境变量
            env = os.environ.copy()
            # 添加platform-tools到PATH最前面，确保使用我们的ADB
            env['PATH'] = str(PLATFORM_TOOLS_DIR) + os.pathsep + env.get('PATH', '')
            # 设置Python IO编码为UTF-8，解决emoji字符编码问题
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # 从当前服务商配置获取参数
            base_url = provider_config.get('base_url', 'https://open.bigmodel.cn/api/paas/v4')
            model = provider_config.get('model', 'autoglm-phone')
            
            cmd = [
                sys.executable,
                str(main_py),
                '--base-url', base_url,
                '--model', model,
            ]
            # 只有有 API Key 时才添加
            if api_key:
                cmd.extend(['--apikey', api_key])
            cmd.append(task_text)
            
            current_task["logs"].append(f"开始执行任务: {task_text}")
            
            process = subprocess.Popen(
                cmd,
                cwd=str(OPEN_AUTOGLM_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    current_task["logs"].append(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                current_task["result"] = {"success": True, "message": "任务执行完成"}
            else:
                current_task["result"] = {"success": False, "message": f"任务执行失败 (退出码: {process.returncode})"}
                
        except Exception as e:
            current_task["result"] = {"success": False, "message": f"执行出错: {str(e)}"}
        finally:
            current_task["running"] = False
    
    thread = threading.Thread(target=execute_task, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "任务已开始执行"})


@app.route('/api/task/status', methods=['GET'])
def get_task_status():
    """获取任务状态"""
    return jsonify({
        "running": current_task["running"],
        "logs": current_task["logs"],  # 返回所有日志
        "result": current_task["result"],
        "total_logs": len(current_task["logs"])
    })


@app.route('/api/task/stop', methods=['POST'])
def stop_task():
    """停止当前任务"""
    global current_task
    # 注意：这只是标记任务停止，实际需要更复杂的进程管理
    current_task["running"] = False
    current_task["result"] = {"success": False, "message": "任务已手动停止"}
    return jsonify({"success": True, "message": "已发送停止信号"})


@app.route('/api/task/clear', methods=['POST'])
def clear_task():
    """清空任务日志"""
    global current_task
    if not current_task["running"]:
        current_task = {"running": False, "logs": [], "result": None}
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "任务正在执行中"})


# ==================== WiFi ADB 连接 ====================

@app.route('/api/adb/wifi/connect', methods=['POST'])
def wifi_connect():
    """通过WiFi连接设备"""
    data = request.json
    ip = data.get('ip', '').strip()
    port = data.get('port', '5555').strip()
    
    if not ip:
        return jsonify({"success": False, "error": "请输入设备IP地址"})
    
    # 验证IP格式
    import re
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(ip_pattern, ip):
        return jsonify({"success": False, "error": "IP地址格式不正确"})
    
    # 验证端口
    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            raise ValueError()
    except:
        return jsonify({"success": False, "error": "端口号必须是1-65535之间的数字"})
    
    address = f"{ip}:{port}"
    adb = get_adb_path()
    
    # 尝试连接
    result = run_command(f'"{adb}" connect {address}', timeout=15)
    
    if result.get('success'):
        output = result.get('stdout', '') + result.get('stderr', '')
        if 'connected' in output.lower() or 'already connected' in output.lower():
            return jsonify({
                "success": True,
                "message": f"已连接到 {address}",
                "device_id": address
            })
        elif 'refused' in output.lower():
            return jsonify({
                "success": False,
                "error": "连接被拒绝",
                "help": [
                    "请确认手机已开启无线调试",
                    "确认IP和端口正确",
                    "确保手机和电脑在同一WiFi网络"
                ]
            })
        elif 'timeout' in output.lower() or 'timed out' in output.lower():
            return jsonify({
                "success": False,
                "error": "连接超时",
                "help": [
                    "请确认IP地址正确",
                    "确认手机和电脑在同一WiFi网络",
                    "检查防火墙设置"
                ]
            })
        else:
            return jsonify({
                "success": False,
                "error": output.strip() or "连接失败"
            })
    else:
        return jsonify({
            "success": False,
            "error": result.get('error') or result.get('stderr') or "连接失败"
        })


@app.route('/api/adb/wifi/disconnect', methods=['POST'])
def wifi_disconnect():
    """断开WiFi设备连接"""
    data = request.json
    device_id = data.get('device_id', '').strip()
    
    adb = get_adb_path()
    
    if device_id:
        result = run_command(f'"{adb}" disconnect {device_id}')
    else:
        # 断开所有WiFi连接
        result = run_command(f'"{adb}" disconnect')
    
    if result.get('success'):
        return jsonify({
            "success": True,
            "message": "已断开连接"
        })
    else:
        return jsonify({
            "success": False,
            "error": result.get('error') or "断开失败"
        })


@app.route('/api/adb/wifi/enable-tcpip', methods=['POST'])
def enable_tcpip():
    """在USB连接的设备上启用TCP/IP模式（用于后续WiFi连接）"""
    data = request.json
    device_id = data.get('device_id', '')
    port = data.get('port', 5555)
    
    adb = get_adb_path()
    
    # 构建命令
    if device_id:
        cmd = f'"{adb}" -s {device_id} tcpip {port}'
    else:
        cmd = f'"{adb}" tcpip {port}'
    
    result = run_command(cmd, timeout=10)
    
    if result.get('success'):
        output = result.get('stdout', '') + result.get('stderr', '')
        if 'restarting' in output.lower() or result.get('returncode', 1) == 0:
            # 获取设备IP
            time.sleep(1)
            ip_result = get_device_ip(device_id)
            
            return jsonify({
                "success": True,
                "message": f"TCP/IP模式已启用，端口: {port}",
                "port": port,
                "device_ip": ip_result
            })
        else:
            return jsonify({
                "success": False,
                "error": output.strip() or "启用失败"
            })
    else:
        return jsonify({
            "success": False,
            "error": result.get('error') or "启用TCP/IP失败"
        })


def get_device_ip(device_id=None):
    """获取设备的IP地址"""
    adb = get_adb_path()
    
    # 构建命令
    if device_id:
        cmd = f'"{adb}" -s {device_id} shell ip route'
    else:
        cmd = f'"{adb}" shell ip route'
    
    result = run_command(cmd, timeout=5)
    
    if result.get('success'):
        output = result.get('stdout', '')
        # 解析IP路由表获取设备IP
        # 格式类似: 192.168.1.0/24 dev wlan0 proto kernel scope link src 192.168.1.100
        import re
        match = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', output)
        if match:
            return match.group(1)
    
    # 备选方法：通过 wlan0 接口获取IP
    if device_id:
        cmd = f'"{adb}" -s {device_id} shell "ip addr show wlan0 | grep inet"'
    else:
        cmd = f'"{adb}" shell "ip addr show wlan0 | grep inet"'
    
    result = run_command(cmd, timeout=5)
    if result.get('success'):
        output = result.get('stdout', '')
        import re
        match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', output)
        if match:
            return match.group(1)
    
    return None


@app.route('/api/adb/wifi/get-device-ip', methods=['GET'])
def api_get_device_ip():
    """获取当前USB连接设备的IP地址"""
    device_id = request.args.get('device_id', '')
    
    ip = get_device_ip(device_id if device_id else None)
    
    if ip:
        return jsonify({
            "success": True,
            "ip": ip
        })
    else:
        return jsonify({
            "success": False,
            "error": "无法获取设备IP，请确保设备已连接WiFi"
        })


# ==================== 启动服务器 ====================

if __name__ == '__main__':
    print("=" * 50)
    print("AutoGLM Web服务")
    print("=" * 50)
    print(f"项目根目录: {BASE_DIR}")
    print(f"Open-AutoGLM: {OPEN_AUTOGLM_DIR}")
    print(f"Platform-Tools: {PLATFORM_TOOLS_DIR}")
    print("-" * 50)
    print("服务启动中...")
    print("请在浏览器中访问: http://127.0.0.1:5000")
    print("-" * 50)
    
    app.run(host='127.0.0.1', port=5000, debug=False)

