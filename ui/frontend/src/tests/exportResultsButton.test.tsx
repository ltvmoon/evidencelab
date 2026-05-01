import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { ExportResultsButton } from '../components/ExportResultsButton';
import type { SearchResult } from '../types/api';

const mockSaveAs = jest.fn();
jest.mock('file-saver', () => ({
  __esModule: true,
  saveAs: (...args: unknown[]) => mockSaveAs(...args),
}));

// The docx generation itself is exercised by exportResultsToDocx.test.ts —
// here we only care about the button's UX, so the util is mocked.
const mockExport = jest.fn();
const mockBuildName = jest.fn();
jest.mock('../utils/exportResultsToDocx', () => ({
  __esModule: true,
  exportResultsToDocxBlob: (...args: unknown[]) => mockExport(...args),
  buildExportFilename: (...args: unknown[]) => mockBuildName(...args),
}));

const makeResult = (overrides: Partial<SearchResult> = {}): SearchResult =>
  ({
    chunk_id: 'c1',
    doc_id: 'd1',
    text: 'sample excerpt',
    page_num: 1,
    headings: [],
    score: 0.5,
    title: 'Sample',
    ...overrides,
  } as SearchResult);

describe('ExportResultsButton', () => {
  beforeEach(() => {
    mockSaveAs.mockReset();
    mockExport.mockReset();
    mockBuildName.mockReset();
    mockBuildName.mockReturnValue('evidencelab-search-test.docx');
  });

  test('renders_when_idle_then_shows_export_label', () => {
    render(<ExportResultsButton results={[makeResult()]} query="climate" />);
    const btn = screen.getByRole('button', { name: /export search results to word/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent(/export to word/i);
    expect(btn).not.toBeDisabled();
  });

  test('disabled_when_results_empty_then_shows_run_search_hint', () => {
    render(<ExportResultsButton results={[]} query="climate" />);
    const btn = screen.getByRole('button', { name: /export search results to word/i });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('title', 'Run a search first');
  });

  test('click_when_idle_then_invokes_export_and_saveAs', async () => {
    const fakeBlob = new Blob(['x'], { type: 'application/octet-stream' });
    mockExport.mockResolvedValue(fakeBlob);
    render(
      <ExportResultsButton
        results={[makeResult()]}
        query="climate"
        aiSummary="## summary"
        dataSource="uneg"
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /export search results to word/i }));
    await waitFor(() => expect(mockExport).toHaveBeenCalledTimes(1));
    const callArg = mockExport.mock.calls[0][0];
    expect(callArg).toMatchObject({
      query: 'climate',
      aiSummary: '## summary',
      dataSource: 'uneg',
    });
    expect(Array.isArray(callArg.results)).toBe(true);
    await waitFor(() =>
      expect(mockSaveAs).toHaveBeenCalledWith(fakeBlob, 'evidencelab-search-test.docx'),
    );
    expect(mockBuildName).toHaveBeenCalledWith('climate', expect.any(Date));
  });

  test('click_while_pending_then_shows_busy_label_and_does_not_double_fire', async () => {
    let resolveExport!: (b: Blob) => void;
    mockExport.mockImplementation(
      () => new Promise<Blob>((resolve) => { resolveExport = resolve; }),
    );
    render(<ExportResultsButton results={[makeResult()]} query="climate" />);
    const btn = screen.getByRole('button', { name: /export search results to word/i });

    fireEvent.click(btn);
    await waitFor(() => expect(btn).toBeDisabled());
    expect(btn).toHaveTextContent(/preparing word document/i);

    fireEvent.click(btn); // second click while busy
    expect(mockExport).toHaveBeenCalledTimes(1); // still only one in-flight call

    await act(async () => {
      resolveExport(new Blob(['x']));
    });
    await waitFor(() => expect(btn).not.toBeDisabled());
  });

  test('export_throws_then_shows_error_alert_and_re_enables_button', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    mockExport.mockRejectedValue(new Error('boom'));
    render(<ExportResultsButton results={[makeResult()]} query="climate" />);
    fireEvent.click(screen.getByRole('button', { name: /export search results to word/i }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/could not export.*boom/i);
    expect(screen.getByRole('button', { name: /export search results to word/i })).not.toBeDisabled();
    expect(mockSaveAs).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  test('forwards_classname_to_wrapper', () => {
    const { container } = render(
      <ExportResultsButton results={[makeResult()]} query="q" className="my-wrap" />,
    );
    expect(container.querySelector('.my-wrap')).toBeInTheDocument();
  });
});
