/**
 * WebSocket service for real-time alerts from TerraWatch backend.
 */

import type { Alert } from '../types';

type AlertHandler = (alert: Alert) => void;
type ConnectionHandler = (connected: boolean) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Set<AlertHandler> = new Set();
  private connHandlers: Set<ConnectionHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 2000;
  private maxDelay = 30000;

  private getUrl(): string {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${window.location.host}/ws/alerts`;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(this.getUrl());

      this.ws.onopen = () => {
        console.log('[WS] Connected to alert stream');
        this.reconnectDelay = 2000;
        this.notifyConnection(true);
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          // Only forward actual alert messages
          if (msg.type === 'alert' && msg.data) {
            this.handlers.forEach((handler) => handler(msg.data as Alert));
          }
          // Ignore heartbeat, pong, initial messages
        } catch (err) {
          console.warn('[WS] Failed to parse message:', err);
        }
      };

      this.ws.onclose = () => {
        this.notifyConnection(false);
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.notifyConnection(false);
        this.ws?.close();
      };
    } catch (err) {
      console.error('[WS] Connection failed:', err);
      this.notifyConnection(false);
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.notifyConnection(false);
  }

  subscribe(handler: AlertHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connHandlers.add(handler);
    return () => this.connHandlers.delete(handler);
  }

  private notifyConnection(connected: boolean): void {
    this.connHandlers.forEach((h) => h(connected));
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxDelay);
      this.connect();
    }, this.reconnectDelay);
  }
}

export const wsService = new WebSocketService();
export default wsService;
