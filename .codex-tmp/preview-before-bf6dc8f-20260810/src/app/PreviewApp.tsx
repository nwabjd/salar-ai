import { useCallback, useMemo, useState } from "react";

import { AccessGate } from "../access/AccessGate";
import { loadPreviewConfig } from "../access/previewSession";
import type { SalarGateway } from "../contracts/gateway";
import { FixtureGateway } from "../data/FixtureGateway";
import { LiveGateway } from "../data/LiveGateway";
import { Briefing } from "../features/briefing/Briefing";
import { ConversationPanel } from "../features/conversation/ConversationPanel";
import { CompanionShell } from "../shell/CompanionShell";

interface PreviewAppProps {
  gateway?: SalarGateway;
}

export function PreviewApp({ gateway: providedGateway }: PreviewAppProps) {
  const config = useMemo(loadPreviewConfig, []);
  const [liveOpen, setLiveOpen] = useState(false);
  const gateway = useMemo(() => {
    if (providedGateway) {
      return providedGateway;
    }
    return config.mode === "live"
      ? new LiveGateway()
      : new FixtureGateway();
  }, [config.mode, providedGateway]);

  const onStartLive = useCallback(() => setLiveOpen(true), []);
  const closeLive = useCallback(() => setLiveOpen(false), []);

  return (
    <AccessGate
      gateway={gateway}
      initialState={
        !providedGateway && config.mode === "fixture" ? "paired" : undefined
      }
    >
      <CompanionShell onStartLive={onStartLive}>
        <Briefing gateway={gateway} />
      </CompanionShell>
      {liveOpen ? (
        <ConversationPanel gateway={gateway} onClose={closeLive} />
      ) : null}
    </AccessGate>
  );
}
