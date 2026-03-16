import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';

// Mock config
jest.mock('../config', () => ({
  __esModule: true,
  default: '/api',
}));

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;
if (!mockedAxios.delete) {
  (mockedAxios as any).delete = jest.fn();
}

import ApiKeyManager from '../components/admin/ApiKeyManager';

const mockKeys = [
  {
    id: 'key-1',
    label: 'Production pipeline',
    key_prefix: 'el_abc12ab',
    is_active: true,
    created_at: '2026-01-15T00:00:00Z',
    created_by_email: 'admin@test.com',
    last_used_at: null,
  },
  {
    id: 'key-2',
    label: 'Staging environment',
    key_prefix: 'el_xyz98yz',
    is_active: true,
    created_at: '2026-02-01T00:00:00Z',
    created_by_email: null,
    last_used_at: '2026-03-01T00:00:00Z',
  },
];

describe('ApiKeyManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAxios.get.mockResolvedValue({ data: mockKeys });
  });

  test('shows loading state initially', () => {
    mockedAxios.get.mockReturnValue(new Promise(() => {}));
    render(<ApiKeyManager />);
    expect(screen.getByText('Loading API keys...')).toBeInTheDocument();
  });

  test('renders key list after loading', async () => {
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Production pipeline')).toBeInTheDocument();
    });
    expect(screen.getByText('Staging environment')).toBeInTheDocument();
  });

  test('displays key prefixes', async () => {
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('el_abc12ab...')).toBeInTheDocument();
    });
    expect(screen.getByText('el_xyz98yz...')).toBeInTheDocument();
  });

  test('displays creator email or dash', async () => {
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('admin@test.com')).toBeInTheDocument();
    });
    expect(screen.getByText('-')).toBeInTheDocument();
  });

  test('shows empty state when no keys', async () => {
    mockedAxios.get.mockResolvedValue({ data: [] });
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('No API keys generated yet.')).toBeInTheDocument();
    });
  });

  test('shows error on fetch failure', async () => {
    mockedAxios.get.mockRejectedValue(new Error('Network error'));
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Failed to load API keys')).toBeInTheDocument();
    });
  });

  test('generate form requires label', async () => {
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Production pipeline')).toBeInTheDocument();
    });
    const input = screen.getByPlaceholderText('e.g. Production pipeline');
    expect(input).toBeRequired();
  });

  test('calls create API on form submit', async () => {
    const createdKey = {
      id: 'key-3',
      label: 'New key',
      key_prefix: 'el_new123n',
      is_active: true,
      created_at: '2026-03-16T00:00:00Z',
      created_by_email: 'admin@test.com',
      last_used_at: null,
      key: 'el_new123n-full-secret-key-value',
    };
    mockedAxios.post.mockResolvedValue({ data: createdKey });
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Production pipeline')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('e.g. Production pipeline');
    fireEvent.change(input, { target: { value: 'New key' } });
    fireEvent.click(screen.getByText('Generate Key'));

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith('/api/api-keys/', {
        label: 'New key',
      });
    });
  });

  test('shows generated key modal with copy warning', async () => {
    const createdKey = {
      id: 'key-3',
      label: 'New key',
      key_prefix: 'el_new123n',
      is_active: true,
      created_at: '2026-03-16T00:00:00Z',
      created_by_email: 'admin@test.com',
      last_used_at: null,
      key: 'el_new123n-full-secret-key-value',
    };
    mockedAxios.post.mockResolvedValue({ data: createdKey });
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Production pipeline')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('e.g. Production pipeline');
    fireEvent.change(input, { target: { value: 'New key' } });
    fireEvent.click(screen.getByText('Generate Key'));

    await waitFor(() => {
      expect(screen.getByText('API Key Generated')).toBeInTheDocument();
    });
    expect(
      screen.getByText('Copy this key now. It will not be shown again.')
    ).toBeInTheDocument();
    expect(
      screen.getByText('el_new123n-full-secret-key-value')
    ).toBeInTheDocument();
    expect(screen.getByText('Copy')).toBeInTheDocument();
  });

  test('opens confirm modal on revoke click', async () => {
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Production pipeline')).toBeInTheDocument();
    });

    const revokeButtons = screen.getAllByText('Revoke');
    fireEvent.click(revokeButtons[0]);

    expect(screen.getByText('Revoke API Key')).toBeInTheDocument();
    expect(
      screen.getByText(
        /Are you sure you want to revoke the API key "Production pipeline"/
      )
    ).toBeInTheDocument();
  });

  test('calls delete API on revoke confirm', async () => {
    mockedAxios.delete.mockResolvedValue({});
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Production pipeline')).toBeInTheDocument();
    });

    const revokeButtons = screen.getAllByText('Revoke');
    fireEvent.click(revokeButtons[0]);

    const confirmBtn = document.querySelector(
      '.confirm-modal-actions .btn-danger'
    ) as HTMLElement;
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockedAxios.delete).toHaveBeenCalledWith('/api/api-keys/key-1');
    });
  });

  test('dismisses error on close click', async () => {
    mockedAxios.get.mockRejectedValue(new Error('fail'));
    render(<ApiKeyManager />);
    await waitFor(() => {
      expect(screen.getByText('Failed to load API keys')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('×'));
    expect(
      screen.queryByText('Failed to load API keys')
    ).not.toBeInTheDocument();
  });
});
