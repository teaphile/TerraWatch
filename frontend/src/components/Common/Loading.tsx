/**
 * Loading spinner component.
 */

import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingProps {
  text?: string;
  className?: string;
}

const Loading: React.FC<LoadingProps> = ({ text = 'Loading...', className = '' }) => (
  <div className={`flex flex-col items-center justify-center p-8 ${className}`}>
    <Loader2 className="w-8 h-8 animate-spin text-primary-400 mb-2" />
    <p className="text-sm text-text-muted">{text}</p>
  </div>
);

export default Loading;
