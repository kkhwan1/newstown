/**
 * WebSocket Manager for Real-time Logs
 *
 * @TASK T1.7 - WebSocket Implementation
 * @SPEC CLAUDE.md#Frontend-Implementation
 * @TASK T2.1 - Polling Fallback Implementation
 */

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.listeners = new Map();
        this.isConnected = false;

        // Polling fallback configuration
        this.pollingEnabled = false;
        this.pollingInterval = 2000; // 2 seconds
        this.pollingTimer = null;
        this.lastLogTimestamp = null;
        this.usePolling = true; // Automatically switch to polling if WebSocket fails (FIX #2: default to true for fallback)
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.ws) {
            this.ws.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const token = localStorage.getItem('jwt_token');
        const wsUrl = `${protocol}//${host}/ws/logs${token ? `?token=${token}` : ''}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.emit('message', data);
                } catch (error) {
                    console.error('WebSocket message parse error:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.emit('disconnected');

                // Attempt to reconnect
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`Reconnecting... Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
                    setTimeout(() => this.connect(), this.reconnectDelay);
                } else {
                    console.error('Max reconnect attempts reached, switching to polling mode');
                    this.emit('reconnect-failed');
                    // Automatically switch to polling if WebSocket fails
                    if (this.usePolling) {
                        this.startPolling();
                    }
                }
            };
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.emit('error', error);
            // Switch to polling on connection error
            if (this.usePolling) {
                console.log('Connection failed, switching to polling mode');
                this.startPolling();
            }
        }
    }

    /**
     * Disconnect WebSocket and stop polling
     */
    disconnect() {
        // Stop polling if active
        this.stopPolling();

        // Close WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
            this.isConnected = false;
        }
    }

    /**
     * Send message through WebSocket
     */
    send(data) {
        if (this.ws && this.isConnected) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket is not connected');
        }
    }

    /**
     * Register event listener
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Emit event to all listeners
     */
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Listener error for event '${event}':`, error);
                }
            });
        }
    }

    /**
     * Check if WebSocket is connected
     */
    connected() {
        return this.isConnected || this.pollingEnabled;
    }

    /**
     * Start polling mode (fallback when WebSocket fails)
     */
    startPolling() {
        if (this.pollingEnabled) {
            console.log('Polling already enabled');
            return;
        }

        console.log('Starting polling mode');
        this.stopPolling(); // FIX #1: Clear any existing timer BEFORE setting pollingEnabled
        this.pollingEnabled = true;

        // Reset lastLogTimestamp to get recent logs
        this.lastLogTimestamp = null;

        this.pollLogs();

        // Set up recurring poll
        this.pollingTimer = setInterval(() => {
            this.pollLogs();
        }, this.pollingInterval);

        this.emit('polling-started');
    }

    /**
     * Stop polling mode
     */
    stopPolling() {
        if (this.pollingTimer) {
            clearInterval(this.pollingTimer);
            this.pollingTimer = null;
        }
        this.pollingEnabled = false;
        console.log('Polling stopped');
    }

    /**
     * Poll for new logs via HTTP
     */
    async pollLogs() {
        try {
            const token = localStorage.getItem('jwt_token');
            const headers = {
                'Content-Type': 'application/json'
            };

            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            // Build query parameters
            const params = new URLSearchParams();
            if (this.lastLogTimestamp) {
                params.append('since', this.lastLogTimestamp);
            } else {
                // FIX #3: Initialize timestamp to 60 seconds ago on first poll
                const sixtySecondsAgo = new Date(Date.now() - 60000).toISOString();
                params.append('since', sixtySecondsAgo);
            }
            params.append('limit', '100'); // Get up to 100 new logs per poll

            const response = await fetch(`/api/logs?${params.toString()}`, {
                method: 'GET',
                headers: headers
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.logs && data.logs.length > 0) {
                // Update timestamp with the most recent log
                this.lastLogTimestamp = data.logs[data.logs.length - 1].timestamp;

                // Emit logs in WebSocket-compatible format
                data.logs.forEach(log => {
                    this.emit('message', {
                        type: 'log',
                        data: log
                    });
                });
            }
        } catch (error) {
            console.error('Polling error:', error);
            // Don't emit error events for polling to avoid noise
        }
    }

    /**
     * Switch from polling back to WebSocket
     */
    switchToWebSocket() {
        if (this.pollingEnabled) {
            this.stopPolling();
            this.reconnectAttempts = 0;
            this.connect();
        }
    }

    /**
     * Enable automatic fallback to polling
     * @param {boolean} enabled - Whether to enable polling fallback
     */
    setPollingFallback(enabled) {
        this.usePolling = enabled;
        console.log(`Polling fallback ${enabled ? 'enabled' : 'disabled'}`);
    }

    /**
     * Set polling interval (milliseconds)
     * @param {number} interval - Polling interval in ms
     */
    setPollingInterval(interval) {
        this.pollingInterval = interval;
        // Restart polling with new interval if currently polling
        if (this.pollingEnabled) {
            this.stopPolling();
            this.startPolling();
        }
    }

    /**
     * Get current connection mode
     * @returns {string} - 'websocket', 'polling', or 'disconnected'
     */
    getMode() {
        if (this.isConnected) {
            return 'websocket';
        } else if (this.pollingEnabled) {
            return 'polling';
        } else {
            return 'disconnected';
        }
    }
}

// Create global WebSocket manager instance
const wsManager = new WebSocketManager();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = wsManager;
}

// Export to global window object for browser
if (typeof window !== 'undefined') {
    window.wsManager = wsManager;
    window.WS = wsManager;  // alias for convenience
}
