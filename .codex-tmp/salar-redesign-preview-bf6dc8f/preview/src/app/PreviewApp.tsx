import { useMemo, useState } from "react";

import { AccessGate } from "../access/AccessGate";
import { loadPreviewConfig } from "../access/previewSession";
import type { SalarGateway } from "../contracts/gateway";
import { FixtureGateway } from "../data/FixtureGateway";
import { LiveGateway } from "../data/LiveGateway";
import { Briefing } from "../features/briefing/Briefing";
import { ConversationWorkspace } from "../features/conversations/ConversationWorkspace";
import { CompanionShell } from "../shell/CompanionShell";
import type { Destination } from "../shell/PrimaryNav";

interface PreviewAppProps {
  gateway?: SalarGateway;
}

export function PreviewApp({ gateway: providedGateway }: PreviewAppProps) {
  const [destination, setDestination] = useState<Destination>("briefing");
  const [liveNotice, setLiveNotice] = useState("");
  const config = useMemo(loadPreviewConfig, []);
  const gateway = useMemo(() => {
    if (providedGateway) {
      return providedGateway;
    }
    return config.mode === "live"
      ? new LiveGateway()
      : new FixtureGateway();
  }, [config.mode, providedGateway]);
  const requestLive = () => {
    setLiveNotice(
      "Live voice mode is not included in this preview build yet. Typed conversation remains available.",
    );
  };

  return (
    <AccessGate
      gateway={gateway}
      initialState={
        !providedGateway && config.mode === "fixture" ? "paired" : undefined
      }
    >
      <CompanionShell
        activeDestination={destination}
        onDestinationChange={setDestination}
        onStartLive={requestLive}
      >
        {liveNotice ? (
          <p className="preview-live-notice" role="status" aria-live="polite">
            {liveNotice}
          </p>
        ) : null}
        {destination === "conversations" ? (
          <ConversationWorkspace gateway={gateway} onStartLive={requestLive} />
        ) : (
          <Briefing gateway={gateway} />
        )}
      </CompanionShell>
    </AccessGate>
  );
}
