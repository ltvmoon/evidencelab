import React, { useState, useEffect, useCallback, useRef } from 'react';

/** Whether the drilldown should inherit the parent investigation's
 *  context (``'subtopic'``) or be treated as a fresh independent
 *  question (``'newtopic'``). */
export type DrilldownMode = 'subtopic' | 'newtopic';

interface DigDeeperPopoverProps {
  containerRef: React.RefObject<HTMLDivElement | null>;
  onDrilldown: (selectedText: string, mode: DrilldownMode) => void;
  disabled?: boolean;
}

const MIN_SELECTION_LENGTH = 10;

export const DigDeeperPopover: React.FC<DigDeeperPopoverProps> = ({
  containerRef,
  onDrilldown,
  disabled,
}) => {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const [selectedText, setSelectedText] = useState('');
  const containerEl = useRef<HTMLDivElement>(null);

  const handleSelectionChange = useCallback(() => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || !containerRef.current) {
      setVisible(false);
      return;
    }

    const text = selection.toString().trim();
    if (text.length < MIN_SELECTION_LENGTH) {
      setVisible(false);
      return;
    }

    const range = selection.getRangeAt(0);
    if (!containerRef.current.contains(range.commonAncestorContainer)) {
      setVisible(false);
      return;
    }

    const rect = range.getBoundingClientRect();
    const containerRect = containerRef.current.getBoundingClientRect();

    setPosition({
      top: rect.bottom - containerRect.top + 4,
      left: rect.left - containerRect.left + rect.width / 2,
    });
    setSelectedText(text);
    setVisible(true);
  }, [containerRef]);

  useEffect(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [handleSelectionChange]);

  const handleClick = useCallback(
    (mode: DrilldownMode) => (e: React.MouseEvent) => {
      e.preventDefault();
      onDrilldown(selectedText, mode);
      setVisible(false);
      window.getSelection()?.removeAllRanges();
    },
    [onDrilldown, selectedText],
  );

  if (!visible || disabled) return null;

  return (
    <div
      ref={containerEl}
      className="dig-deeper-popover"
      style={{
        position: 'absolute',
        top: position.top,
        left: position.left,
        transform: 'translateX(-50%)',
      }}
      onMouseDown={(e) => e.preventDefault()}
    >
      <button
        type="button"
        className="dig-deeper-popover-btn"
        aria-label="Find out more as a sub-topic of the current investigation"
        onClick={handleClick('subtopic')}
      >
        Find out more (sub-topic)
      </button>
      <button
        type="button"
        className="dig-deeper-popover-btn"
        aria-label="Find out more as a new independent topic"
        onClick={handleClick('newtopic')}
      >
        Find out more (new topic)
      </button>
    </div>
  );
};
