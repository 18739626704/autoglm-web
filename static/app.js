/**
 * AutoGLM Web控制台 - 前端脚本
 */

const API_BASE = '';

// 环境检测状态
const envStatus = {
    python: false,
    autoglm: false,
    platformTools: false,
    dependencies: false,
    device: false,
    adbKeyboard: false
};

// 配置状态
let configComplete = false;
let hasApiKey = false;

// 任务状态
let taskPollingInterval = null;

// ==================== 视图切换 ====================

function showConfigView() {
    document.getElementById('config-view').style.display = 'flex';
    document.getElementById('task-view').style.display = 'none';
    document.getElementById('btn-settings').style.display = 'none';
}

function showTaskView() {
    document.getElementById('config-view').style.display = 'none';
    document.getElementById('task-view').style.display = 'flex';
    document.getElementById('btn-settings').style.display = 'block';
}

function finishConfig() {
    // 保存配置完成状态到本地存储
    localStorage.setItem('autoglm_config_complete', 'true');
    showTaskView();
}

function checkInitialView() {
    // 检查是否已完成配置
    const saved = localStorage.getItem('autoglm_config_complete');
    if (saved === 'true' && configComplete && hasApiKey) {
        showTaskView();
    } else {
        showConfigView();
    }
}

function updateFinishButton() {
    const btn = document.getElementById('btn-finish-config');
    const hint = document.getElementById('config-hint');
    const envReady = Object.values(envStatus).every(v => v);
    
    // 自定义服务商允许不填 API Key
    const provider = document.getElementById('api-provider')?.value || 'bigmodel';
    const providerConfig = providersConfig[provider] || {};
    const apiReady = hasApiKey || providerConfig.has_api_key || (provider === 'custom');
    
    if (envReady && apiReady) {
        btn.disabled = false;
        hint.textContent = '配置已完成，点击按钮开始使用';
        hint.style.color = 'var(--accent-success)';
        configComplete = true;
    } else {
        btn.disabled = true;
        const issues = [];
        if (!envReady) issues.push('环境配置');
        if (!apiReady) issues.push('API配置');
        hint.textContent = `请先完成${issues.join('和')}`;
        hint.style.color = 'var(--text-muted)';
        configComplete = false;
    }
}

// ==================== 工具函数 ====================

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(API_BASE + endpoint, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        return await response.json();
    } catch (error) {
        console.error('API请求失败:', error);
        return { error: error.message };
    }
}

function updateCheckItem(id, status, message, detail = null, actions = null) {
    const item = document.getElementById(id);
    if (!item) return;

    // 移除旧状态
    item.classList.remove('success', 'error', 'warning');
    
    // 设置新状态
    const iconEl = item.querySelector('.check-icon');
    const statusEl = item.querySelector('.check-status');
    const detailEl = item.querySelector('.check-detail');

    switch (status) {
        case 'success':
            item.classList.add('success');
            iconEl.textContent = '✅';
            break;
        case 'error':
            item.classList.add('error');
            iconEl.textContent = '❌';
            break;
        case 'warning':
            item.classList.add('warning');
            iconEl.textContent = '⚠️';
            break;
        case 'loading':
            iconEl.textContent = '⏳';
            break;
        default:
            iconEl.textContent = '⏳';
    }

    statusEl.textContent = message;

    // 处理详情
    if (detail || actions) {
        detailEl.classList.remove('hidden');
        let html = '';
        
        if (detail) {
            if (Array.isArray(detail)) {
                html += '<ul>' + detail.map(d => `<li>${d}</li>`).join('') + '</ul>';
            } else {
                html += `<p>${detail}</p>`;
            }
        }
        
        if (actions) {
            html += actions;
        }
        
        detailEl.innerHTML = html;
    } else {
        detailEl.classList.add('hidden');
        detailEl.innerHTML = '';
    }
}

function updateEnvSummary() {
    const summary = document.getElementById('env-summary');
    const allPassed = Object.values(envStatus).every(v => v);
    
    summary.classList.remove('ready', 'error');
    
    if (allPassed) {
        summary.classList.add('ready');
        summary.innerHTML = `
            <div class="summary-content">
                <span class="summary-icon">🎉</span>
                <span class="summary-text">环境配置完成！</span>
            </div>
        `;
    } else {
        const failedCount = Object.values(envStatus).filter(v => !v).length;
        summary.classList.add('error');
        summary.innerHTML = `
            <div class="summary-content">
                <span class="summary-icon">⚠️</span>
                <span class="summary-text">还有 ${failedCount} 项需要配置</span>
            </div>
        `;
    }
    
    // 更新完成按钮状态
    updateFinishButton();
}

// ==================== 环境检测 ====================

async function checkPython() {
    updateCheckItem('check-python', 'loading', '检测中...');
    const result = await fetchAPI('/api/check/python');
    
    if (result.installed) {
        envStatus.python = true;
        updateCheckItem('check-python', 'success', result.version || 'Python已安装');
    } else {
        envStatus.python = false;
        updateCheckItem('check-python', 'error', '未安装', null,
            `<div class="check-detail-content">
                <p>${result.help}</p>
                <p style="margin-top:8px;">安装完成后请重启本服务</p>
            </div>`
        );
    }
}

async function checkOpenAutoGLM() {
    updateCheckItem('check-autoglm', 'loading', '检测中...');
    const result = await fetchAPI('/api/check/open-autoglm');
    
    if (result.installed) {
        envStatus.autoglm = true;
        updateCheckItem('check-autoglm', 'success', '已就绪');
    } else {
        envStatus.autoglm = false;
        updateCheckItem('check-autoglm', 'error', '未找到', 
            `请确保 Open-AutoGLM 文件夹在项目根目录`);
    }
}

async function checkPlatformTools() {
    updateCheckItem('check-platform-tools', 'loading', '检测中...');
    const result = await fetchAPI('/api/check/platform-tools');
    
    if (result.installed) {
        envStatus.platformTools = true;
        updateCheckItem('check-platform-tools', 'success', result.version || 'ADB已就绪');
    } else {
        envStatus.platformTools = false;
        updateCheckItem('check-platform-tools', 'error', '未找到',
            `请确保 platform-tools 文件夹在项目根目录`);
    }
}

async function checkDependencies() {
    updateCheckItem('check-dependencies', 'loading', '检测中...');
    const result = await fetchAPI('/api/check/dependencies');
    
    if (result.all_installed) {
        envStatus.dependencies = true;
        updateCheckItem('check-dependencies', 'success', '依赖完整');
    } else {
        envStatus.dependencies = false;
        updateCheckItem('check-dependencies', 'warning', 
            `缺少: ${result.missing.join(', ')}`,
            null,
            `<button class="btn btn-primary" onclick="installDependencies()">📦 安装依赖</button>`
        );
    }
}

async function installDependencies() {
    updateCheckItem('check-dependencies', 'loading', '正在安装...');
    const result = await fetchAPI('/api/install/dependencies', { method: 'POST' });
    
    if (result.success) {
        updateCheckItem('check-dependencies', 'success', '安装成功');
        envStatus.dependencies = true;
        updateEnvSummary();
    } else {
        updateCheckItem('check-dependencies', 'error', '安装失败',
            result.error || result.output);
    }
}

async function checkDevice() {
    updateCheckItem('check-device', 'loading', '检测中...');
    const result = await fetchAPI('/api/check/device');
    
    if (result.connected && result.authorized) {
        envStatus.device = true;
        const deviceInfo = result.devices.map(d => d.id).join(', ');
        updateCheckItem('check-device', 'success', deviceInfo);
    } else if (result.connected && !result.authorized) {
        envStatus.device = false;
        updateCheckItem('check-device', 'warning', '需要授权', result.help);
    } else {
        envStatus.device = false;
        updateCheckItem('check-device', 'error', '未连接', result.help);
    }
}

async function checkADBKeyboard() {
    updateCheckItem('check-adbkeyboard', 'loading', '检测中...');
    const result = await fetchAPI('/api/check/adbkeyboard');
    
    // 已安装并启用
    if (result.installed && result.enabled) {
        envStatus.adbKeyboard = true;
        updateCheckItem('check-adbkeyboard', 'success', '已安装并启用');
        return;
    }
    
    // 已安装但未启用
    if (result.installed && !result.enabled) {
        envStatus.adbKeyboard = false;
        const actions = result.can_enable 
            ? `<button class="btn btn-primary" onclick="enableADBKeyboard()">⚡ 一键启用</button>`
            : '';
        updateCheckItem('check-adbkeyboard', 'warning', '需要启用', result.help, actions);
        return;
    }
    
    // 未安装的情况
    envStatus.adbKeyboard = false;
    
    // 检查设备是否连接
    if (!result.device_connected) {
        updateCheckItem('check-adbkeyboard', 'warning', '等待手机连接', 
            ['请先连接手机，然后点击"重新检测"']);
        return;
    }
    
    // 设备已连接，检查APK是否存在
    if (result.apk_exists) {
        // APK存在，询问用户是否安装
        const detail = [
            '检测到您的手机未安装 ADBKeyboard',
            '本地已有安装包，是否现在安装到手机？'
        ];
        const actions = `
            <button class="btn btn-primary" onclick="installADBKeyboard()">
                📲 安装到手机
            </button>
        `;
        updateCheckItem('check-adbkeyboard', 'warning', '未安装', detail, actions);
    } else {
        // APK不存在
        const detail = [
            'APK文件不存在',
            `请下载 ADBKeyboard.apk 放入 apk 文件夹`,
            `路径: ${result.apk_path || 'apk/ADBKeyboard.apk'}`
        ];
        updateCheckItem('check-adbkeyboard', 'error', '未安装', detail);
    }
}

async function enableADBKeyboard() {
    updateCheckItem('check-adbkeyboard', 'loading', '正在启用...');
    const result = await fetchAPI('/api/enable/adbkeyboard', { method: 'POST' });
    
    if (result.success) {
        envStatus.adbKeyboard = true;
        updateCheckItem('check-adbkeyboard', 'success', '已启用');
        updateEnvSummary();
    } else {
        const detail = [
            result.error || '启用失败',
            result.help || '请在手机上手动启用'
        ];
        const actions = `
            <button class="btn btn-secondary" onclick="enableADBKeyboard()">🔄 重试</button>
        `;
        updateCheckItem('check-adbkeyboard', 'warning', '需手动启用', detail, actions);
    }
}

async function installADBKeyboard() {
    updateCheckItem('check-adbkeyboard', 'loading', '正在安装到手机...');
    const result = await fetchAPI('/api/install/adbkeyboard', { method: 'POST' });
    
    if (result.success) {
        // 安装成功，提示用户在手机上启用
        const detail = result.next_steps || [
            '安装成功！请在手机上启用：',
            '1. 打开手机 设置',
            '2. 进入 系统 → 语言和输入法 → 虚拟键盘',
            '3. 点击 管理键盘',
            '4. 开启 ADB Keyboard'
        ];
        const actions = `
            <button class="btn btn-secondary" onclick="checkADBKeyboard(); updateEnvSummary();">
                🔄 我已启用，重新检测
            </button>
        `;
        updateCheckItem('check-adbkeyboard', 'warning', '已安装，需启用', detail, actions);
    } else {
        // 安装失败
        const errorMsg = result.error || '未知错误';
        const detail = [
            `安装失败: ${errorMsg}`,
            '请确保手机已授权USB调试',
            '部分手机需要开启"USB安装"权限'
        ];
        const actions = `
            <button class="btn btn-secondary" onclick="installADBKeyboard()">
                🔄 重试安装
            </button>
        `;
        updateCheckItem('check-adbkeyboard', 'error', '安装失败', detail, actions);
    }
}

async function scanAdbFiles() {
    const warningDiv = document.getElementById('adb-warning');
    const headerDiv = document.getElementById('adb-warning-header');
    const descDiv = document.getElementById('adb-warning-desc');
    const listDiv = document.getElementById('adb-list');
    
    // 显示扫描中状态
    warningDiv.style.display = 'block';
    warningDiv.style.borderColor = 'var(--accent-info)';
    warningDiv.style.background = 'rgba(6, 182, 212, 0.1)';
    headerDiv.textContent = '🔍 正在扫描...';
    descDiv.textContent = '正在检测系统中的 ADB 文件，请稍候...';
    listDiv.innerHTML = '';
    
    const result = await fetchAPI('/api/adb/scan');
    
    if (result.found && result.found.length > 0) {
        let html = '';
        result.found.forEach(adb => {
            const isOurs = adb.is_ours;
            html += `
                <div class="adb-item ${isOurs ? 'ours' : 'conflict'}">
                    <span class="adb-path">${adb.path}<br><small style="color:var(--text-muted)">${adb.version}</small></span>
                    <span class="adb-tag ${isOurs ? 'ours' : 'conflict'}">${isOurs ? '✓ 当前使用' : '⚠ 可能冲突'}</span>
                </div>
            `;
        });
        listDiv.innerHTML = html;
        
        if (result.has_conflict) {
            // 发现冲突
            headerDiv.textContent = '⚠️ 检测到多个 ADB 版本';
            descDiv.textContent = '系统中存在其他 adb.exe，可能导致版本冲突。建议将冲突的版本重命名为 adb.exe.bak';
            warningDiv.style.borderColor = 'var(--accent-warning)';
            warningDiv.style.background = 'rgba(245, 158, 11, 0.1)';
        } else {
            // 无冲突
            headerDiv.textContent = '✅ 未发现 ADB 冲突';
            descDiv.textContent = '系统中只有本项目的 ADB，无版本冲突问题';
            warningDiv.style.borderColor = 'var(--accent-success)';
            warningDiv.style.background = 'rgba(16, 185, 129, 0.1)';
        }
    } else {
        headerDiv.textContent = '✅ 检测完成';
        descDiv.textContent = '未发现其他 ADB 文件';
        listDiv.innerHTML = '';
        warningDiv.style.borderColor = 'var(--accent-success)';
        warningDiv.style.background = 'rgba(16, 185, 129, 0.1)';
    }
}

async function runAllChecks() {
    // 按顺序检测
    await checkPython();
    updateEnvSummary();
    
    await checkOpenAutoGLM();
    updateEnvSummary();
    
    await checkPlatformTools();
    updateEnvSummary();
    
    await checkDependencies();
    updateEnvSummary();
    
    await checkDevice();
    updateEnvSummary();
    
    await checkADBKeyboard();
    updateEnvSummary();
}

// ==================== API配置 ====================

// 缓存所有服务商的配置
let providersConfig = {};
let currentProvider = 'bigmodel';

function onProviderChange() {
    const provider = document.getElementById('api-provider').value;
    const baseUrlInput = document.getElementById('base-url');
    const modelInput = document.getElementById('model-name');
    const apiKeyInput = document.getElementById('api-key');
    const helpDiv = document.getElementById('api-help');
    
    currentProvider = provider;
    
    // 加载该服务商的已保存配置
    const savedConfig = providersConfig[provider] || {};
    
    switch (provider) {
        case 'bigmodel':
            baseUrlInput.value = savedConfig.base_url || 'https://open.bigmodel.cn/api/paas/v4';
            modelInput.value = savedConfig.model || 'autoglm-phone';
            baseUrlInput.readOnly = true;
            modelInput.readOnly = true;
            helpDiv.innerHTML = `
                <h4>📝 如何获取 API Key？</h4>
                <ol>
                    <li>访问 <a href="https://open.bigmodel.cn/" target="_blank">https://open.bigmodel.cn/</a></li>
                    <li>注册/登录账号</li>
                    <li>进入控制台 → <strong>API Keys</strong> → <strong>创建密钥</strong></li>
                    <li>复制 API Key 粘贴到上方输入框</li>
                </ol>
                <p class="help-note">💡 新用户有免费额度，无需付费即可体验</p>
            `;
            break;
        case 'modelscope':
            baseUrlInput.value = savedConfig.base_url || 'https://api-inference.modelscope.cn/v1';
            modelInput.value = savedConfig.model || 'ZhipuAI/AutoGLM-Phone-9B';
            baseUrlInput.readOnly = true;
            modelInput.readOnly = true;
            helpDiv.innerHTML = `
                <h4>📝 如何获取 API Key？</h4>
                <ol>
                    <li>访问 <a href="https://modelscope.cn/" target="_blank">https://modelscope.cn/</a></li>
                    <li>注册/登录账号</li>
                    <li>进入个人中心获取 API Token</li>
                </ol>
            `;
            break;
        case 'custom':
            baseUrlInput.value = savedConfig.base_url || 'http://localhost:8000/v1';
            modelInput.value = savedConfig.model || 'autoglm-phone-9b';
            baseUrlInput.readOnly = false;
            modelInput.readOnly = false;
            helpDiv.innerHTML = `
                <h4>📝 自定义API配置</h4>
                <p>填写您的自部署服务地址，格式示例：</p>
                <ul>
                    <li><code>http://192.168.1.100:8000/v1</code> - 局域网服务器</li>
                    <li><code>http://localhost:8000/v1</code> - 本机服务</li>
                </ul>
                <p class="help-note">💡 自部署服务通常不需要填写 API Key，可留空</p>
            `;
            break;
    }
    
    // 更新 API Key 显示
    updateApiKeyDisplay(savedConfig);
    
    // 更新按钮状态
    updateFinishButton();
}

function updateApiKeyDisplay(config) {
    const apiKeyInput = document.getElementById('api-key');
    const deleteBtn = document.getElementById('btn-delete-key');
    
    apiKeyInput.value = '';
    
    if (config && config.has_api_key) {
        apiKeyInput.placeholder = config.api_key_display;
        deleteBtn.style.display = 'inline-flex';
        hasApiKey = true;
        showApiStatus('success', '✅ API Key 已配置');
    } else {
        apiKeyInput.placeholder = currentProvider === 'custom' ? 'API Key（可选，自部署可留空）' : '请输入API Key';
        deleteBtn.style.display = 'none';
        // 自定义服务商允许不填 Key
        hasApiKey = (currentProvider === 'custom');
        if (currentProvider === 'custom') {
            showApiStatus('info', '💡 自部署服务可不填 API Key');
        } else {
            showApiStatus('', '');
        }
    }
}

function toggleKeyVisibility() {
    const input = document.getElementById('api-key');
    input.type = input.type === 'password' ? 'text' : 'password';
}

async function loadConfig() {
    const config = await fetchAPI('/api/config');
    
    // 保存所有服务商配置
    providersConfig = config.providers || {};
    currentProvider = config.current_provider || 'bigmodel';
    
    // 设置下拉框
    document.getElementById('api-provider').value = currentProvider;
    
    // 触发切换以加载配置
    onProviderChange();
}

function showApiStatus(type, message) {
    const statusEl = document.getElementById('api-status');
    statusEl.className = 'api-status ' + type;
    statusEl.textContent = message;
    statusEl.style.display = message ? 'block' : 'none';
}

async function verifyAndSaveKey() {
    const apiKey = document.getElementById('api-key').value.trim();
    const baseUrl = document.getElementById('base-url').value;
    const model = document.getElementById('model-name').value;
    const provider = document.getElementById('api-provider').value;
    
    // 检查是否已有保存的 Key
    const savedConfig = providersConfig[provider] || {};
    const hasExistingKey = savedConfig.has_api_key;
    
    // 自定义服务商允许不填 Key
    const skipVerify = (provider === 'custom' && !apiKey);
    
    // 如果输入框为空
    if (!apiKey) {
        if (hasExistingKey) {
            // 已有 Key，提示用户
            showApiStatus('success', '✅ API Key 已配置，无需重复验证');
            return;
        } else if (provider !== 'custom') {
            // 没有 Key 且不是自定义，要求输入
            showApiStatus('error', '请输入 API Key');
            return;
        }
    }
    
    showApiStatus('loading', '⏳ 正在验证...');
    
    const result = await fetchAPI('/api/verify-key', {
        method: 'POST',
        body: JSON.stringify({ 
            api_key: apiKey, 
            base_url: baseUrl, 
            model: model,
            provider: provider,
            skip_verify: skipVerify
        })
    });
    
    if (result.valid) {
        // 保存配置
        await fetchAPI('/api/config', {
            method: 'POST',
            body: JSON.stringify({ 
                api_key: apiKey, 
                base_url: baseUrl, 
                model: model,
                provider: provider
            })
        });
        
        // 更新本地缓存
        providersConfig[provider] = {
            base_url: baseUrl,
            model: model,
            has_api_key: !!apiKey,
            api_key_display: apiKey ? (apiKey.slice(0, 4) + '****' + apiKey.slice(-4)) : ''
        };
        
        const msg = result.skipped_verify ? '配置已保存' : result.message;
        showApiStatus('success', '✅ ' + msg);
        document.getElementById('api-key').value = '';
        
        if (apiKey) {
            document.getElementById('api-key').placeholder = apiKey.slice(0, 4) + '****' + apiKey.slice(-4);
            document.getElementById('btn-delete-key').style.display = 'inline-flex';
        } else {
            document.getElementById('api-key').placeholder = 'API Key（可选）';
        }
        
        hasApiKey = true;
        updateFinishButton();
    } else {
        showApiStatus('error', '❌ ' + result.error);
    }
}

async function deleteKey() {
    const provider = document.getElementById('api-provider').value;
    if (!confirm(`确定要删除 ${getProviderName(provider)} 的 API Key 吗？`)) return;
    
    await fetchAPI('/api/config/delete-key', { 
        method: 'POST',
        body: JSON.stringify({ provider: provider })
    });
    
    // 更新本地缓存
    if (providersConfig[provider]) {
        providersConfig[provider].has_api_key = false;
        providersConfig[provider].api_key_display = '';
    }
    
    document.getElementById('api-key').placeholder = provider === 'custom' ? 'API Key（可选）' : '请输入API Key';
    document.getElementById('btn-delete-key').style.display = 'none';
    showApiStatus('', '');
    hasApiKey = (provider === 'custom');
    updateFinishButton();
}

function getProviderName(provider) {
    const names = {
        'bigmodel': '智谱 BigModel',
        'modelscope': 'ModelScope',
        'custom': '自定义服务'
    };
    return names[provider] || provider;
}

// ==================== 任务执行 ====================

function setTask(text) {
    document.getElementById('task-input').value = text;
}

async function runTask() {
    const taskInput = document.getElementById('task-input');
    const task = taskInput.value.trim();
    
    if (!task) {
        alert('请输入任务内容');
        return;
    }
    
    // 更新UI
    document.getElementById('btn-run-task').style.display = 'none';
    document.getElementById('btn-stop-task').style.display = 'inline-flex';
    
    // 清空日志
    const logContent = document.getElementById('log-content');
    logContent.innerHTML = '';
    
    // 启动任务
    const result = await fetchAPI('/api/task/run', {
        method: 'POST',
        body: JSON.stringify({ task: task })
    });
    
    if (result.success) {
        addLog('🚀 任务已启动: ' + task, 'info');
        // 开始轮询状态
        startPolling();
    } else {
        addLog('❌ 启动失败: ' + result.error, 'error');
        resetTaskUI();
    }
}

function startPolling() {
    taskPollingInterval = setInterval(async () => {
        const status = await fetchAPI('/api/task/status');
        
        // 更新日志
        const logContent = document.getElementById('log-content');
        logContent.innerHTML = '';
        
        status.logs.forEach(log => {
            let logClass = 'info';
            if (log.includes('💭') || log.includes('think')) logClass = 'thinking';
            else if (log.includes('🎯') || log.includes('action')) logClass = 'action';
            else if (log.includes('✅') || log.includes('完成')) logClass = 'success';
            else if (log.includes('❌') || log.includes('Error')) logClass = 'error';
            
            addLogLine(log, logClass);
        });
        
        // 滚动到底部
        logContent.scrollTop = logContent.scrollHeight;
        
        // 检查是否完成
        if (!status.running) {
            stopPolling();
            resetTaskUI();
            
            if (status.result) {
                if (status.result.success) {
                    addLog('🎉 ' + status.result.message, 'success');
                } else {
                    addLog('⚠️ ' + status.result.message, 'error');
                }
            }
        }
    }, 1000);
}

function stopPolling() {
    if (taskPollingInterval) {
        clearInterval(taskPollingInterval);
        taskPollingInterval = null;
    }
}

async function stopTask() {
    await fetchAPI('/api/task/stop', { method: 'POST' });
    stopPolling();
    resetTaskUI();
    addLog('⏹️ 任务已停止', 'error');
}

function resetTaskUI() {
    document.getElementById('btn-run-task').style.display = 'inline-flex';
    document.getElementById('btn-stop-task').style.display = 'none';
}

function addLog(text, type = 'info') {
    const logContent = document.getElementById('log-content');
    // 移除占位符
    const placeholder = logContent.querySelector('.log-placeholder');
    if (placeholder) placeholder.remove();
    
    addLogLine(text, type);
}

function addLogLine(text, type = 'info') {
    const logContent = document.getElementById('log-content');
    const line = document.createElement('div');
    line.className = 'log-line ' + type;
    line.textContent = text;
    logContent.appendChild(line);
    logContent.scrollTop = logContent.scrollHeight;
}

async function clearLog() {
    await fetchAPI('/api/task/clear', { method: 'POST' });
    const logContent = document.getElementById('log-content');
    logContent.innerHTML = '<p class="log-placeholder">执行任务后，日志将在这里显示...</p>';
}

// ==================== 弹窗 ====================

function showModal(title, body, footer) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = body;
    document.getElementById('modal-footer').innerHTML = footer;
    document.getElementById('install-modal').classList.add('show');
}

function closeModal() {
    document.getElementById('install-modal').classList.remove('show');
}

// ==================== 手机连接方式切换 ====================

function switchConnectionTab(type) {
    // 更新标签页状态
    const tabUsb = document.getElementById('tab-usb');
    const tabWifi = document.getElementById('tab-wifi');
    const panelUsb = document.getElementById('panel-usb');
    const panelWifi = document.getElementById('panel-wifi');
    
    if (type === 'usb') {
        tabUsb.classList.add('active');
        tabWifi.classList.remove('active');
        panelUsb.classList.remove('hidden');
        panelWifi.classList.add('hidden');
    } else {
        tabUsb.classList.remove('active');
        tabWifi.classList.add('active');
        panelUsb.classList.add('hidden');
        panelWifi.classList.remove('hidden');
    }
}

async function wifiConnect() {
    const ip = document.getElementById('wifi-ip').value.trim();
    const port = document.getElementById('wifi-port').value.trim() || '5555';
    const statusDiv = document.getElementById('wifi-status');
    
    if (!ip) {
        statusDiv.className = 'wifi-status error';
        statusDiv.textContent = '❌ 请输入设备IP地址';
        return;
    }
    
    statusDiv.className = 'wifi-status info';
    statusDiv.textContent = '⏳ 正在连接...';
    
    try {
        const response = await fetch('/api/adb/wifi/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ip, port })
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusDiv.className = 'wifi-status success';
            statusDiv.textContent = `✅ ${data.message}`;
            // 刷新设备检测
            await checkDevice();
            await checkADBKeyboard();
            updateEnvSummary();
        } else {
            statusDiv.className = 'wifi-status error';
            let msg = `❌ ${data.error}`;
            if (data.help) {
                msg += '\n' + data.help.join('\n');
            }
            statusDiv.innerHTML = msg.replace(/\n/g, '<br>');
        }
    } catch (error) {
        statusDiv.className = 'wifi-status error';
        statusDiv.textContent = `❌ 连接失败: ${error.message}`;
    }
}

async function wifiDisconnect() {
    const ip = document.getElementById('wifi-ip').value.trim();
    const port = document.getElementById('wifi-port').value.trim() || '5555';
    const statusDiv = document.getElementById('wifi-status');
    
    const deviceId = ip ? `${ip}:${port}` : '';
    
    try {
        const response = await fetch('/api/adb/wifi/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_id: deviceId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusDiv.className = 'wifi-status info';
            statusDiv.textContent = `✂️ ${data.message}`;
            // 刷新设备检测
            await checkDevice();
            updateEnvSummary();
        } else {
            statusDiv.className = 'wifi-status error';
            statusDiv.textContent = `❌ ${data.error}`;
        }
    } catch (error) {
        statusDiv.className = 'wifi-status error';
        statusDiv.textContent = `❌ 断开失败: ${error.message}`;
    }
}

async function getDeviceIP() {
    const statusDiv = document.getElementById('wifi-status');
    
    statusDiv.className = 'wifi-status info';
    statusDiv.textContent = '⏳ 正在获取设备IP（需先USB连接）...';
    
    try {
        const response = await fetch('/api/adb/wifi/get-device-ip');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('wifi-ip').value = data.ip;
            statusDiv.className = 'wifi-status success';
            statusDiv.textContent = `✅ 设备IP: ${data.ip}（已自动填入）`;
        } else {
            statusDiv.className = 'wifi-status error';
            statusDiv.textContent = `❌ ${data.error}`;
        }
    } catch (error) {
        statusDiv.className = 'wifi-status error';
        statusDiv.textContent = `❌ 获取失败: ${error.message}`;
    }
}

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', async () => {
    // 加载配置
    await loadConfig();
    
    // 运行所有检测
    await runAllChecks();
    
    // 检查是否应该直接进入任务视图
    checkInitialView();
});

