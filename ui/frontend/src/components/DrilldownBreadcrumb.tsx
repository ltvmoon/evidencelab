import React from 'react';
import { DrilldownNode } from '../types/api';
import { getAncestorLabels } from '../utils/drilldownUtils';

interface DrilldownBreadcrumbProps {
  stackDepth: number;
  onBack: () => void;
  currentHighlight?: string;
  /** Drilldown tree, used to render the full ancestor path so the user
   *  can see the overlying investigation context, not just the leaf. */
  tree?: DrilldownNode | null;
  /** Id of the node the user is currently viewing in the tree. */
  currentNodeId?: string | null;
}

export const DrilldownBreadcrumb: React.FC<DrilldownBreadcrumbProps> = ({
  stackDepth,
  currentHighlight,
  tree,
  currentNodeId,
}) => {
  if (stackDepth === 0) return null;

  // Prefer the full ancestor path when we have the tree; fall back to
  // just the current label for callers that haven't migrated yet.
  const ancestors = getAncestorLabels(tree, currentNodeId);
  const labels = ancestors.length > 0
    ? ancestors
    : (currentHighlight ? [currentHighlight] : []);

  if (labels.length === 0) return null;

  return (
    <div className="ai-drilldown-breadcrumb">
      <span className="ai-drilldown-context">
        Exploring:{' '}
        {labels.map((label, i) => (
          <React.Fragment key={`${i}-${label}`}>
            {i > 0 && <span className="ai-drilldown-sep"> › </span>}
            <span
              className={
                i === labels.length - 1
                  ? 'ai-drilldown-current'
                  : 'ai-drilldown-ancestor'
              }
            >
              &ldquo;{label}&rdquo;
            </span>
          </React.Fragment>
        ))}
      </span>
    </div>
  );
};
