import React, { useRef } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';

import { DigDeeperPopover } from '../components/DigDeeperPopover';

// jsdom doesn't implement layout — stub bounding rects so the popover's
// position calculation doesn't blow up during render.
const fakeRect = (): DOMRect => ({
  top: 10, bottom: 30, left: 10, right: 50,
  width: 40, height: 20, x: 10, y: 10,
  toJSON: () => ({}),
});
beforeAll(() => {
  Object.defineProperty(Range.prototype, 'getBoundingClientRect', {
    configurable: true, value: () => fakeRect(),
  });
  Object.defineProperty(Element.prototype, 'getBoundingClientRect', {
    configurable: true, value: () => fakeRect(),
  });
});

// Selection is a global on the document; clear it so each test starts
// from a known-empty state.
beforeEach(() => {
  window.getSelection()?.removeAllRanges();
});

const Harness: React.FC<{
  text: string;
  onDrilldown: (text: string, mode: 'subtopic' | 'newtopic') => void;
}> = ({ text, onDrilldown }) => {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div ref={ref}>
      <p data-testid="paragraph">{text}</p>
      <DigDeeperPopover containerRef={ref} onDrilldown={onDrilldown} />
    </div>
  );
};

const selectParagraph = () => {
  // jsdom doesn't fully implement text selection — Range objects work but
  // window.getSelection().toString() returns '' even after addRange. Stub
  // the global getSelection so the popover sees a real (non-collapsed)
  // selection over the paragraph contents.
  const p = screen.getByTestId('paragraph');
  const range = document.createRange();
  range.selectNodeContents(p);
  jest.spyOn(window, 'getSelection').mockReturnValue({
    isCollapsed: false,
    rangeCount: 1,
    getRangeAt: () => range,
    toString: () => p.textContent || '',
    removeAllRanges: jest.fn(),
  } as unknown as Selection);
  act(() => {
    document.dispatchEvent(new Event('selectionchange'));
  });
};

describe('DigDeeperPopover', () => {
  test('renders both sub-topic and new-topic buttons after a long enough selection', () => {
    render(
      <Harness
        text="A long enough sentence about cash based transfers to clear the threshold."
        onDrilldown={jest.fn()}
      />,
    );
    selectParagraph();
    expect(screen.getByRole('button', { name: /sub-topic of the current investigation/i }))
      .toHaveTextContent(/Find out more \(sub-topic\)/);
    expect(screen.getByRole('button', { name: /new independent topic/i }))
      .toHaveTextContent(/Find out more \(new topic\)/);
  });

  test('sub-topic button fires onDrilldown with mode="subtopic"', () => {
    const onDrilldown = jest.fn();
    render(
      <Harness
        text="A long enough sentence about cash based transfers to clear the threshold."
        onDrilldown={onDrilldown}
      />,
    );
    selectParagraph();
    fireEvent.click(screen.getByRole('button', { name: /sub-topic/i }));
    expect(onDrilldown).toHaveBeenCalledTimes(1);
    expect(onDrilldown.mock.calls[0][1]).toBe('subtopic');
  });

  test('new-topic button fires onDrilldown with mode="newtopic"', () => {
    const onDrilldown = jest.fn();
    render(
      <Harness
        text="A long enough sentence about cash based transfers to clear the threshold."
        onDrilldown={onDrilldown}
      />,
    );
    selectParagraph();
    fireEvent.click(screen.getByRole('button', { name: /new independent topic/i }));
    expect(onDrilldown).toHaveBeenCalledTimes(1);
    expect(onDrilldown.mock.calls[0][1]).toBe('newtopic');
  });

  test('does not render when selection is below the minimum length', () => {
    render(<Harness text="too short" onDrilldown={jest.fn()} />);
    selectParagraph();
    expect(screen.queryByRole('button', { name: /sub-topic/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /new topic/i })).toBeNull();
  });

  test('does not render when disabled even with a valid selection', () => {
    const Disabled: React.FC = () => {
      const ref = useRef<HTMLDivElement>(null);
      return (
        <div ref={ref}>
          <p data-testid="paragraph">A long enough sentence to clear the threshold.</p>
          <DigDeeperPopover containerRef={ref} onDrilldown={jest.fn()} disabled />
        </div>
      );
    };
    render(<Disabled />);
    selectParagraph();
    expect(screen.queryByRole('button', { name: /sub-topic/i })).toBeNull();
  });
});
