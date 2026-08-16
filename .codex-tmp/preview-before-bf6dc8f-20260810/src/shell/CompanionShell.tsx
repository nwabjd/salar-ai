import { Radio } from "lucide-react";
import {
  type ReactNode,
  useEffect,
  useState,
} from "react";

import { ContextDrawer } from "./ContextDrawer";
import { type Destination, PrimaryNav } from "./PrimaryNav";

interface CompanionShellProps {
  children: ReactNode;
  activeDestination?: Destination;
  onDestinationChange?: (destination: Destination) => void;
  onStartLive?: () => void;
  context?: ReactNode;
  contextTitle?: string;
  contextOpen?: boolean;
  onContextClose?: () => void;
}

function isMobileViewport() {
  return typeof window !== "undefined" && window.innerWidth <= 820;
}

export function CompanionShell({
  children,
  activeDestination: controlledDestination,
  onDestinationChange,
  onStartLive,
  context,
  contextTitle,
  contextOpen = true,
  onContextClose,
}: CompanionShellProps) {
  const [internalDestination, setInternalDestination] =
    useState<Destination>("briefing");
  const [mobile, setMobile] = useState(isMobileViewport);
  const activeDestination = controlledDestination ?? internalDestination;

  useEffect(() => {
    const updateViewport = () => setMobile(isMobileViewport());
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  function changeDestination(destination: Destination) {
    if (controlledDestination === undefined) {
      setInternalDestination(destination);
    }
    onDestinationChange?.(destination);
  }

  return (
    <>
      <a className="skip-link" href="#conversation">
        Skip to conversation
      </a>

      <div className="companion-shell">
        <PrimaryNav
          variant="rail"
          activeDestination={activeDestination}
          onDestinationChange={changeDestination}
          hidden={mobile}
        />

        <main
          className="companion-shell__canvas"
          id="conversation"
          aria-label="SALAR companion"
          tabIndex={-1}
        >
          <header className="companion-shell__mobile-header">
            <div className="mobile-identity" aria-label="SALAR companion">
              <span className="mobile-identity__mark" aria-hidden="true">
                S
              </span>
              <span>SALAR</span>
            </div>
            <span className="primary-nav__connection">
              <span className="connection-dot" aria-hidden="true" />
              Private
            </span>
          </header>

          <div className="companion-shell__content">
            <div className="companion-shell__kicker">
              SALAR is here and listening
            </div>
            {children}
          </div>
        </main>

        {context ? (
          <ContextDrawer
            open={contextOpen}
            title={contextTitle}
            onClose={onContextClose}
          >
            {context}
          </ContextDrawer>
        ) : null}

        <button
          className="live-action"
          type="button"
          aria-label="Start Live conversation"
          onClick={onStartLive}
        >
          <span className="live-action__orb" aria-hidden="true">
            <Radio size={17} />
          </span>
          <span>Talk to SALAR</span>
        </button>

        <PrimaryNav
          variant="dock"
          activeDestination={activeDestination}
          onDestinationChange={changeDestination}
          hidden={!mobile}
        />
      </div>
    </>
  );
}
