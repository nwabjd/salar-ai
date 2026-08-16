import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { SalarGateway } from '../contracts/gateway';
import { AccessGate } from './AccessGate';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('AccessGate', () => {
  it('bypasses the gate when initialState is paired', () => {
    render(
      <AccessGate
        gateway={
          {
            getAccessState: vi.fn().mockResolvedValue('paired' as const),
          } as unknown as SalarGateway
        }
        initialState="paired"
      >
        <p>Your companion</p>
      </AccessGate>,
    );

    expect(screen.getByText('Your companion')).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { name: 'Bring SALAR closer' }),
    ).not.toBeInTheDocument();
  });

  it('shows a status message when access is unavailable', () => {
    render(
      <AccessGate
        gateway={
          { getAccessState: vi.fn() } as unknown as SalarGateway
        }
      >
        <p>Never rendered</p>
      </AccessGate>,
    );

    expect(
      screen.getByRole('heading', { name: 'Bring SALAR closer' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Never rendered')).not.toBeInTheDocument();
  });

  it('reads the access state for persisted gate check', async () => {
    const gateway = {
      getAccessState: vi.fn().mockResolvedValue('paired' as const),
    } as unknown as SalarGateway;

    render(
      <AccessGate gateway={gateway} initialState="paired">
        <p>Your companion</p>
      </AccessGate>,
    );

    expect(await screen.findByText('Your companion')).toBeInTheDocument();
  });
});
