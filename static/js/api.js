/**
 * API Communication Module
 * Handles all backend API calls
 *
 * @TASK T1.7 - Frontend API Layer
 * @SPEC CLAUDE.md#Frontend-Implementation
 */

const API = {
    baseURL: '/api',

    /**
     * Generic fetch wrapper
     */
    async fetch(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const token = localStorage.getItem('jwt_token');

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            // Handle 401 Unauthorized
            if (response.status === 401) {
                localStorage.removeItem('jwt_token');
                window.location.reload();
                return null;
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'API request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
                if (typeof Utils !== 'undefined' && Utils.showToast) {
                    Utils.showToast('네트워크 연결을 확인해주세요', 'error');
                }
            }
            throw error;
        }
    },

    /**
     * Authentication
     */
    async login(username, password, remember = false) {
        return this.fetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password, remember })
        });
    },

    async logout() {
        return this.fetch('/auth/logout', { method: 'POST' });
    },

    async getCurrentUser() {
        return this.fetch('/auth/me');
    },

    /**
     * Process Management
     */
    async getProcessStatus(processName) {
        return this.fetch(`/process/${processName}`);
    },

    async startProcess(processName, config) {
        return this.fetch(`/process/${processName}`, {
            method: 'POST',
            body: JSON.stringify({ action: 'start', config })
        });
    },

    async stopProcess(processName) {
        return this.fetch(`/process/${processName}`, {
            method: 'POST',
            body: JSON.stringify({ action: 'stop' })
        });
    },

    async stopAllProcesses() {
        return this.fetch('/process/stop-all', {
            method: 'POST'
        });
    },

    async getProcessLogs(processName, lines = 50) {
        return this.fetch(`/process/${processName}/logs?lines=${lines}`);
    },

    /**
     * News Management
     */
    async searchNews(keyword, display = 20, sort = 'date') {
        return this.fetch('/news/search', {
            method: 'POST',
            body: JSON.stringify({ keyword, display, sort })
        });
    },

    async saveNews(newsList, category, searchKeyword = null) {
        const mappedList = newsList.map(item => ({
            title: item.title,
            content: item.content || item.description || '',
            link: item.link || item.originallink || '',
            category: item.category,
            search_keyword: searchKeyword
        }));
        return this.fetch('/news/save', {
            method: 'POST',
            body: JSON.stringify({
                news_list: mappedList,
                category,
                search_keyword: searchKeyword
            })
        });
    },

    async getNewsList(options = {}) {
        const params = new URLSearchParams();
        if (options.category) params.append('category', options.category);
        if (options.status) params.append('status', options.status);
        if (options.limit) params.append('limit', options.limit);
        if (options.offset) params.append('offset', options.offset);

        return this.fetch(`/news?${params}`);
    },

    async getNewsStats() {
        return this.fetch('/news/stats');
    },

    async deleteNews(newsId) {
        return this.fetch(`/news/${newsId}`, {
            method: 'DELETE'
        });
    },

    async deleteAllNews(category = null) {
        const params = category ? `?category=${category}` : '';
        return this.fetch(`/news/all${params}`, {
            method: 'DELETE'
        });
    },

    /**
     * Sync Management
     */
    async getSyncStatus() {
        return this.fetch('/sync/status');
    },

    async syncDeleteFromSheet(links) {
        return this.fetch('/sync/delete-from-sheet', {
            method: 'POST',
            body: JSON.stringify({ links })
        });
    },

    /**
     * Logs
     */
    async getLogs(limit = 200, category = null) {
        const params = new URLSearchParams();
        params.append('limit', limit);
        if (category) params.append('category', category);

        return this.fetch(`/logs?${params}`);
    },

    async clearLogs() {
        return this.fetch('/logs', {
            method: 'DELETE'
        });
    },

    /**
     * Configuration
     */
    async getConfig(section = null) {
        const url = section ? `/config/${section}` : '/config';
        return this.fetch(url);
    },

    async setConfig(section, key, value) {
        return this.fetch(`/config/${section}/${key}`, {
            method: 'PUT',
            body: JSON.stringify({ value })
        });
    },

    async setConfigSection(section, data) {
        return this.fetch(`/config/${section}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    async updateConfig(section, data) {
        return this.fetch('/config', {
            method: 'POST',
            body: JSON.stringify({ section, data })
        });
    },

    /**
     * Platform Management
     */
    async getPlatforms() {
        return this.fetch('/platforms');
    },

    async addPlatform(platformId, displayName, titleColumn, contentColumn, completedColumn, credentialsSection) {
        return this.fetch('/platforms', {
            method: 'POST',
            body: JSON.stringify({
                platform_id: platformId,
                display_name: displayName,
                title_column: titleColumn,
                content_column: contentColumn,
                completed_column: completedColumn,
                credentials_section: credentialsSection
            })
        });
    },

    async removePlatform(platformId) {
        return this.fetch(`/platforms/${platformId}`, {
            method: 'DELETE'
        });
    },

    async updatePlatform(platformId, updates) {
        return this.fetch(`/platforms/${platformId}`, {
            method: 'PUT',
            body: JSON.stringify(updates)
        });
    },

    /**
     * User Management (Admin)
     */
    async getUsers() {
        return this.fetch('/admin/users');
    },

    async addUser(username, password, role) {
        return this.fetch('/admin/users', {
            method: 'POST',
            body: JSON.stringify({ username, password, role })
        });
    },

    async deleteUser(username) {
        return this.fetch(`/admin/users/${username}`, {
            method: 'DELETE'
        });
    },

    async changeUserPassword(username, newPassword) {
        return this.fetch(`/admin/users/${username}/password`, {
            method: 'PUT',
            body: JSON.stringify({ new_password: newPassword })
        });
    },

    async changeUserRole(username, newRole) {
        return this.fetch(`/admin/users/${username}/role`, {
            method: 'PUT',
            body: JSON.stringify({ role: newRole })
        });
    },

    /**
     * API Usage
     */
    async getAPIUsage() {
        return this.fetch('/usage/api');
    },

    /**
     * Naver API Config - 파일에 즉시 저장
     */
    async saveNaverApiConfig(clientId, clientSecret) {
        return this.fetch('/config/naver-api/file', {
            method: 'POST',
            body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
        });
    },

    /**
     * Self Password Change
     */
    async changeMyPassword(currentPassword, newPassword) {
        return this.fetch('/auth/password', {
            method: 'PUT',
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}

// Export to global window object for browser
if (typeof window !== 'undefined') {
    window.API = API;
}
