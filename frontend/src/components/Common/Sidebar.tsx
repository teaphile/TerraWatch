import React, { useEffect, useState } from 'react';
import {
  Leaf,
  AlertTriangle,
  Bell,
  Sprout,
  Download,
  Activity,
  ChevronLeft,
  ChevronRight,
  CloudSun,
  X,
} from 'lucide-react';

export type SidebarTab =
  | 'soil'
  | 'risk'
  | 'earthquakes'
  | 'alerts'
  | 'recommendations'
  | 'weather'
  | 'export';

interface SidebarProps {
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  alertCount?: number;
}

const TABS: { key: SidebarTab; label: string; shortLabel: string; icon: typeof Leaf }[] = [
  { key: 'soil', label: 'Soil Analysis', shortLabel: 'Soil', icon: Leaf },
  { key: 'risk', label: 'Risk Assessment', shortLabel: 'Risk', icon: AlertTriangle },
  { key: 'earthquakes', label: 'Earthquakes', shortLabel: 'Quakes', icon: Activity },
  { key: 'weather', label: 'Weather', shortLabel: 'Weather', icon: CloudSun },
  { key: 'alerts', label: 'Alerts', shortLabel: 'Alerts', icon: Bell },
  { key: 'recommendations', label: 'Recommendations', shortLabel: 'Recs', icon: Sprout },
  { key: 'export', label: 'Export Data', shortLabel: 'Export', icon: Download },
];

// Mobile shows first 5 tabs in bottom nav
const MOBILE_TABS = TABS.slice(0, 5);

function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);
  return isMobile;
}

const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  collapsed,
  onToggle,
  children,
  alertCount = 0,
}) => {
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // When mobile tab is tapped, open drawer
  const handleMobileTab = (key: SidebarTab) => {
    onTabChange(key);
    setDrawerOpen(true);
  };

  // Close drawer
  const closeDrawer = () => setDrawerOpen(false);

  // ─── Mobile Layout ───────────────────────────────────
  if (isMobile) {
    return (
      <>
        {/* Mobile Bottom Navigation */}
        <nav className="mobile-nav bg-surface-800/95 border-t border-surface-600 safe-bottom">
          {MOBILE_TABS.map(({ key, shortLabel, icon: Icon }) => (
            <button
              key={key}
              onClick={() => handleMobileTab(key)}
              className={`flex flex-col items-center justify-center gap-0.5 px-1 py-1.5 rounded-lg transition-colors min-w-[48px] ${
                activeTab === key && drawerOpen
                  ? 'text-primary-400'
                  : 'text-text-muted'
              }`}
            >
              <span className="relative">
                <Icon className="w-5 h-5" />
                {key === 'alerts' && alertCount > 0 && (
                  <span className="absolute -top-1 -right-1.5 w-3.5 h-3.5 bg-red-500 rounded-full text-[7px] text-white flex items-center justify-center font-bold">
                    {alertCount > 9 ? '9+' : alertCount}
                  </span>
                )}
              </span>
              <span className="text-[9px] font-medium leading-none">{shortLabel}</span>
            </button>
          ))}
        </nav>

        {/* Mobile Drawer Overlay */}
        {drawerOpen && (
          <div
            className="fixed inset-0 z-[1999] bg-black/40"
            onClick={closeDrawer}
          />
        )}

        {/* Mobile Drawer */}
        {drawerOpen && (
          <div className="mobile-drawer bg-surface-800 border-t border-surface-600 slide-up">
            <div className="mobile-drawer-handle" />
            <div className="flex items-center justify-between px-4 py-2 border-b border-surface-600">
              <h2 className="text-sm font-semibold text-text-primary">
                {TABS.find((t) => t.key === activeTab)?.label}
              </h2>
              <button
                onClick={closeDrawer}
                className="p-1.5 rounded-lg hover:bg-surface-700 text-text-muted"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="overflow-y-auto p-3 scrollbar-thin" style={{ maxHeight: 'calc(85vh - 60px)' }}>
              {children}
            </div>
          </div>
        )}
      </>
    );
  }

  // ─── Desktop Layout ──────────────────────────────────
  return (
    <div
      className={`flex flex-shrink-0 h-full transition-all duration-300 ${
        collapsed ? 'w-12' : 'w-[360px] lg:w-[380px] xl:w-[400px]'
      }`}
    >
      {/* Icon rail */}
      <div className="w-12 bg-surface-900 border-r border-surface-600 flex flex-col items-center py-2 gap-1">
        {TABS.map(({ key, shortLabel, icon: Icon }) => (
          <button
            key={key}
            onClick={() => {
              onTabChange(key);
              if (collapsed) onToggle();
            }}
            className={`sidebar-icon-btn relative w-9 h-9 flex items-center justify-center rounded-lg transition-colors ${
              activeTab === key
                ? 'bg-primary-600/20 text-primary-400'
                : 'text-text-muted hover:text-text-secondary hover:bg-surface-700'
            }`}
            title={shortLabel}
          >
            <Icon className="w-4 h-4" />
            {key === 'alerts' && alertCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 bg-red-500 rounded-full text-[8px] text-white flex items-center justify-center font-bold">
                {alertCount > 9 ? '9+' : alertCount}
              </span>
            )}
          </button>
        ))}

        <div className="flex-1" />

        <button
          onClick={onToggle}
          className="w-9 h-9 flex items-center justify-center text-text-muted hover:text-text-secondary rounded-lg hover:bg-surface-700 transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Panel content */}
      {!collapsed && (
        <div className="flex-1 bg-surface-800 border-r border-surface-600 overflow-hidden flex flex-col">
          <div className="px-3 py-2 border-b border-surface-600">
            <h2 className="text-sm font-semibold text-text-primary">
              {TABS.find((t) => t.key === activeTab)?.label}
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
            <div className="fade-in">{children}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sidebar;
