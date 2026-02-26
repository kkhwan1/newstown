/**
 * Main Application JavaScript (Performance Optimized)
 * News Automation Dashboard
 *
 * Optimizations:
 * - Request caching with TTL
 * - Debounced search input
 * - Event listener cleanup on page switch
 * - DocumentFragment for DOM updates
 * - Lazy rendering for large lists
 */

// =============================================================================
// XSS Protection Utility
// =============================================================================

/**
 * Escapes HTML special characters to prevent XSS attacks
 * @param {string} str - The string to escape
 * @returns {string} The escaped string
 */
function escapeHTML(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// =============================================================================
// App State with Memory Management
// =============================================================================

const AppState = {
    user: null,
    currentPage: 'dashboard',
    processStatus: {
        upload: { running: false, runtime: null },
        deletion: { running: false, runtime: null },
        news: { running: false, runtime: null }
    },
    searchResults: [],
    selectedNews: new Set(),
    refreshInterval: null,

    // Event listener tracking for cleanup
    eventListeners: new Map(),
    intervals: new Map(),
    timeouts: new Map(),

    // Track event listener for cleanup
    trackListener(handlerName, element, event, handler, options = {}) {
        if (!this.eventListeners.has(handlerName)) {
            this.eventListeners.set(handlerName, []);
        }
        element.addEventListener(event, handler, options);
        this.eventListeners.get(handlerName).push({ element, event, handler, options });
    },

    // Track interval for cleanup
    trackInterval(handlerName, intervalId) {
        if (!this.intervals.has(handlerName)) {
            this.intervals.set(handlerName, []);
        }
        this.intervals.get(handlerName).push(intervalId);
    },

    // Track timeout for cleanup
    trackTimeout(handlerName, timeoutId) {
        if (!this.timeouts.has(handlerName)) {
            this.timeouts.set(handlerName, []);
        }
        this.timeouts.get(handlerName).push(timeoutId);
    },

    // Cleanup all resources for a handler
    cleanupHandler(handlerName) {
        const listeners = this.eventListeners.get(handlerName) || [];
        listeners.forEach(({ element, event, handler, options }) => {
            element.removeEventListener(event, handler, options);
        });
        this.eventListeners.delete(handlerName);

        const intervals = this.intervals.get(handlerName) || [];
        intervals.forEach(id => clearInterval(id));
        this.intervals.delete(handlerName);

        const timeouts = this.timeouts.get(handlerName) || [];
        timeouts.forEach(id => clearTimeout(id));
        this.timeouts.delete(handlerName);
    },

    // Cleanup all handlers (for logout)
    cleanupAll() {
        const allHandlers = [
            ...this.eventListeners.keys(),
            ...this.intervals.keys(),
            ...this.timeouts.keys()
        ];
        allHandlers.forEach(handler => this.cleanupHandler(handler));
        Utils.clearCache();
    }
};

// =============================================================================
// Utility Functions with Performance Optimizations
// =============================================================================

const Utils = {
    showPage(pageId) {
        const targetPage = document.getElementById(pageId);
        if (!targetPage) return;

        if (targetPage.classList.contains('content-page')) {
            // Internal page navigation (dashboard, search, news, etc.)
            document.querySelectorAll('.content-page').forEach(page => {
                page.classList.remove('active');
            });
            targetPage.classList.add('active');
        } else {
            // Top-level page switch (login <-> app)
            document.querySelectorAll('.page').forEach(page => {
                page.classList.add('hidden');
            });
            targetPage.classList.remove('hidden');
        }
        AppState.currentPage = pageId;
    },

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');

        // FIX #5: Limit max toasts to 5, remove oldest if exceeded
        const MAX_TOASTS = 5;
        const existingToasts = container.querySelectorAll('.toast');
        if (existingToasts.length >= MAX_TOASTS) {
            existingToasts[0].remove();
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    },

    formatDateTime(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleString('ko-KR');
    },

    formatDate(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleDateString('ko-KR');
    },

    formatRuntime(seconds) {
        if (!seconds) return '';
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h}시간 ${m}분 ${s}초`;
    },

    // Performance optimization utilities
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Request cache with TTL
    requestCache: new Map(),
    async cachedRequest(key, fetcher, ttl = 5000) {
        const cached = this.requestCache.get(key);
        const now = Date.now();

        if (cached && (now - cached.timestamp) < ttl) {
            return cached.data;
        }

        const data = await fetcher();
        this.requestCache.set(key, { data, timestamp: now });

        // Limit cache size to 100 entries
        if (this.requestCache.size > 100) {
            const firstKey = this.requestCache.keys().next().value;
            this.requestCache.delete(firstKey);
        }

        return data;
    },

    clearCache() {
        this.requestCache.clear();
    },

    // In-flight request deduplication
    pendingRequests: new Map(),
    async deduplicatedRequest(key, fetcher) {
        if (this.pendingRequests.has(key)) {
            return this.pendingRequests.get(key);
        }

        const promise = fetcher().finally(() => {
            this.pendingRequests.delete(key);
        });
        this.pendingRequests.set(key, promise);
        return promise;
    }
};

// =============================================================================
// Login Handler
// =============================================================================

const LoginHandler = {
    async init() {
        try {
            const form = document.getElementById('login-form');
            const token = localStorage.getItem('jwt_token');

            if (token) {
                try {
                    const user = await API.getCurrentUser();
                    if (user) {
                        AppState.user = user;
                        this.showApp();
                        return;
                    }
                } catch (error) {
                    localStorage.removeItem('jwt_token');
                }
            }

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const username = document.getElementById('login-username').value;
                const password = document.getElementById('login-password').value;
                const remember = document.getElementById('login-remember').checked;

                try {
                    const result = await API.login(username, password, remember);
                    const token = result.token || result.access_token;
                    if (token) {
                        localStorage.setItem('jwt_token', token);
                        AppState.user = result.user;
                        Utils.showToast('로그인되었습니다', 'success');
                        if (result.password_change_required) {
                            setTimeout(() => Utils.showToast('기본 비밀번호를 변경해주세요. 설정 > 비밀번호 변경에서 변경할 수 있습니다.', 'warning'), 500);
                        }
                        this.showApp();
                    }
                } catch (error) {
                    Utils.showToast(error.message || '로그인 실패', 'error');
                }
            });
        } catch (error) {
            console.error('LoginHandler init failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('로그인 초기화 중 오류가 발생했습니다', 'error');
            }
        }
    },

    showApp() {
        Utils.showPage('app');
        document.getElementById('user-username').textContent = AppState.user.username;

        const dashboardPage = document.getElementById('dashboard-page');
        if (dashboardPage) {
            dashboardPage.classList.add('active');
        }

        const dashboardNavBtn = document.querySelector('.nav-btn[data-page="dashboard"]');
        if (dashboardNavBtn) {
            dashboardNavBtn.classList.add('active');
        }

        DashboardHandler.init();
        NavigationHandler.init();
    }
};

// =============================================================================
// Navigation Handler with Cleanup
// =============================================================================

const NavigationHandler = {
    currentHandler: null,

    init() {
        const navBtns = document.querySelectorAll('.nav-btn');
        navBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const page = btn.dataset.page;
                this.showPage(page);
            });
        });

        document.getElementById('logout-btn').addEventListener('click', async () => {
            try {
                await API.logout();
            } catch (error) {
                console.error('Logout error:', error);
            } finally {
                AppState.cleanupAll();
                localStorage.removeItem('jwt_token');
                window.location.reload();
            }
        });

        document.getElementById('stop-all-btn').addEventListener('click', async () => {
            if (confirm('모든 프로세스를 중지하시겠습니까?')) {
                try {
                    await API.stopAllProcesses();
                    Utils.showToast('모든 프로세스가 중지되었습니다', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        });
    },

    async showPage(pageName) {
        try {
            // Cleanup current handler before switching
            if (this.currentHandler) {
                const handlerMap = {
                    'dashboard': DashboardHandler,
                    'search': SearchHandler,
                    'news': NewsHandler,
                    'logs': LogsHandler,
                    'settings': SettingsHandler
                };

                const currentHandlerObj = handlerMap[this.currentHandler];
                if (currentHandlerObj && typeof currentHandlerObj.cleanup === 'function') {
                    currentHandlerObj.cleanup();
                }
            }

            // Update navigation UI
            document.querySelectorAll('.nav-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.dataset.page === pageName) {
                    btn.classList.add('active');
                }
            });

            Utils.showPage(`${pageName}-page`);

            // Initialize new handler
            switch (pageName) {
                case 'dashboard':
                    await DashboardHandler.init();
                    break;
                case 'search':
                    await SearchHandler.init();
                    break;
                case 'news':
                    await NewsHandler.init();
                    break;
                case 'logs':
                    await LogsHandler.init();
                    break;
                case 'settings':
                    await SettingsHandler.init();
                    break;
            }

            this.currentHandler = pageName;
        } catch (error) {
            console.error('NavigationHandler showPage failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('페이지 전환 중 오류가 발생했습니다', 'error');
            }
        }
    }
};

// =============================================================================
// Dashboard Handler with Cleanup
// =============================================================================

const DashboardHandler = {
    handlerName: 'DashboardHandler',
    initialized: false,
    wsConnected: false,

    cleanup() {
        AppState.cleanupHandler(this.handlerName);
        if (this.wsConnected) {
            wsManager.disconnect();
            this.wsConnected = false;
        }
        if (AppState.refreshInterval) {
            clearInterval(AppState.refreshInterval);
            AppState.refreshInterval = null;
        }
        this.initialized = false;
    },

    async init() {
        try {
            if (this.initialized) return;
            // FIX #4: Do NOT set initialized=true until after async operations complete

            await this.load();
            this.bindEvents();
            this.startAutoRefresh();

            wsManager.connect();
            this.wsConnected = true;
            wsManager.on('message', (data) => {
                if (data.type === 'log') {
                    this.updateLogContent(data.process, data.log);
                } else if (data.type === 'status') {
                    this.updateProcessStatus(data.process, data.status);
                }
            });

            // FIX #4: Set initialized flag AFTER all async operations complete
            this.initialized = true;
        } catch (error) {
            console.error('DashboardHandler init failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('대시보드 초기화 중 오류가 발생했습니다', 'error');
            }
        }
    },

    async load() {
        try {
            const config = await Utils.cachedRequest(
                'dashboard_config',
                async () => API.getConfig(),
                10000
            );
            this.renderConfig(config);
            await this.updateStatus();
        } catch (error) {
            console.error('Dashboard load error:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('대시보드 로드 중 오류가 발생했습니다', 'error');
            }
        }
    },

    bindEvents() {
        // Upload toggle
        AppState.trackListener(
            this.handlerName,
            document.getElementById('upload-toggle-btn'),
            'click',
            () => this.toggleProcess('upload')
        );

        // Deletion toggle
        AppState.trackListener(
            this.handlerName,
            document.getElementById('deletion-toggle-btn'),
            'click',
            () => this.toggleProcess('deletion')
        );

        // News toggle
        AppState.trackListener(
            this.handlerName,
            document.getElementById('news-toggle-btn'),
            'click',
            () => this.toggleProcess('news')
        );

        // Platform selection
        document.querySelectorAll('.platform-checkbox input').forEach(checkbox => {
            AppState.trackListener(
                this.handlerName,
                checkbox,
                'change',
                () => this.updateSelectedPlatforms()
            );
        });

        // Sort option
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-sort-btn'),
            'click',
            async () => {
                const sort = document.querySelector('input[name="sort-option"]:checked').value;
                try {
                    await API.setConfig('news_collection', 'sort', sort);
                    Utils.clearCache();
                    Utils.showToast('정렬 방식이 저장되었습니다', 'success');
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Schedule settings
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-schedule'),
            'click',
            async () => {
                const enabled = document.getElementById('schedule-enabled').checked;
                const interval = parseInt(document.getElementById('schedule-interval').value);
                try {
                    await API.setConfig('news_schedule', 'enabled', enabled);
                    await API.setConfig('news_schedule', 'interval_hours', interval);
                    Utils.clearCache();
                    Utils.showToast('스케줄 설정이 저장되었습니다', 'success');
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Save keywords (키워드 저장)
        const saveKeywordsBtn = document.getElementById('save-keywords-btn');
        if (saveKeywordsBtn) {
            AppState.trackListener(
                this.handlerName,
                saveKeywordsBtn,
                'click',
                async () => {
                    const keywordInputs = document.querySelectorAll('.keyword-input');
                    const categoryKeywords = {};

                    keywordInputs.forEach(input => {
                        const category = input.dataset.category;
                        const type = input.dataset.type;
                        const values = input.value.split(',').map(v => v.trim()).filter(v => v);

                        if (!categoryKeywords[category]) {
                            categoryKeywords[category] = { core: [], general: [] };
                        }
                        categoryKeywords[category][type] = values;
                    });

                    try {
                        await API.updateConfig('category_keywords', categoryKeywords);
                        Utils.showToast('키워드 설정이 저장되었습니다', 'success');
                    } catch (error) {
                        console.error('키워드 저장 실패:', error);
                        Utils.showToast(error.message || '키워드 저장에 실패했습니다', 'error');
                    }
                }
            );
        }

        // Publication count - total mode (all categories same)
        const applyTotalPubBtn = document.getElementById('apply-total-pub');
        if (applyTotalPubBtn) {
            AppState.trackListener(
                this.handlerName,
                applyTotalPubBtn,
                'click',
                async () => {
                    try {
                        const count = parseInt(document.getElementById('total-pub')?.value) || 15;
                        const keywords = { '연애': count, '경제': count, '스포츠': count };
                        const currentConfig = await API.getConfig('news_collection');
                        await API.updateConfig('news_collection', { ...currentConfig, keywords });
                        Utils.clearCache();
                        Utils.showToast('발행 개수가 저장되었습니다', 'success');
                    } catch (error) {
                        Utils.showToast(error.message || '저장 실패', 'error');
                    }
                }
            );
        }

        // Publication count - per-category mode
        const applyCatPubBtn = document.getElementById('apply-cat-pub');
        if (applyCatPubBtn) {
            AppState.trackListener(
                this.handlerName,
                applyCatPubBtn,
                'click',
                async () => {
                    try {
                        const keywords = {
                            '연애': parseInt(document.getElementById('pub-연애')?.value) || 15,
                            '경제': parseInt(document.getElementById('pub-경제')?.value) || 15,
                            '스포츠': parseInt(document.getElementById('pub-스포츠')?.value) || 15,
                        };
                        const currentConfig = await API.getConfig('news_collection');
                        await API.updateConfig('news_collection', { ...currentConfig, keywords });
                        Utils.clearCache();
                        Utils.showToast('카테고리별 발행 개수가 저장되었습니다', 'success');
                    } catch (error) {
                        Utils.showToast(error.message || '저장 실패', 'error');
                    }
                }
            );
        }

        // Publication mode radio toggle (all vs category)
        document.querySelectorAll('input[name="pub-mode"]').forEach(radio => {
            AppState.trackListener(
                this.handlerName,
                radio,
                'change',
                () => {
                    const allMode = document.getElementById('pub-all-mode');
                    const catMode = document.getElementById('pub-category-mode');
                    if (allMode) allMode.classList.toggle('hidden', radio.value !== 'all');
                    if (catMode) catMode.classList.toggle('hidden', radio.value !== 'category');
                }
            );
        });

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => {
                    const tab = btn.dataset.tab;
                    const parent = btn.closest('.tabs');
                    parent.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    const container = parent.parentElement;
                    container.querySelectorAll('.tab-content').forEach(content => {
                        content.classList.remove('active');
                    });
                    document.getElementById(tab).classList.add('active');
                }
            );
        });
    },

    async updateStatus() {
        try {
            const [uploadStatus, deletionStatus, newsStatus] = await Promise.all([
                API.getProcessStatus('upload_monitor'),
                API.getProcessStatus('row_deletion'),
                API.getProcessStatus('news_collection')
            ]);

            this.updateStatusUI('upload', uploadStatus);
            this.updateStatusUI('deletion', deletionStatus);
            this.updateStatusUI('news', newsStatus);

        } catch (error) {
            console.error('Status update error:', error);
        }
    },

    updateStatusUI(process, status) {
        const statusEl = document.getElementById(`${process}-status`);
        const btn = document.getElementById(`${process}-toggle-btn`);

        if (status.running) {
            statusEl.textContent = `● 실행중 ${status.runtime ? `(${status.runtime})` : ''}`;
            statusEl.classList.add('running');
            statusEl.classList.remove('stopped');
            btn.textContent = '중지';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-secondary');
        } else {
            statusEl.textContent = '○ 중지됨';
            statusEl.classList.add('stopped');
            statusEl.classList.remove('running');
            btn.textContent = `${process === 'upload' ? '업로드' : process === 'deletion' ? '완료행 삭제' : '뉴스 수집'} 시작`;
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-secondary');
        }

        AppState.processStatus[process] = status;
    },

    async toggleProcess(process) {
        const status = AppState.processStatus[process];
        try {
            if (status.running) {
                await API.stopProcess(`${process}_monitor`);
                Utils.showToast(`${process}가 중지되었습니다`, 'success');
            } else {
                if (process === 'upload') {
                    const selected = this.getSelectedPlatforms();
                    if (selected.length === 0) {
                        Utils.showToast('업로드할 플랫폼을 선택해주세요', 'warning');
                        return;
                    }
                    // Get full config and extract sections (single API call, consistent data)
                    const fullConfig = await API.getConfig();
                    const config = { ...(fullConfig.upload_monitor || {}) };
                    const platforms = fullConfig.upload_platforms || {};
                    config.selected_platforms = selected;
                    config.upload_platforms = platforms;
                    config.sheet_url = fullConfig.google_sheet?.url || '';
                    config.golftimes = fullConfig.golftimes || {};
                    console.log('[DEBUG] Upload config:', { selected, platformsKeys: Object.keys(platforms), sheet_url: !!config.sheet_url });
                    await API.startProcess('upload_monitor', config);
                } else if (process === 'deletion') {
                    const config = await API.getConfig('row_deletion');
                    await API.startProcess('row_deletion', config);
                } else if (process === 'news') {
                    const config = await API.getConfig('news_collection');
                    const categoryKeywords = await API.getConfig('category_keywords');
                    if (categoryKeywords) {
                        config.category_keywords = categoryKeywords;
                    }
                    await API.startProcess('news_collection', config);
                }
                Utils.showToast(`${process}가 시작되었습니다`, 'success');
            }
            setTimeout(() => this.updateStatus(), 1000);
        } catch (error) {
            Utils.showToast(error.message, 'error');
        }
    },

    async loadProcessLogs(processName) {
        try {
            const result = await API.getProcessLogs(processName, 50);
            const logs = result?.logs || result || '';
            const logId = processName === 'upload_monitor' ? 'upload-log-content' :
                         processName === 'row_deletion' ? 'deletion-log-content' :
                         'news-log-content';
            const el = document.getElementById(logId);
            if (el) {
                el.textContent = logs || '로그가 없습니다';
                el.scrollTop = el.scrollHeight;
            }
        } catch (error) {
            console.error('Load logs error:', error);
        }
    },

    async renderConfig(config) {
        // Render platforms - load from /api/platforms if not in config
        const platformsContainer = document.getElementById('platform-checkboxes');
        if (platformsContainer) {
            let platforms = config.upload_platforms;

            // If upload_platforms not in config, fetch from /api/platforms
            if (!platforms || Object.keys(platforms).length === 0) {
                try {
                    const platformsResp = await fetch('/api/platforms');
                    if (platformsResp.ok) {
                        const data = await platformsResp.json();
                        platforms = data.platforms || {};
                    }
                } catch (error) {
                    console.error('Failed to load platforms:', error);
                }
            }

            if (platforms && Object.keys(platforms).length > 0) {
                platformsContainer.innerHTML = '';
                Object.entries(platforms).forEach(([id, platform]) => {
                    const label = document.createElement('label');
                    label.className = 'platform-checkbox';
                    label.innerHTML = `
                        <input type="checkbox" value="${escapeHTML(id)}" ${platform.enabled ? 'checked' : ''}>
                        <span>${escapeHTML(platform.display_name || id)}</span>
                    `;
                    platformsContainer.appendChild(label);
                });
            }
        }

        // Update dashboard link buttons from config
        const sheetLink = document.getElementById('sheet-link');
        if (sheetLink && config.google_sheet && config.google_sheet.url) {
            sheetLink.href = config.google_sheet.url;
            sheetLink.title = '구글 스프레드시트 열기';
        }
        const makeLink = document.getElementById('make-link');
        if (makeLink) {
            if (config.make_scenario && config.make_scenario.url) {
                makeLink.href = config.make_scenario.url;
                makeLink.title = 'Make 시나리오 열기';
                makeLink.classList.remove('disabled');
            } else {
                makeLink.href = 'javascript:void(0)';
                makeLink.title = 'Make URL이 설정되지 않았습니다';
                makeLink.classList.add('disabled');
                makeLink.onclick = (e) => { e.preventDefault(); Utils.showToast('Make URL이 설정되지 않았습니다', 'warning'); };
            }
        }

        // Update publication inputs
        if (config.news_collection && config.news_collection.keywords) {
            const keywords = config.news_collection.keywords;
            document.getElementById('total-pub').value = keywords.연애 || 15;
            document.getElementById('pub-연애').value = keywords.연애 || 15;
            document.getElementById('pub-경제').value = keywords.경제 || 15;
            document.getElementById('pub-스포츠').value = keywords.스포츠 || 15;

            const total = (keywords.연애 || 15) + (keywords.경제 || 15) + (keywords.스포츠 || 15);
            const summary = document.getElementById('pub-summary');
            if (summary) {
                summary.textContent = `총 ${total}개 뉴스 수집 예정 (연애 ${keywords.연애 || 15} + 경제 ${keywords.경제 || 15} + 스포츠 ${keywords.스포츠 || 15})`;
            }
        }

        // Update schedule settings
        if (config.news_schedule) {
            document.getElementById('schedule-enabled').checked = config.news_schedule.enabled || false;
            document.getElementById('schedule-interval').value = config.news_schedule.interval_hours || 3;

            const scheduleInfo = document.getElementById('schedule-info');
            const scheduleStatus = document.getElementById('schedule-status');

            if (config.news_schedule.enabled) {
                if (config.news_schedule.last_run) {
                    const lastDate = new Date(config.news_schedule.last_run);
                    const nextDate = new Date(lastDate.getTime() + (config.news_schedule.interval_hours || 3) * 3600000);
                    const now = new Date();
                    if (nextDate > now) {
                        const diff = nextDate - now;
                        const hours = Math.floor(diff / 3600000);
                        const minutes = Math.floor((diff % 3600000) / 60000);
                        scheduleInfo.textContent = `마지막 수집: ${Utils.formatDateTime(lastDate)}\n다음 수집 예정: ${Utils.formatDateTime(nextDate)}`;
                        scheduleStatus.textContent = `자동 스케줄러 ON: ${config.news_schedule.interval_hours}시간 간격 | 다음 수집까지 ${hours}시간 ${minutes}분`;
                    } else {
                        scheduleInfo.textContent = `마지막 수집: ${Utils.formatDateTime(lastDate)}\n다음 수집 예정: 곧 수집 시작`;
                        scheduleStatus.textContent = `자동 스케줄러 ON: ${config.news_schedule.interval_hours}시간 간격 | 곧 수집 시작`;
                    }
                } else {
                    scheduleInfo.textContent = '마지막 수집: 아직 실행되지 않음';
                    scheduleStatus.textContent = `자동 스케줄러 ON: ${config.news_schedule.interval_hours}시간 간격 | 첫 수집 대기중`;
                }
            } else {
                scheduleStatus.textContent = '';
            }
        }

        // Update sort option
        if (config.news_collection && config.news_collection.sort) {
            const sortRadio = document.querySelector(`input[name="sort-option"][value="${config.news_collection.sort}"]`);
            if (sortRadio) sortRadio.checked = true;
        }

        // Render keyword settings on dashboard
        SettingsHandler.renderKeywords(config.category_keywords || {});
    },

    getSelectedPlatforms() {
        const selected = [];
        document.querySelectorAll('.platform-checkbox input:checked').forEach(checkbox => {
            selected.push(checkbox.value);
        });
        return selected;
    },

    async updateSelectedPlatforms() {
        try {
            const checkboxes = document.querySelectorAll('.platform-checkbox input[type="checkbox"]');
            if (!checkboxes.length) return;

            const config = await Utils.cachedRequest('config', () => API.getConfig(), 10000);
            const platforms = config?.upload_platforms || {};

            checkboxes.forEach(checkbox => {
                const platformId = checkbox.value || checkbox.dataset.platform;
                if (platformId && platforms[platformId]) {
                    platforms[platformId].enabled = checkbox.checked;
                }
            });

            await API.updateConfig('upload_platforms', platforms);
            Utils.showToast('플랫폼 설정이 저장되었습니다', 'success');
        } catch (error) {
            Utils.showToast(error.message || '플랫폼 저장 실패', 'error');
        }
    },

    startAutoRefresh() {
        if (AppState.refreshInterval) {
            clearInterval(AppState.refreshInterval);
        }
        AppState.refreshInterval = setInterval(async () => {
            if (AppState.processStatus.news.running) {
                await this.updateStatus();
            }
        }, 5000);
    },

    updateLogContent(process, log) {
        const logId = process === 'upload_monitor' ? 'upload-log-content' :
                     process === 'row_deletion' ? 'deletion-log-content' :
                     'news-log-content';
        const el = document.getElementById(logId);
        if (el) {
            el.textContent = log;
            el.scrollTop = el.scrollHeight;
        }
    },

    updateProcessStatus(process, status) {
        this.updateStatusUI(process.replace('_monitor', ''), status);
    }
};

// =============================================================================
// Search Handler with Debounce
// =============================================================================

const SearchHandler = {
    handlerName: 'SearchHandler',
    debouncedSearch: null,
    initialized: false,

    cleanup() {
        AppState.cleanupHandler(this.handlerName);
        this.debouncedSearch = null;
        this.initialized = false;
    },

    init() {
        if (this.initialized) return;
        this.initialized = true;

        // Create debounced search function (500ms delay)
        this.debouncedSearch = Utils.debounce(() => {
            this.search();
        }, 500);

        // Search button
        AppState.trackListener(
            this.handlerName,
            document.getElementById('search-btn'),
            'click',
            () => this.search()
        );

        // Debounced input listener for keyword field
        AppState.trackListener(
            this.handlerName,
            document.getElementById('search-keyword'),
            'input',
            () => {
                const keyword = document.getElementById('search-keyword').value;
                if (keyword.trim().length >= 2) {
                    this.debouncedSearch();
                }
            }
        );

        // Save all button
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-all-btn'),
            'click',
            () => this.saveAll()
        );

        // Select all button
        AppState.trackListener(
            this.handlerName,
            document.getElementById('select-all-btn'),
            'click',
            () => this.selectAll()
        );

        // Deselect all button
        AppState.trackListener(
            this.handlerName,
            document.getElementById('deselect-all-btn'),
            'click',
            () => this.deselectAll()
        );

        // Save selected button
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-selected-btn'),
            'click',
            () => this.saveSelected()
        );
    },

    async search() {
        try {
            const keyword = document.getElementById('search-keyword').value.trim();
            const count = parseInt(document.getElementById('search-count').value);
            const sort = document.getElementById('search-sort').value;
            const category = document.getElementById('search-category').value;

            if (!keyword) {
                Utils.showToast('검색어를 입력해주세요', 'warning');
                return;
            }

            try {
                const cacheKey = `search_${keyword}_${count}_${sort}`;
                const response = await Utils.deduplicatedRequest(
                    cacheKey,
                    () => API.searchNews(keyword, count, sort)
                );

                const results = response?.items || response;
                if (results && results.length > 0) {
                    AppState.searchResults = results;
                    AppState.selectedNews.clear();
                    this.renderResults();
                    Utils.showToast(`${results.length}개 검색 완료`, 'success');
                } else {
                    Utils.showToast('검색 결과가 없습니다', 'info');
                }
            } catch (error) {
                Utils.showToast(error.message, 'error');
            }
        } catch (error) {
            console.error('SearchHandler search failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('검색 중 오류가 발생했습니다', 'error');
            }
        }
    },

    renderResults() {
        const container = document.getElementById('search-results-list');
        const resultsDiv = document.getElementById('search-results');
        const summary = document.getElementById('search-summary');

        // FIX #6: Properly clean up all tracked event listeners for container's children
        const listeners = AppState.eventListeners.get(this.handlerName) || [];
        const childElements = container.querySelectorAll('*');

        // Remove event listeners for all child elements
        const listenersToRemove = listeners.filter(l =>
            Array.from(childElements).includes(l.element) || container === l.element
        );

        listenersToRemove.forEach(({ element, event, handler, options }) => {
            element.removeEventListener(event, handler, options);
            // Remove from tracked listeners
            const index = listeners.indexOf({ element, event, handler, options });
            if (index > -1) {
                listeners.splice(index, 1);
            }
        });

        resultsDiv.classList.remove('hidden');
        summary.textContent = `검색 결과: ${AppState.searchResults.length}개 | 선택됨: ${AppState.selectedNews.size}개`;

        // Use DocumentFragment for better performance
        const fragment = document.createDocumentFragment();

        AppState.searchResults.forEach((news, idx) => {
            const item = document.createElement('div');
            item.className = 'search-item';

            const label = document.createElement('label');
            label.className = 'checkbox-label';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.dataset.idx = idx;
            if (AppState.selectedNews.has(idx)) checkbox.checked = true;

            const strong = document.createElement('strong');
            strong.textContent = news.title;

            const small = document.createElement('small');
            const desc = news.content || news.description || '';
            small.textContent = `${desc.substring(0, 100)}...`;

            const br = document.createElement('br');
            const link = document.createElement('a');
            link.href = news.link;
            link.target = '_blank';
            link.className = 'btn btn-secondary';
            link.style.marginTop = '4px';
            link.textContent = '원문 보기';

            label.appendChild(checkbox);
            label.appendChild(strong);
            item.appendChild(label);
            item.appendChild(small);
            item.appendChild(br);
            item.appendChild(link);

            fragment.appendChild(item);
        });

        container.innerHTML = '';
        container.appendChild(fragment);

        // Bind checkbox events
        container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            AppState.trackListener(
                this.handlerName,
                checkbox,
                'change',
                (e) => {
                    const idx = parseInt(e.target.dataset.idx);
                    if (e.target.checked) {
                        AppState.selectedNews.add(idx);
                    } else {
                        AppState.selectedNews.delete(idx);
                    }
                    summary.textContent = `검색 결과: ${AppState.searchResults.length}개 | 선택됨: ${AppState.selectedNews.size}개`;
                    document.getElementById('selected-actions').classList.toggle('hidden', AppState.selectedNews.size === 0);
                }
            );
        });
    },

    async saveAll() {
        try {
            const category = document.getElementById('search-category').value;
            const keyword = document.getElementById('search-keyword').value;

            try {
                const result = await API.saveNews(AppState.searchResults, category, keyword);
                Utils.showToast(`전체 ${result.saved}개 저장 완료!`, 'success');
                AppState.searchResults = [];
                AppState.selectedNews.clear();
                document.getElementById('search-results').classList.add('hidden');
            } catch (error) {
                Utils.showToast(error.message, 'error');
            }
        } catch (error) {
            console.error('SearchHandler saveAll failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('저장 중 오류가 발생했습니다', 'error');
            }
        }
    },

    selectAll() {
        AppState.searchResults.forEach((_, idx) => AppState.selectedNews.add(idx));
        this.renderResults();
    },

    deselectAll() {
        AppState.selectedNews.clear();
        this.renderResults();
    },

    async saveSelected() {
        try {
            const category = document.getElementById('search-category').value;
            const keyword = document.getElementById('search-keyword').value;
            const selected = Array.from(AppState.selectedNews).map(idx => AppState.searchResults[idx]);

            try {
                const result = await API.saveNews(selected, category, keyword);
                Utils.showToast(`${result.saved}개 저장 완료!`, 'success');
                AppState.searchResults = [];
                AppState.selectedNews.clear();
                document.getElementById('search-results').classList.add('hidden');
            } catch (error) {
                Utils.showToast(error.message, 'error');
            }
        } catch (error) {
            console.error('SearchHandler saveSelected failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('저장 중 오류가 발생했습니다', 'error');
            }
        }
    }
};

// =============================================================================
// News Handler with Lazy Rendering
// =============================================================================

const NewsHandler = {
    handlerName: 'NewsHandler',
    initialized: false,
    ITEMS_PER_PAGE: 20,
    currentPage: 0,
    allPendingNews: [],

    cleanup() {
        AppState.cleanupHandler(this.handlerName);
        this.allPendingNews = [];
        this.currentPage = 0;
        this.initialized = false;
    },

    async init() {
        try {
            if (this.initialized) return;
            this.initialized = true;

            await this.loadStats();
            await this.loadPendingNews();
            this.bindEvents();
        } catch (error) {
            console.error('NewsHandler init failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('뉴스 페이지 초기화 중 오류가 발생했습니다', 'error');
            }
        }
    },

    async loadStats() {
        try {
            const stats = await Utils.cachedRequest(
                'news_stats',
                () => API.getNewsStats(),
                5000
            );
            document.getElementById('stat-total').textContent = stats.total || 0;
            document.getElementById('stat-pending').textContent = stats.pending || 0;
            document.getElementById('stat-uploaded').textContent = stats.uploaded || 0;
            document.getElementById('stat-failed').textContent = stats.failed || 0;
        } catch (error) {
            console.error('Load stats error:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('통계 로드 중 오류가 발생했습니다', 'error');
            }
        }
    },

    async loadPendingNews() {
        try {
            const category = document.getElementById('pending-category').value;
            const sort = document.getElementById('pending-sort').value;

            try {
                const catParam = category === 'all' ? null : category;
                const data = await API.getNewsList({
                    category: catParam,
                    status: 'pending',
                    limit: 100
                });

                const newsList = Array.isArray(data) ? data : (data.news || []);

                if (sort === 'oldest' && Array.isArray(newsList)) {
                    newsList.reverse();
                }

                this.allPendingNews = newsList;
                this.currentPage = 0;
                this.renderPendingNews(newsList);
            } catch (error) {
                console.error('Load pending news error:', error);
            }
        } catch (error) {
            console.error('NewsHandler loadPendingNews failed:', error);
            if (typeof Utils !== 'undefined' && Utils.showToast) {
                Utils.showToast('뉴스 로드 중 오류가 발생했습니다', 'error');
            }
        }
    },

    renderPendingNews(newsList) {
        const container = document.getElementById('pending-news-list');

        if (!newsList || newsList.length === 0) {
            container.innerHTML = '<p class="caption">대기 중인 뉴스가 없습니다.</p>';
            return;
        }

        // Render first page only
        const endIndex = Math.min(this.ITEMS_PER_PAGE, newsList.length);
        const fragment = document.createDocumentFragment();

        for (let i = 0; i < endIndex; i++) {
            const news = newsList[i];
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${news.id}</td>
                <td>${escapeHTML((news.title || '').substring(0, 50))}...</td>
                <td>${escapeHTML(news.category || '-')}</td>
                <td>${escapeHTML(news.search_keyword || '-')}</td>
                <td>${Utils.formatDate(news.created_at)}</td>
                <td><button class="btn btn-secondary" data-news-id="${news.id}">삭제</button></td>
            `;
            fragment.appendChild(tr);
        }

        const wrapper = document.createElement('div');

        const caption = document.createElement('p');
        caption.className = 'caption';
        caption.textContent = `총 ${newsList.length || 0}개 뉴스 (표시: ${endIndex})`;
        wrapper.appendChild(caption);

        const table = document.createElement('table');
        table.className = 'news-table';
        table.innerHTML = `
            <thead>
                <tr><th>ID</th><th>제목</th><th>카테고리</th><th>검색어</th><th>수집일</th><th>작업</th></tr>
            </thead>
            <tbody></tbody>
        `;
        table.querySelector('tbody').appendChild(fragment);
        wrapper.appendChild(table);

        // Add "Load More" button if needed
        if (newsList.length > this.ITEMS_PER_PAGE) {
            const loadMoreBtn = document.createElement('button');
            loadMoreBtn.id = 'load-more-news';
            loadMoreBtn.className = 'btn btn-secondary';
            loadMoreBtn.style.marginTop = '10px';
            loadMoreBtn.textContent = '더보기';

            AppState.trackListener(
                this.handlerName,
                loadMoreBtn,
                'click',
                () => this.loadMoreNews()
            );

            wrapper.appendChild(loadMoreBtn);
        }

        container.innerHTML = '';
        container.appendChild(wrapper);

        // Bind delete buttons
        container.querySelectorAll('button[data-news-id]').forEach(btn => {
            const newsId = parseInt(btn.dataset.newsId);
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => this.deleteNews(newsId)
            );
        });
    },

    loadMoreNews() {
        const container = document.getElementById('pending-news-list');
        const tbody = container.querySelector('tbody');
        const fragment = document.createDocumentFragment();

        const startIndex = (this.currentPage + 1) * this.ITEMS_PER_PAGE;
        const endIndex = Math.min(startIndex + this.ITEMS_PER_PAGE, this.allPendingNews.length);

        for (let i = startIndex; i < endIndex; i++) {
            const news = this.allPendingNews[i];
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${news.id}</td>
                <td>${escapeHTML((news.title || '').substring(0, 50))}...</td>
                <td>${escapeHTML(news.category || '-')}</td>
                <td>${escapeHTML(news.search_keyword || '-')}</td>
                <td>${Utils.formatDate(news.created_at)}</td>
                <td><button class="btn btn-secondary" data-news-id="${news.id}">삭제</button></td>
            `;
            fragment.appendChild(tr);
        }

        tbody.appendChild(fragment);
        this.currentPage++;

        // Update count display
        const caption = container.querySelector('.caption');
        caption.textContent = `총 ${this.allPendingNews.length}개 뉴스 (표시: ${endIndex})`;

        // Remove button if all loaded
        if (endIndex >= this.allPendingNews.length) {
            const btn = document.getElementById('load-more-news');
            if (btn) btn.remove();
        }

        // Bind new delete buttons
        container.querySelectorAll('button[data-news-id]').forEach(btn => {
            const newsId = parseInt(btn.dataset.newsId);
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => this.deleteNews(newsId)
            );
        });
    },

    async deleteNews(newsId) {
        if (!confirm('이 뉴스를 삭제하시겠습니까?')) return;

        try {
            await API.deleteNews(newsId);
            Utils.showToast('삭제되었습니다', 'success');
            Utils.clearCache();
            await this.loadPendingNews();
            await this.loadStats();
        } catch (error) {
            Utils.showToast(error.message, 'error');
        }
    },

    bindEvents() {
        AppState.trackListener(
            this.handlerName,
            document.getElementById('pending-category'),
            'change',
            () => this.loadPendingNews()
        );

        AppState.trackListener(
            this.handlerName,
            document.getElementById('pending-sort'),
            'change',
            () => this.loadPendingNews()
        );

        AppState.trackListener(
            this.handlerName,
            document.getElementById('delete-all-pending'),
            'click',
            async () => {
                if (!confirm('정말로 모든 대기중 뉴스를 삭제하시겠습니까?')) return;

                const category = document.getElementById('pending-category').value;
                try {
                    await API.deleteAllNews(category === 'all' ? null : category);
                    Utils.showToast('모든 뉴스가 삭제되었습니다', 'success');
                    Utils.clearCache();
                    await this.loadPendingNews();
                    await this.loadStats();
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Refresh button — force reload from sheet
        AppState.trackListener(
            this.handlerName,
            document.getElementById('refresh-news-btn'),
            'click',
            async () => {
                Utils.clearCache();
                await this.loadPendingNews();
                await this.loadStats();
                Utils.showToast('새로고침 완료', 'success');
            }
        );

        // Sync status check
        const checkSyncBtn = document.getElementById('check-sync-btn');
        if (checkSyncBtn) {
            AppState.trackListener(
                this.handlerName,
                checkSyncBtn,
                'click',
                async () => {
                    const btn = document.getElementById('check-sync-btn');
                    try {
                        btn.disabled = true;
                        btn.textContent = '확인 중...';

                        const response = await API.getSyncStatus();

                        const syncStatus = document.getElementById('sync-status');
                        if (syncStatus) {
                            syncStatus.classList.remove('hidden');
                            const syncedEl = document.getElementById('sync-synced');
                            if (syncedEl) syncedEl.textContent = response.sheet_count || 0;
                        }

                        Utils.showToast(`시트에 ${response.sheet_count || 0}개 행이 있습니다`, 'success');
                    } catch (error) {
                        Utils.showToast(error.message || '동기화 상태 확인 실패', 'error');
                    } finally {
                        if (btn) {
                            btn.disabled = false;
                            btn.textContent = '동기화 상태 확인';
                        }
                    }
                }
            );
        }

        // Tab switching
        document.querySelectorAll('#news-page .tab-btn').forEach(btn => {
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => {
                    const tab = btn.dataset.tab;
                    document.querySelectorAll('#news-page .tab-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    document.querySelectorAll('#news-page .tab-content').forEach(c => c.classList.remove('active'));
                    document.getElementById(tab).classList.add('active');
                }
            );
        });
    }
};

// =============================================================================
// Logs Handler with Interval Cleanup
// =============================================================================

const LogsHandler = {
    handlerName: 'LogsHandler',
    autoRefresh: false,
    refreshInterval: null,
    initialized: false,

    cleanup() {
        this.stopAutoRefresh();
        AppState.cleanupHandler(this.handlerName);
        this.initialized = false;
    },

    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.loadLogs();

        AppState.trackListener(
            this.handlerName,
            document.getElementById('refresh-logs'),
            'click',
            () => this.loadLogs()
        );

        AppState.trackListener(
            this.handlerName,
            document.getElementById('clear-logs'),
            'click',
            async () => {
                if (!confirm('모든 로그를 삭제하시겠습니까?')) return;
                try {
                    await API.clearLogs();
                    Utils.showToast('로그가 삭제되었습니다', 'success');
                    this.loadLogs();
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        AppState.trackListener(
            this.handlerName,
            document.getElementById('auto-refresh-logs'),
            'change',
            (e) => {
                this.autoRefresh = e.target.checked;
                if (this.autoRefresh) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            }
        );

        AppState.trackListener(
            this.handlerName,
            document.getElementById('log-category-filter'),
            'change',
            () => this.loadLogs()
        );
    },

    async loadLogs() {
        const category = document.getElementById('log-category-filter').value;
        const catParam = category === 'all' ? null : category;

        try {
            const cacheKey = `logs_${category}`;
            const logs = await Utils.cachedRequest(
                cacheKey,
                () => API.getLogs(200, catParam),
                2000
            );
            this.renderLogs(Array.isArray(logs) ? logs : (logs.logs || []));
        } catch (error) {
            console.error('Load logs error:', error);
        }
    },

    renderLogs(logs) {
        const container = document.getElementById('logs-container');

        if (!logs || logs.length === 0) {
            container.innerHTML = '<p class="caption">로그가 없습니다. 뉴스 수집이나 업로드를 시작하면 로그가 표시됩니다.</p>';
            return;
        }

        // Use DocumentFragment for better performance
        const fragment = document.createDocumentFragment();

        logs.forEach(log => {
            const entry = document.createElement('div');
            entry.className = 'log-entry';

            const timestamp = document.createElement('span');
            timestamp.className = 'log-timestamp';
            timestamp.textContent = log.timestamp;

            const category = document.createElement('span');
            category.className = `log-category ${log.category || 'SYSTEM'}`;
            category.textContent = log.category;

            const message = document.createElement('span');
            message.className = `log-message ${log.level || 'INFO'}`;
            message.textContent = log.message;

            entry.appendChild(timestamp);
            entry.appendChild(category);
            entry.appendChild(message);

            fragment.appendChild(entry);
        });

        container.innerHTML = '';
        container.appendChild(fragment);

        container.scrollTop = container.scrollHeight;
    },

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshInterval = setInterval(() => {
            this.loadLogs();
        }, 5000);
        AppState.trackInterval(this.handlerName, this.refreshInterval);
    },

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
};

// =============================================================================
// Settings Handler with Cleanup
// =============================================================================

const SettingsHandler = {
    handlerName: 'SettingsHandler',
    initialized: false,

    cleanup() {
        AppState.cleanupHandler(this.handlerName);
        this.initialized = false;
    },

    async init() {
        if (this.initialized) return;
        this.initialized = true;

        await this.loadSettings();
        this.bindEvents();
    },

    async loadSettings() {
        try {
            const config = await API.getConfig();
            this.renderSettings(config);
        } catch (error) {
            console.error('Load settings error:', error);
        }
    },

    renderSettings(config) {
        // Google Sheet URL
        if (config.google_sheet && config.google_sheet.url) {
            document.getElementById('sheet-url').value = config.google_sheet.url;
        }

        // Golftimes credentials
        if (config.golftimes) {
            document.getElementById('golftimes-id').value = config.golftimes.site_id || '';
            document.getElementById('golftimes-pw').value = config.golftimes.site_pw || '';
        }

        // Upload intervals
        if (config.upload_monitor) {
            document.getElementById('check-interval').value = config.upload_monitor.check_interval || 30;
            document.getElementById('concurrent-uploads').value = config.upload_monitor.concurrent_uploads || 2;
        }

        if (config.row_deletion) {
            document.getElementById('delete-interval').value = config.row_deletion.delete_interval || 60;
        }

        // Platforms list
        this.renderPlatforms(config.upload_platforms || {});

        // Keywords rendering (추가)
        this.renderKeywords(config.category_keywords || {});

        const isAdmin = AppState.user.role === 'admin';

        // API 사용량 - admin만 볼 수 있음
        const kkhwanOnlyEl = document.getElementById('kkhwan-only-settings');
        if (isAdmin) {
            kkhwanOnlyEl.classList.remove('hidden');
            this.loadAPIUsage();
        } else {
            kkhwanOnlyEl.classList.add('hidden');
        }

        // Admin-only settings (네이버 API 설정, 사용자 관리)
        const adminOnlyEl = document.getElementById('admin-only-settings');
        const userSettingsEl = document.getElementById('user-settings');

        if (isAdmin) {
            adminOnlyEl.classList.remove('hidden');
            userSettingsEl.classList.add('hidden');
            this.loadUsers();
            this.loadNaverApiConfig();
        } else {
            adminOnlyEl.classList.add('hidden');
            userSettingsEl.classList.remove('hidden');
        }
    },

    renderPlatforms(platforms) {
        const container = document.getElementById('platforms-list');
        container.innerHTML = Object.entries(platforms).map(([id, platform]) => `
            <p><strong>${escapeHTML(platform.display_name || id)}</strong> (열: ${escapeHTML(platform.title_column)}, ${escapeHTML(platform.content_column)}, ${escapeHTML(platform.completed_column)})</p>
        `).join('');
    },

    renderKeywords(categoryKeywords) {
        // Dashboard page 내의 keyword-settings 요소 찾기
        const container = document.getElementById('keyword-settings');
        if (!container) return;

        // If empty, use default categories so users can add keywords
        const defaultCategories = { '연애': { core: [], general: [] }, '경제': { core: [], general: [] }, '스포츠': { core: [], general: [] } };
        const keywordsToRender = Object.keys(categoryKeywords).length > 0 ? categoryKeywords : defaultCategories;

        container.innerHTML = Object.entries(keywordsToRender).map(([category, keywords]) => `
            <div class="keyword-category-block" style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 8px;">
                <h4 style="margin-bottom: 10px;">${escapeHTML(this._getCategoryDisplayName(category))}</h4>
                <div style="margin-bottom: 10px;">
                    <label style="display:block; margin-bottom:5px;">핵심 키워드 (쉼표로 구분):</label>
                    <input type="text"
                           class="keyword-input"
                           data-category="${escapeHTML(category)}"
                           data-type="core"
                           value="${escapeHTML(keywords.core ? keywords.core.join(', ') : '')}"
                           style="width: 100%; padding: 8px; box-sizing: border-box;"
                           placeholder="예: 연애, 열애, 커플">
                </div>
                <div>
                    <label style="display:block; margin-bottom:5px;">일반 키워드 (쉼표로 구분):</label>
                    <input type="text"
                           class="keyword-input"
                           data-category="${escapeHTML(category)}"
                           data-type="general"
                           value="${escapeHTML(keywords.general ? keywords.general.join(', ') : '')}"
                           style="width: 100%; padding: 8px; box-sizing: border-box;"
                           placeholder="예: 신랑, 신부, 웨딩">
                </div>
            </div>
        `).join('');
    },

    _getCategoryDisplayName(category) {
        const displayNames = { '연애': '연애', '경제': '경제', '스포츠': '스포츠' };
        return displayNames[category] || category;
    },

    async loadAPIUsage() {
        try {
            const usage = await API.getAPIUsage();
            const container = document.getElementById('api-usage-info');

            const calls = usage.calls ?? 0;
            const newsCount = usage.news_count ?? 0;
            const dailyLimit = usage.daily_limit ?? 25000;
            const remaining = usage.remaining ?? Math.max(0, dailyLimit - calls);
            const usagePercent = usage.usage_percent ?? (dailyLimit > 0 ? ((calls / dailyLimit) * 100).toFixed(1) : 0);
            const progress = Math.min(usagePercent / 100, 1);

            container.innerHTML = `
                <p class="caption">날짜: ${usage.date || '-'}</p>
                <progress value="${progress}" max="1" style="width:100%"></progress>
                <div class="stats-row">
                    <div class="metric-box">
                        <div class="metric-num">${calls.toLocaleString()}</div>
                        <div class="metric-label">API 호출</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-num">${newsCount.toLocaleString()}</div>
                        <div class="metric-label">수집 뉴스</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-num">${remaining.toLocaleString()}</div>
                        <div class="metric-label">남은 한도</div>
                    </div>
                </div>
                <p class="caption">일일 한도: ${dailyLimit.toLocaleString()}회 (${usagePercent}% 사용)</p>
            `;
        } catch (error) {
            console.error('Load API usage error:', error);
        }
    },

    async loadNaverApiConfig() {
        try {
            const config = await API.getConfig();
            if (config.naver_api) {
                document.getElementById('naver-client-id').value = config.naver_api.client_id || '';
                document.getElementById('naver-client-secret').value = config.naver_api.client_secret || '';
            }
        } catch (error) {
            console.error('Load Naver API config error:', error);
        }
    },

    async loadUsers() {
        try {
            const users = await API.getUsers();
            this.renderUsers(users);
        } catch (error) {
            console.error('Load users error:', error);
        }
    },

    renderUsers(users) {
        const container = document.getElementById('users-list');
        container.innerHTML = Object.entries(users).map(([username, userData]) => `
            <details class="prompt-card">
                <summary><strong>${escapeHTML(username)}</strong> (${escapeHTML(userData.role)})</summary>
                <div class="form-group">
                    <input type="password" class="user-new-pw" placeholder="새 비밀번호" data-username="${escapeHTML(username)}">
                    <select class="user-role-select" data-username="${escapeHTML(username)}">
                        <option value="user" ${userData.role === 'user' ? 'selected' : ''}>user</option>
                        <option value="admin" ${userData.role === 'admin' ? 'selected' : ''}>admin</option>
                    </select>
                    <div style="margin-top:8px;">
                        <button class="btn btn-primary change-user-pw-btn" data-username="${escapeHTML(username)}">비밀번호 변경</button>
                        <button class="btn btn-secondary change-user-role-btn" data-username="${escapeHTML(username)}">권한 변경</button>
                        ${username !== AppState.user.username ? `<button class="btn btn-danger delete-user-btn" data-username="${escapeHTML(username)}">삭제</button>` : ''}
                    </div>
                </div>
            </details>
        `).join('');

        // Bind events
        container.querySelectorAll('.change-user-pw-btn').forEach(btn => {
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => this.changeUserPassword(btn.dataset.username)
            );
        });

        container.querySelectorAll('.change-user-role-btn').forEach(btn => {
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => this.changeUserRole(btn.dataset.username)
            );
        });

        container.querySelectorAll('.delete-user-btn').forEach(btn => {
            AppState.trackListener(
                this.handlerName,
                btn,
                'click',
                () => this.deleteUser(btn.dataset.username)
            );
        });
    },

    bindEvents() {
        // Save Google Sheet URL
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-sheet-btn'),
            'click',
            async () => {
                const url = document.getElementById('sheet-url').value;
                try {
                    await API.setConfig('google_sheet', 'url', url);
                    Utils.clearCache();
                    Utils.showToast('저장되었습니다', 'success');
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Save Golftimes credentials
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-golftimes-btn'),
            'click',
            async () => {
                const id = document.getElementById('golftimes-id').value;
                const pw = document.getElementById('golftimes-pw').value;
                try {
                    await API.setConfig('golftimes', 'site_id', id);
                    await API.setConfig('golftimes', 'site_pw', pw);
                    Utils.clearCache();
                    Utils.showToast('저장되었습니다', 'success');
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Save intervals
        AppState.trackListener(
            this.handlerName,
            document.getElementById('save-interval-btn'),
            'click',
            async () => {
                const checkInterval = parseInt(document.getElementById('check-interval').value);
                const deleteInterval = parseInt(document.getElementById('delete-interval').value);
                const concurrent = parseInt(document.getElementById('concurrent-uploads').value);

                try {
                    await API.setConfig('upload_monitor', 'check_interval', checkInterval);
                    await API.setConfig('row_deletion', 'delete_interval', deleteInterval);
                    await API.setConfig('upload_monitor', 'concurrent_uploads', concurrent);
                    Utils.clearCache();
                    Utils.showToast('저장되었습니다', 'success');
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Save Naver API credentials (즉시 적용)
        const saveApiBtn = document.getElementById('save-api-btn');
        if (saveApiBtn) {
            AppState.trackListener(
                this.handlerName,
                saveApiBtn,
                'click',
                async () => {
                    const clientId = document.getElementById('naver-client-id').value.trim();
                    const clientSecret = document.getElementById('naver-client-secret').value.trim();

                    if (!clientId || !clientSecret) {
                        Utils.showToast('Client ID와 Client Secret을 모두 입력해주세요', 'warning');
                        return;
                    }

                    try {
                        // DB 설정 저장
                        await API.setConfig('naver_api', 'client_id', clientId);
                        await API.setConfig('naver_api', 'client_secret', clientSecret);
                        // 파일에도 즉시 저장 (뉴스 수집 시 바로 사용되도록)
                        await API.saveNaverApiConfig(clientId, clientSecret);
                        Utils.clearCache();
                        Utils.showToast('네이버 API 설정이 저장되고 즉시 적용되었습니다', 'success');
                    } catch (error) {
                        Utils.showToast(error.message, 'error');
                    }
                }
            );
        }

        // Add platform
        AppState.trackListener(
            this.handlerName,
            document.getElementById('add-platform-btn'),
            'click',
            async () => {
                const id = document.getElementById('new-platform-id').value;
                const name = document.getElementById('new-platform-name').value;
                const titleCol = parseInt(document.getElementById('new-title-col').value);
                const contentCol = parseInt(document.getElementById('new-content-col').value);
                const doneCol = parseInt(document.getElementById('new-done-col').value);

                if (!id || !name) {
                    Utils.showToast('플랫폼 ID와 이름을 입력해주세요', 'warning');
                    return;
                }

                // Validate column numbers (1-26 for Excel columns A-Z)
                if (titleCol < 1 || titleCol > 26 || contentCol < 1 || contentCol > 26 || doneCol < 1 || doneCol > 26) {
                    Utils.showToast('열 번호는 1-26 사이의 값이어야 합니다', 'warning');
                    return;
                }

                try {
                    await API.addPlatform(id, name, titleCol, contentCol, doneCol, id);
                    Utils.showToast(`'${name}' 플랫폼이 추가되었습니다`, 'success');
                    await this.loadSettings();
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Add user (admin only)
        AppState.trackListener(
            this.handlerName,
            document.getElementById('add-user-btn'),
            'click',
            async () => {
                const username = document.getElementById('new-username').value;
                const password = document.getElementById('new-user-pw').value;
                const role = document.getElementById('new-user-role').value;

                if (!username || !password) {
                    Utils.showToast('사용자 ID와 비밀번호를 입력하세요', 'warning');
                    return;
                }

                if (password.length < 6) {
                    Utils.showToast('비밀번호는 6자 이상이어야 합니다', 'warning');
                    return;
                }

                try {
                    await API.addUser(username, password, role);
                    Utils.showToast(`'${username}' 사용자가 추가되었습니다`, 'success');
                    document.getElementById('new-username').value = '';
                    document.getElementById('new-user-pw').value = '';
                    await this.loadUsers();
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

        // Change my password
        AppState.trackListener(
            this.handlerName,
            document.getElementById('change-my-pw-btn'),
            'click',
            async () => {
                const currentPw = document.getElementById('current-pw').value;
                const newPw = document.getElementById('my-new-pw').value;
                const newPwConfirm = document.getElementById('my-new-pw-confirm').value;

                if (newPw !== newPwConfirm) {
                    Utils.showToast('새 비밀번호가 일치하지 않습니다', 'warning');
                    return;
                }

                if (newPw.length < 6) {
                    Utils.showToast('비밀번호는 6자 이상이어야 합니다', 'warning');
                    return;
                }

                try {
                    await API.changeMyPassword(currentPw, newPw);
                    Utils.showToast('비밀번호가 변경되었습니다', 'success');
                    document.getElementById('current-pw').value = '';
                    document.getElementById('my-new-pw').value = '';
                    document.getElementById('my-new-pw-confirm').value = '';
                } catch (error) {
                    Utils.showToast(error.message, 'error');
                }
            }
        );

    },

    async changeUserPassword(username) {
        const newPassword = document.querySelector(`.user-new-pw[data-username="${username}"]`).value;

        if (!newPassword) {
            Utils.showToast('새 비밀번호를 입력하세요', 'warning');
            return;
        }

        if (newPassword.length < 6) {
            Utils.showToast('비밀번호는 6자 이상이어야 합니다', 'warning');
            return;
        }

        try {
            await API.changeUserPassword(username, newPassword);
            Utils.showToast(`'${username}' 비밀번호가 변경되었습니다`, 'success');
        } catch (error) {
            Utils.showToast(error.message, 'error');
        }
    },

    async changeUserRole(username) {
        const newRole = document.querySelector(`.user-role-select[data-username="${username}"]`).value;

        try {
            await API.changeUserRole(username, newRole);
            Utils.showToast(`'${username}' 권한이 ${newRole}(으)로 변경되었습니다`, 'success');
            await this.loadUsers();
        } catch (error) {
            Utils.showToast(error.message, 'error');
        }
    },

    async deleteUser(username) {
        if (!confirm(`'${username}' 사용자를 삭제하시겠습니까?`)) return;

        try {
            await API.deleteUser(username);
            Utils.showToast(`'${username}' 사용자가 삭제되었습니다`, 'success');
            await this.loadUsers();
        } catch (error) {
            Utils.showToast(error.message, 'error');
        }
    }
};

// =============================================================================
// Initialize App
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    LoginHandler.init();

    // Hamburger menu toggle for mobile
    const hamburgerBtn = document.getElementById('hamburgerBtn');
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    if (hamburgerBtn && sidebar && sidebarOverlay) {
        hamburgerBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('active');
        });
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
    }
});
// Updated: Added keyword settings rendering in SettingsHandler
