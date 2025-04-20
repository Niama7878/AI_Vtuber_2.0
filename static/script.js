document.addEventListener('DOMContentLoaded', () => {
    // --- 全局变量 ---
    const statusList = {
        processing: document.getElementById('processing'),
        stt: document.getElementById('stt'),
        mic: document.getElementById('mic'),
        playerStatus: document.getElementById('playerStatus'), 
        chatIds: document.getElementById('chatIds'),
    };
    const recordsContainer = document.getElementById('recordsContainer');
    const paginationControls = document.getElementById('paginationControls');
    const currentPageSpan = document.getElementById('currentPage');
    const totalPagesSpan = document.getElementById('totalPages');
    const prevPageButton = document.getElementById('prevPageButton');
    const nextPageButton = document.getElementById('nextPageButton');
    const pageInput = document.getElementById('pageInput');
    const jumpPageButton = document.getElementById('jumpPageButton');
    const themeToggleButton = document.getElementById('themeToggleButton');

    const chatInterface = document.getElementById('chatInterface');
    let currentChatMessages = { user: null, bot: null }; // 跟踪当前的聊天消息DOM元素
    let botMessageContent = ""; // 存储当前机器人回复的完整内容（用于delta累加）
    let isBotTyping = false; // 跟踪机器人是否正在输入
    let botTypingTimer = null; // 用于检测打字停止的计时器

    let allRecords = [];
    let currentPage = 1;
    const rowsPerPage = 10; // 每页显示的记录数
    let isFetchingRecords = false; // 防止重复获取
    let eventSource = null; // SSE 连接对象

    /**
    * 更新状态列表的 DOM 显示 - 修改版 (接受自定义文本)
    * @param {HTMLElement} element - 要更新的DOM元素
    * @param {any} value - 状态值
    * @param {boolean} [isBool=true] - 值是否为布尔类型
    * @param {string} [iconTrue='fa-toggle-on'] - True状态的FontAwesome图标类
    * @param {string} [iconFalse='fa-toggle-off'] - False状态的FontAwesome图标类
    * @param {string} [textTrue='开启'] - True状态显示的文本
    * @param {string} [textFalse='关闭'] - False状态显示的文本
    */
    function setStatus(element, value, isBool = true, iconTrue = 'fa-toggle-on', iconFalse = 'fa-toggle-off', textTrue = '开启', textFalse = '关闭') {
        if (element) {
            if (value === null || value === undefined) {
                element.innerHTML = '<span class="loader"></span>'; // 加载中
            } else if (isBool) {
                // 使用传入的或默认的图标和文本
                element.innerHTML = `<i class="fa-solid ${value ? iconTrue : iconFalse}" style="color: ${value ? 'var(--success-color)' : 'var(--error-color)'};"></i> ${value ? textTrue : textFalse}`;
            } else {
                element.textContent = value || 'N/A'; // 处理非布尔值，处理空字符串或 null
            }
        }
    }

    /**
    * 更新状态列表的 DOM 显示 (调用setStatus)
    * @param {object} status - 包含状态信息的对象
    */
    function updateStatusDOM(status) {
        if (!status) return; // 防御性编程

        setStatus(statusList.processing, status.processing);
        setStatus(statusList.stt, status.stt);
        setStatus(statusList.mic, status.mic, true, 'fa-microphone', 'fa-microphone-slash');

        // 处理 player 状态 
        setStatus(
            statusList.playerStatus,      // 要更新的元素
            status.player,                // 状态值 (true/false)
            true,                         // 布尔值
            'fa-play',                    // True 状态图标 (播放)
            'fa-pause',                   // False 状态图标 (暂停/停止)
            '播放中',                     // True 状态文本
            '已停止'                      // False 状态文本
        );
        setStatus(statusList.chatIds, status.chat_ids, false); // chat_ids 不是布尔值
    }

    /**
    * 获取初始状态并设置 SSE
    */
    async function fetchInitialStatus() {
        try {
            const response = await fetch('/status');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const initialStatus = await response.json();
            updateStatusDOM(initialStatus);

        } catch (error) {
            console.error("获取初始状态失败:", error);
            // 在页面上显示错误状态
            Object.values(statusList).forEach(el => {
                if (el) el.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color: var(--error-color);"></i> 获取失败';
            });
        }
    }

    /**
    * 设置 Server-Sent Events (SSE) 监听器
    */
    function setupSSE() {
        // 如果已有连接，先关闭
        if (eventSource) {
            eventSource.close();
            console.log("关闭旧的 SSE 连接.");
        }

        eventSource = new EventSource("/status-stream");

        eventSource.onopen = function() {
            console.log("SSE 连接已建立.");
            // 清理可能存在的错误状态
            Object.values(statusList).forEach(el => {
                if (el && el.innerHTML.includes('连接丢失')) {
                    el.innerHTML = '<span class="loader"></span>'; // 重置为加载中
                }
            });
            // 连接建立时获取一次当前状态，以防万一错过了初始加载
            fetchInitialStatus();
        };

        eventSource.onmessage = function(event) {
            try {
                const receivedData = JSON.parse(event.data);

                // 1. 更新状态显示部分
                updateStatusDOM(receivedData); // 现在会包含 player 状态

                // 2. 检查数据库更新
                if (receivedData.db_updated === true && !isFetchingRecords) {
                    console.log("检测到数据库更新，将重新获取记录...");
                    fetchRecords(); // 重新获取记录并更新表格
                } else if (receivedData.db_updated === true && isFetchingRecords) {
                    console.log("正在获取记录，跳过此次数据库更新触发。");
                }

                // 3. 处理聊天更新
                handleChatUpdate(receivedData);

            } catch (error) {
                console.error("解析或处理 SSE 数据失败:", error, "原始数据:", event.data);
            }
        };

        eventSource.onerror = function(err) {
            console.error("EventSource 错误:", err);
            Object.values(statusList).forEach(el => {
                // 如果元素存在，并且其内容包含加载器或不包含“连接丢失”文本，则更新它
                if (el && (el.innerHTML.includes('loader') || !el.innerHTML.includes('连接丢失'))) {
                    el.innerHTML = '<i class="fa-solid fa-plug-circle-xmark" style="color: var(--error-color);"></i> 连接丢失';
                }
            });
            // 连接丢失时也可能需要清理聊天界面
            clearChatInterface(true); // true 表示是错误导致，立即清除
            isBotTyping = false; // 停止打字状态
            if (botTypingTimer) clearTimeout(botTypingTimer); // 清除计时器
            eventSource.close(); // 关闭错误的连接
            setTimeout(setupSSE, 5000); // 5秒后尝试重连
        };

        // 页面卸载时关闭连接
        window.addEventListener('beforeunload', () => {
            if (eventSource) {
                eventSource.close();
                console.log("页面卸载，SSE 连接已关闭.");
            }
        });
    }

    /**
    * 处理来自 SSE 的聊天相关更新
    * @param {object} data - 从 SSE 收到的数据对象
    */
    function handleChatUpdate(data) {
        // a. 处理 question 更新 (用户消息)
        if (data.question_updated === true && data.question !== null) {
            // 重置机器人打字状态和内容
            stopBotTyping(); // 停止之前的打字 (如果有)
            botMessageContent = "";

            // 清理旧消息并创建新的用户消息
            addNewMessage('user', data.question);
            // 准备接收机器人消息 - 创建一个空的占位符，并开始打字动画
            addNewMessage('bot', '', true); // true 表示是占位符
        }
        // b. 处理 delta 更新 (机器人消息流)
        else if (data.delta_chunk !== null && data.delta_chunk !== undefined && currentChatMessages.bot) {
            // 如果机器人消息还没标记为打字状态，现在标记
            if (!isBotTyping) {
                startBotTyping();
            }
            // 累加 delta 内容
            botMessageContent += data.delta_chunk;
            // 更新机器人消息元素的文本
            const botTextElement = currentChatMessages.bot.querySelector('p');
            if (botTextElement) {
                botTextElement.textContent = botMessageContent; // 使用 textContent 防止 XSS
                // 滚动到底部，确保能看到最新文字
                scrollToBottom(chatInterface);
            }
            // 重置打字停止计时器
            resetBotTypingTimer();
        }
    }

    /**
    * 开始机器人打字状态
    */
    function startBotTyping() {
        if (!isBotTyping && currentChatMessages.bot) {
            isBotTyping = true;
            resetBotTypingTimer(); // 开始打字时也启动计时器
        }
    }

    /**
    * 停止机器人打字状态
    */
    function stopBotTyping() {
        if (botTypingTimer) clearTimeout(botTypingTimer); // 清除计时器
        isBotTyping = false;
    }

    /**
    * 重置打字超时计时器 (如果在一定时间内没有新的 delta，则停止打字动画)
    */
    function resetBotTypingTimer() {
        if (botTypingTimer) clearTimeout(botTypingTimer);
        // 设置 1.5 秒超时，如果1.5秒内没有新的 delta，认为打字结束
        botTypingTimer = setTimeout(() => {
            if (isBotTyping) {
                stopBotTyping();
            }
        }, 1500); // 1.5秒无更新则停止动画
    }

    /**
    * 向聊天界面添加新消息，并处理旧消息的退出动画
    * @param {'user' | 'bot'} type - 消息类型
    * @param {string} text - 消息文本
    * @param {boolean} [isPlaceholder=false] - 是否是机器人的初始占位符
    */
    function addNewMessage(type, text, isPlaceholder = false) {
        // --- 移除旧消息 ---
        // 如果是用户消息进来，清理上一轮的所有消息
        if (type === 'user') {
            clearChatInterface(); // 清理带动画
            currentChatMessages.user = null;
            currentChatMessages.bot = null;
        }
        // 如果是机器人消息进来 (包括占位符)，只清理旧的机器人消息 (如果存在)
        else if (type === 'bot' && currentChatMessages.bot) {
            // 如果新消息是占位符或者明确要替换，才移除旧的bot消息
            // （防止delta更新时意外移除自己）
            if (isPlaceholder || !currentChatMessages.bot.classList.contains('bot-message')) {
                triggerMessageExit(currentChatMessages.bot);
                currentChatMessages.bot = null;
            }
        }

        // --- 创建新消息元素 ---
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', `${type}-message`);

        const textParagraph = document.createElement('p');
        textParagraph.textContent = text; // 安全地设置文本
        messageDiv.appendChild(textParagraph);

        if (type === 'bot') {
            if (isPlaceholder) { // 只有占位符才立即开始打字
                startBotTyping(); // 启动打字状态
            } else if (text) { // 如果有初始文本，则不显示打字
                stopBotTyping();
            }
        }

        // --- 添加到界面 ---
        chatInterface.appendChild(messageDiv);
        scrollToBottom(chatInterface); // 滚动到底部

        // 更新当前消息引用
        currentChatMessages[type] = messageDiv;

        // 如果是用户消息添加后，重置机器人内容
        if (type === 'user') {
            botMessageContent = "";
        }
    }

    /**
    * 触发消息的退出动画并稍后移除
    * @param {HTMLElement} messageElement
    */
    function triggerMessageExit(messageElement) {
        if (!messageElement || !messageElement.parentNode) return; // 检查元素和父节点

        messageElement.classList.add('message-exit-active');

        const handleAnimationEnd = () => {
            // 再次检查父节点，防止在动画期间被其他逻辑移除
            if (messageElement.parentNode === chatInterface) {
                chatInterface.removeChild(messageElement);
            }
            // 移除事件监听器是个好习惯，虽然 {once: true} 也能做到
            messageElement.removeEventListener('animationend', handleAnimationEnd);
        };

        messageElement.addEventListener('animationend', handleAnimationEnd, { once: true });

        // 保险措施：如果动画事件由于某些原因未触发 (例如元素被隐藏), 设定超时移除
        setTimeout(() => {
            // 再次检查父节点
            if (messageElement.parentNode === chatInterface) {
                try {
                    chatInterface.removeChild(messageElement);
                } catch (e) {
                    // 忽略移除失败的错误 (可能已被移除)
                }
            }
        }, 550); // 动画时间是 500ms，稍微给点余量
    }

    /**
    * 清理聊天界面所有消息，带动画或立即
    * @param {boolean} immediate - 是否立即清除（例如出错时）
    */
    function clearChatInterface(immediate = false) {
        const messages = chatInterface.querySelectorAll('.chat-message');
        messages.forEach(msg => {
            if (immediate) {
                if (msg.parentNode === chatInterface) chatInterface.removeChild(msg);
            } else {
                triggerMessageExit(msg);
            }
        });
        // 清理引用和状态
        currentChatMessages.user = null;
        currentChatMessages.bot = null;
        botMessageContent = "";
        stopBotTyping(); // 确保停止打字
    }

    /**
    * 平滑滚动元素到底部
    * @param {HTMLElement} element
    */
    function scrollToBottom(element) {
        if(element) {
            element.scrollTo({
                top: element.scrollHeight,
                behavior: 'smooth' // 平滑滚动
            });
        }
    }

    // --- 数据库记录获取与分页 ---
    /**
    * 获取数据库记录
    */
    async function fetchRecords() {
        if (isFetchingRecords) {
            console.warn("已经在获取记录，请稍候...");
            return;
        }
        isFetchingRecords = true;
        const wasEmptyOrError = !recordsContainer.querySelector('table') || recordsContainer.querySelector('.error-message');

        // 只有在初次加载或之前是错误/空状态时显示加载中
        if (wasEmptyOrError) {
            recordsContainer.innerHTML = '加载中... <span class="loader"></span>';
            recordsContainer.classList.add('loading');
            if(paginationControls) paginationControls.style.display = 'none';
        }

        try {
            const res = await fetch('/records');
            if (!res.ok) {
                let errorMsg = `HTTP 错误! 状态: ${res.status}`;
                try {
                    const errData = await res.json();
                    if (errData && errData.error) errorMsg = errData.error;
                } catch (parseErr) { /* 忽略解析错误 */ }
                throw new Error(errorMsg);
            }
            const fetchedData = await res.json();

            // 确保数据是数组
            allRecords = Array.isArray(fetchedData) ? fetchedData : [];

            // 如果当前页码在获取新数据后变得无效，调整到最后一页
            const totalPages = Math.max(1, Math.ceil(allRecords.length / rowsPerPage));
            if (currentPage > totalPages) {
                currentPage = totalPages;
            }

            updatePagination(); // 更新分页控件并渲染当前页

        } catch (error) {
            console.error("获取记录失败:", error);
            recordsContainer.innerHTML = `<p class="error-message"><i class="fa-solid fa-exclamation-triangle"></i> 加载记录失败: ${error.message}</p>`;
            if(paginationControls) paginationControls.style.display = 'none';
        } finally {
            isFetchingRecords = false;
            // 使用 rAF 确保 loading 类在渲染更新后移除
            requestAnimationFrame(() => {
                recordsContainer.classList.remove('loading');
            });
        }
    }

    /**
    * 渲染表格的特定页面
    * @param {Array} records - 要渲染的记录数组 (当前页的记录)
    * @param {number} totalRecords - 总记录数
    */
    function renderTable(records, totalRecords) {
        const wasLoading = recordsContainer.classList.contains('loading');
        // 如果之前是加载状态，准备淡入
        if (!wasLoading) {
            recordsContainer.style.opacity = '0'; // 准备淡入
        }

        if (totalRecords === 0) {
            recordsContainer.innerHTML = '<p><i class="fa-solid fa-info-circle"></i> 暂无数据。</p>';
            if (paginationControls) paginationControls.style.display = 'none';
        } else if (!records || !records.length) {
            // 这种情况理论上不应发生，除非页码错误，但也处理一下
            recordsContainer.innerHTML = '<p><i class="fa-solid fa-info-circle"></i> 当前页无数据。</p>';
            if (paginationControls) paginationControls.style.display = 'flex'; // 分页还是要显示
        } else {
            let html = `
             <table>
              <thead>
               <tr>
                <th>ID</th><th>用户ID</th><th>类型</th><th>问题</th><th>回复</th><th>已回答</th>
               </tr>
              </thead>
              <tbody>
            `;

            for (let rec of records) {
                html += `
                <tr>
                 <td>${escapeHtml(rec.id)}</td>
                 <td>${escapeHtml(rec.user_id || '-')}</td>
                 <td>${escapeHtml(rec.event_type || '-')}</td>
                 <td title="${escapeHtml(rec.question || '')}">${escapeHtml(rec.question || '-')}</td>
                 <td title="${escapeHtml(rec.response || '')}">${escapeHtml(rec.response || '-')}</td>
                 <td>${rec.answered ? '<i class="fa-solid fa-check" style="color: var(--success-color);"></i> 是' : '<i class="fa-solid fa-times" style="color: var(--error-color);"></i> 否'}</td>
                </tr>
             `;
            }

            html += '</tbody></table>';
            recordsContainer.innerHTML = html;
            if (paginationControls) paginationControls.style.display = 'flex';
        }
        // 使用 rAF 确保内容插入后开始淡入动画
        requestAnimationFrame(() => {
            recordsContainer.style.opacity = '1';
            recordsContainer.style.transition = 'opacity 0.3s ease-in-out';
        });
        // 移除过渡效果，防止后续更新也淡入
        setTimeout(() => {
            recordsContainer.style.transition = '';
        }, 300);
    }

    /**
    * 转义 HTML 特殊字符
    * @param {string} unsafe - 可能包含 HTML 的字符串
    * @returns {string} 转义后的安全字符串
    */
    function escapeHtml(unsafe) {
        if (unsafe === null || unsafe === undefined) {
            return '';
        }
        const text = String(unsafe); // 确保是字符串
        return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    /**
    * 更新分页控件的状态和显示
    */
    function updatePagination() {
        const totalRecords = allRecords.length;
        const totalPages = Math.max(1, Math.ceil(totalRecords / rowsPerPage));

        if(paginationControls) {
            currentPageSpan.textContent = currentPage;
            totalPagesSpan.textContent = totalPages;
            pageInput.max = totalPages; // 设置输入框最大值
            pageInput.min = 1; // 设置最小值

            prevPageButton.disabled = currentPage <= 1;
            nextPageButton.disabled = currentPage >= totalPages;
        }

        // 计算当前页的记录
        const startIndex = (currentPage - 1) * rowsPerPage;
        const endIndex = startIndex + rowsPerPage;
        const paginatedRecords = allRecords.slice(startIndex, endIndex);

        // 渲染表格
        renderTable(paginatedRecords, totalRecords);
    }

    /**
    * 切换页面
    * @param {number} direction - 1 表示下一页, -1 表示上一页
    */
    function changePage(direction) {
        const totalPages = Math.ceil(allRecords.length / rowsPerPage);
        const newPage = currentPage + direction;

        if (newPage >= 1 && newPage <= totalPages) {
            currentPage = newPage;
            updatePagination();
            pageInput.value = ''; // 清空跳转输入框
            pageInput.classList.remove('input-error');
        }
    }

    /**
    * 跳转到指定页面
    */
    function jumpToPage() {
        const totalPages = Math.ceil(allRecords.length / rowsPerPage);
        const targetPage = parseInt(pageInput.value, 10);

        if (!isNaN(targetPage) && targetPage >= 1 && targetPage <= totalPages) {
            currentPage = targetPage;
            updatePagination();
            pageInput.value = ''; // 清空跳转输入框
            pageInput.classList.remove('input-error');
        } else {
            console.warn("无效的页码:", pageInput.value);
            pageInput.classList.add('input-error'); // 显示错误样式
        }
    }

    // --- 主题切换 ---
    /**
    * 切换亮色/暗色主题
    */
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        let targetTheme = 'light';

        if (currentTheme === 'light') {
            targetTheme = 'dark';
        } else if (currentTheme === 'dark') {
            targetTheme = 'light';
        } else { // 如果是 'auto' 或未设置，根据系统偏好决定
             targetTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark';
        }

        document.documentElement.setAttribute('data-theme', targetTheme);
        localStorage.setItem('theme', targetTheme); // 保存用户选择
    }

    /**
    * 应用保存的主题或系统偏好
    */
    function applyPreferredTheme() {
        const savedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
        } else {
            // 如果未保存，则根据系统偏好设置 'auto' 或实际值
            document.documentElement.setAttribute('data-theme', systemPrefersDark ? 'dark' : 'light');
        }
    }
    // 监听系统主题变化，仅在用户未手动选择主题时更新
    const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    function handleSystemThemeChange(e) {
        if (!localStorage.getItem('theme')) { // 只有在没有明确存储主题时才响应系统变化
            const newTheme = e.matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
        }
    }
    darkModeMediaQuery.addEventListener('change', handleSystemThemeChange);

    // --- 事件监听器绑定 ---
    if (themeToggleButton) themeToggleButton.addEventListener('click', toggleTheme);
    if (prevPageButton) prevPageButton.addEventListener('click', () => changePage(-1));
    if (nextPageButton) nextPageButton.addEventListener('click', () => changePage(1));
    if (jumpPageButton) jumpPageButton.addEventListener('click', jumpToPage);
    if (pageInput) {
        pageInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault(); // 阻止表单提交
                jumpToPage();
            }
        });
        // 输入时移除错误状态
        pageInput.addEventListener('input', () => pageInput.classList.remove('input-error'));
    }

    // --- 初始化 ---
    applyPreferredTheme(); // 页面加载时应用主题
    fetchInitialStatus();  // 获取初始状态
    fetchRecords();        // 获取初始数据库记录
    setupSSE();            // 设置 SSE 连接
});