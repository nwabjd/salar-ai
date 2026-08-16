import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PreviewApp } from './PreviewApp';
import { FixtureGateway } from '../data/FixtureGateway';

describe('PreviewApp', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    sessionStorage.clear();
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

  it('keeps Briefing as the default and opens Conversations from primary navigation', async () => {
    render(<PreviewApp gateway={new FixtureGateway()} />);

    expect(
      await screen.findByRole('heading', { name: /Good (morning|afternoon|evening)\./ }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Conversations' }));
    expect(
      await screen.findByRole('heading', { name: 'Conversations', level: 1 }),
    ).toBeInTheDocument();
  });

  it('exposes a truthful accessible fallback when Live is requested', async () => {
    render(<PreviewApp gateway={new FixtureGateway()} />);
    fireEvent.click(
      await screen.findByRole('button', { name: 'Start Live conversation' }),
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'Live voice mode is not included in this preview build yet.',
    );
  });
});
