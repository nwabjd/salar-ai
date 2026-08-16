import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PreviewApp } from './PreviewApp';

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 6, 29, 15, 30));
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
  sessionStorage.clear();
});

describe('PreviewApp', () => {
  it('renders the fixture Briefing without a live backend', async () => {
    render(<PreviewApp />);

    expect(
      await screen.findByRole('heading', { name: 'Good afternoon.' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Your personal briefing')).toBeInTheDocument();
  });

  it('exposes the SALAR companion main landmark', () => {
    render(<PreviewApp />);

    expect(
      screen.getByRole('main', { name: 'SALAR companion' }),
    ).toBeInTheDocument();
  });

  it('selects the live gateway from preview config and keeps content gated', async () => {
    sessionStorage.setItem('salar-preview.mode', 'live');
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);

    render(<PreviewApp />);

    expect(
      await screen.findByRole('heading', { name: 'Bring SALAR closer' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('main', { name: 'SALAR companion' }),
    ).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
