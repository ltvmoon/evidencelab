import React, { useState } from 'react';
import { SearchToolCall } from '../../types/api';

interface ToolCallPanelProps {
  toolCalls: SearchToolCall[];
  defaultExpanded?: boolean;
}

export const ToolCallPanel: React.FC<ToolCallPanelProps> = ({
  toolCalls,
  defaultExpanded = false,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (toolCalls.length === 0) return null;

  const totalResults = toolCalls.reduce((sum, tc) => sum + tc.resultCount, 0);

  return (
    <div className="tool-call-panel">
      <button
        className="tool-call-panel-toggle"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <span className="tool-call-panel-icon">{expanded ? '\u25BC' : '\u25B6'}</span>
        <span className="tool-call-panel-summary">
          {toolCalls.length} search{toolCalls.length !== 1 ? 'es' : ''} &middot; {totalResults} result{totalResults !== 1 ? 's' : ''}
        </span>
      </button>
      {expanded && (
        <div className="tool-call-panel-details">
          {toolCalls.map((tc, i) => (
            <div key={i} className="tool-call-item">
              <span className="tool-call-query">{tc.query}</span>
              <span className="tool-call-count">{tc.resultCount} results</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
