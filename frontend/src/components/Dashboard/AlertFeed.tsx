import React from 'react';
import {
  AlertTriangle,
  AlertCircle,
  Bell,
  Info,
  X,
} from 'lucide-react';
import type { Alert } from '../../types';

interface AlertFeedProps {
  alerts: Alert[];
  onDismiss?: (id: string) => void;
}

function getSeverityStyle(severity: string) {
  switch (severity) {
    case 'critical':
      return {
        bg: 'bg-red-500/10 border-red-500/40',
        icon: AlertTriangle,
        iconColor: 'text-red-500',
        badge: 'bg-red-500 text-white',
      };
    case 'warning':
      return {
        bg: 'bg-orange-500/10 border-orange-500/40',
        icon: AlertCircle,
        iconColor: 'text-orange-500',
        badge: 'bg-orange-500 text-white',
      };
    case 'watch':
      return {
        bg: 'bg-yellow-500/10 border-yellow-500/40',
        icon: Bell,
        iconColor: 'text-yellow-500',
        badge: 'bg-yellow-500 text-black',
      };
    default:
      return {
        bg: 'bg-blue-500/10 border-blue-500/40',
        icon: Info,
        iconColor: 'text-blue-400',
        badge: 'bg-blue-500 text-white',
      };
  }
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

const AlertFeed: React.FC<AlertFeedProps> = ({ alerts, onDismiss }) => {
  if (alerts.length === 0) {
    return (
      <div className="p-4 text-center text-text-muted">
        <Bell className="w-6 h-6 mx-auto mb-2 opacity-30" />
        <p className="text-sm">No active alerts</p>
        <p className="text-xs mt-1">Alerts appear when earthquakes or hazards are detected</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 max-h-[calc(100vh-140px)] overflow-y-auto pr-1 scrollbar-thin">
      {alerts.map((alert) => {
        const style = getSeverityStyle(alert.severity);
        const Icon = style.icon;

        return (
          <div
            key={alert.id}
            className={`p-3 rounded-lg border ${style.bg} transition-all hover:brightness-110`}
          >
            <div className="flex items-start gap-2">
              <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${style.iconColor}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${style.badge}`}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <span className="text-[10px] text-text-muted">
                    {timeAgo(alert.created_at)}
                  </span>
                </div>
                <p className="text-sm font-medium text-text-primary truncate">{alert.title}</p>
                <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                  {alert.description}
                </p>
                {alert.latitude && alert.longitude && (
                  <p className="text-[10px] text-text-muted mt-1">
                    📍 {alert.latitude.toFixed(2)}, {alert.longitude.toFixed(2)}
                  </p>
                )}
              </div>
              {onDismiss && (
                <button
                  onClick={() => onDismiss(alert.id)}
                  className="text-text-muted hover:text-text-secondary p-0.5"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default AlertFeed;
