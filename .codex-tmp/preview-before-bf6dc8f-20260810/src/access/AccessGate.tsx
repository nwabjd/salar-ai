import { type ReactNode, useEffect, useState } from 'react';

import type { AccessState } from '../contracts/models';
import type { SalarGateway } from '../contracts/gateway';

interface AccessGateProps {
  gateway: SalarGateway;
  initialState?: AccessState;
  children: ReactNode;
}

export function AccessGate({
  gateway,
  initialState,
  children,
}: AccessGateProps) {
  const [state, setState] = useState<AccessState>(
    initialState ?? 'unpaired',
  );

  useEffect(() => {
    let active = true;
    if (state === 'unpaired' || state === 'checking') {
      return;
    }
    gateway.getAccessState().then((result) => {
      if (active) {
        setState(result);
      }
    });
    return () => {
      active = false;
    };
  }, [gateway, state]);

  useEffect(() => {
    if (initialState && state === 'unpaired') {
      setState(initialState);
    }
  }, [initialState, state]);

  if (state === 'paired') {
    return <>{children}</>;
  }

  return (
    <section className="access-gate" aria-label="Access gate">
      <header className="access-gate__header">
        <span className="access-gate__mark" aria-hidden="true">
          S
        </span>
        <h1 className="access-gate__title">Bring SALAR closer</h1>
      </header>
      <p className="access-gate__description">
        {state === 'checking'
          ? 'Verifying your connection…'
          : state === 'offline'
            ? 'SALAR cannot be reached right now. Check your connection and try again.'
            : state === 'expired'
              ? 'Your session has expired. Please log in again from the main app.'
              : 'Use the main SALAR app to pair this preview.'}
      </p>
    </section>
  );
}
