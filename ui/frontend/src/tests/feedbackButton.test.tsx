import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

// html2canvas relies on browser APIs (canvas, document.fonts) that jsdom only
// partially implements. Replace it with a deterministic stub.
jest.mock('html2canvas', () => ({
  __esModule: true,
  default: jest.fn(() =>
    Promise.resolve({
      toDataURL: () => 'data:image/jpeg;base64,STUB',
    }),
  ),
}));

// Stub axios so the modal's submit doesn't try to hit the network.
jest.mock('axios', () => ({
  __esModule: true,
  default: {
    post: jest.fn(() => Promise.resolve({ data: {} })),
    isAxiosError: jest.fn(() => false),
  },
}));

import FeedbackButton from '../components/feedback/FeedbackButton';

describe('FeedbackButton', () => {
  test('renders a feedback trigger button', () => {
    render(<FeedbackButton />);
    expect(screen.getByRole('button', { name: /send feedback/i })).toBeInTheDocument();
  });

  test('clicking the trigger opens the modal with the current URL', async () => {
    render(<FeedbackButton />);
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }));
    expect(await screen.findByRole('heading', { name: /send feedback/i })).toBeInTheDocument();
    expect(screen.getByText(/Page:/)).toBeInTheDocument();
  });

  test('cancel button closes the modal', async () => {
    render(<FeedbackButton />);
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }));
    await screen.findByRole('heading', { name: /send feedback/i });
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.queryByRole('heading', { name: /send feedback/i })).not.toBeInTheDocument();
  });

  test('submit is disabled until the user types a comment', async () => {
    render(<FeedbackButton />);
    fireEvent.click(screen.getByRole('button', { name: /send feedback/i }));
    await screen.findByRole('heading', { name: /send feedback/i });
    const submit = screen.getByRole('button', { name: /^submit$/i });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/Tell us what went well/i), {
      target: { value: 'The export button is hidden.' },
    });
    expect(submit).not.toBeDisabled();
  });
});
