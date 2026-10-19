/**
 * WebSocket client for the TerraWatch alert stream.
 *
 * The backend sends three message types:
 *   - `initial`   : snapshot of active alerts on connect
 *   - `alert`     : a newly created alert
 *   - `heartbeat` : keep-alive every 30 s
 *
 * The client reconnects with exponential backoff and pings the server so
 * intermediate proxies do not drop an idle connection.
 */

import type { Alert } from '../types';

type AlertHandler = (alert: Alert) => void;
type InitialHandler = (alerts: Alert[]) => void;
type ConnectionHandler = (connected: boolean) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Set<AlertHandler> = new Set();
  private initialHandlers: Set<InitialHandler> = new Set();
  private connHandlers: Set<ConnectionHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectDelay = 2000;
  private readonly maxDelay = 30000;
  private manuallyClosed = false;

  private getUrl(): string {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${window.location.host}/ws/alerts`;
  }

  connect(): void {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this.manuallyClosed = false;

    try {
      this.ws = new WebSocket(this.getUrl());

      this.ws.onopen = () => {
        console.info('[WS] Connected to alert stream');
        this.reconnectDelay = 2000;
        this.notifyConnection(true);
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'alert' && msg.data) {
            this.handlers.forEach((handler) => handler(msg.data as Alert));
          } else if (msg.type === 'initial' && msg.data) {
            const snapshot = (msg.data.active_alerts ?? []) as Alert[];
            this.initialHandlers.forEach((handler) => handler(snapshot));
          }
          // heartbeat / pong require no action
        } catch (err) {
          console.warn('[WS] Failed to parse message:', err);
        }
      };

      this.ws.onclose = () => {
        this.stopPing();
        this.notifyConnection(false);
        if (!this.manuallyClosed) {
          this.scheduleReconnect();
        }
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
    this.manuallyClosed = true;
    this.stopPing();
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

  onInitial(handler: InitialHandler): () => void {
    this.initialHandlers.add(handler);
    return () => this.initialHandlers.delete(handler);
  }

  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connHandlers.add(handler);
    return () => this.connHandlers.delete(handler);
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 25_000);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private notifyConnection(connected: boolean): void {
    this.connHandlers.forEach((handler) => handler(connected));
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
