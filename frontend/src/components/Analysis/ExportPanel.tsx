import React from 'react';
import { Download, FileSpreadsheet, Globe, FileText } from 'lucide-react';
import api from '../../services/api';

interface ExportPanelProps {
  lat: number | null;
  lon: number | null;
}

const ExportPanel: React.FC<ExportPanelProps> = ({ lat, lon }) => {
  if (lat == null || lon == null) {
    return (
      <div className="p-4 text-center text-text-muted">
        <Download className="w-6 h-6 mx-auto mb-2 opacity-30" />
        <p className="text-sm">Select a location to export data</p>
      </div>
    );
  }

  const exports = [
    {
      label: 'Full Report (JSON)',
      icon: FileText,
      url: api.exportReport(lat, lon),
      desc: 'Complete analysis with soil, risk & recommendations',
    },
    {
      label: 'CSV Spreadsheet',
      icon: FileSpreadsheet,
      url: api.exportCsv(lat, lon),
      desc: 'Soil properties and risk scores',
    },
    {
      label: 'Soil GeoJSON',
      icon: Globe,
      url: api.exportGeojson(lat, lon),
      desc: 'Soil data for GIS tools',
    },
    {
      label: 'Risk GeoJSON',
      icon: Globe,
      url: api.exportRiskGeojson(lat, lon),
      desc: 'Risk data for GIS tools',
    },
  ];

  return (
    <div className="space-y-2">
      <p className="text-xs text-text-secondary">
        Export data for {lat.toFixed(4)}, {lon.toFixed(4)}
      </p>
      {exports.map(({ label, icon: Icon, url, desc }) => (
        <a
          key={label}
          href={url}
          download
          className="flex items-center gap-3 p-3 rounded-lg bg-surface-700/30 border border-surface-600 hover:bg-surface-700/60 transition-colors"
        >
          <Icon className="w-5 h-5 text-primary-400" />
          <div>
            <p className="text-sm font-medium text-text-primary">{label}</p>
            <p className="text-xs text-text-muted">{desc}</p>
          </div>
          <Download className="w-4 h-4 ml-auto text-text-muted" />
        </a>
      ))}
    </div>
  );
};

export default ExportPanel;
