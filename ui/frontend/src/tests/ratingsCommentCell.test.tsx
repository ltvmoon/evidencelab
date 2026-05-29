import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import { CommentCell } from '../components/admin/RatingsManager';

const renderCell = (comment: string | null) =>
  render(
    <table><tbody><tr><CommentCell comment={comment} /></tr></tbody></table>,
  );

describe('CommentCell', () => {
  test('renders an em-dash when there is no comment', () => {
    renderCell(null);
    expect(screen.getByText('-')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /see (more|full comment)/i })).toBeNull();
  });

  test('renders a short comment without a See more toggle', () => {
    renderCell('Short feedback');
    expect(screen.getByText('Short feedback')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /see more|see full comment/i })).toBeNull();
  });

  test('truncates long comments and exposes a "See more" toggle', () => {
    const long = 'A long comment about the AI summary that goes well over the threshold. '.repeat(5);
    renderCell(long);
    // Truncated body shouldn't contain the full text yet
    expect(screen.queryByText(long)).toBeNull();
    // ellipsis character is present in the truncated body
    expect(screen.getByText(/…/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /see full comment/i })).toBeInTheDocument();
  });

  test('clicking "See more" expands to full comment with "Show less" toggle', () => {
    const long = 'A long comment about the AI summary that goes well over the threshold. '.repeat(5);
    renderCell(long);
    fireEvent.click(screen.getByRole('button', { name: /see full comment/i }));
    // The cell's textContent should now contain the full comment, and the
    // ellipsis from the truncated view should be gone.
    const cell = screen.getByRole('button', { name: /show less of this comment/i }).closest('td');
    expect(cell?.textContent).toContain(long.trim());
    expect(cell?.textContent).not.toContain('…');
  });

  test('clicking "Show less" collapses back to the truncated view', () => {
    const long = 'A long comment about the AI summary that goes well over the threshold. '.repeat(5);
    renderCell(long);
    fireEvent.click(screen.getByRole('button', { name: /see full comment/i }));
    fireEvent.click(screen.getByRole('button', { name: /show less of this comment/i }));
    expect(screen.getByRole('button', { name: /see full comment/i })).toBeInTheDocument();
    expect(screen.getByText(/…/)).toBeInTheDocument();
  });

  test('toggle clicks do not bubble up (so the row does not also expand)', () => {
    const onRowClick = jest.fn();
    render(
      <table><tbody>
        <tr onClick={onRowClick}>
          <CommentCell comment={'A long comment about the AI summary that goes well over the threshold. '.repeat(5)} />
        </tr>
      </tbody></table>,
    );
    fireEvent.click(screen.getByRole('button', { name: /see full comment/i }));
    expect(onRowClick).not.toHaveBeenCalled();
  });
});
