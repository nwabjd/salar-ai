import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type { SalarGateway } from "../contracts/gateway";
import type { AccessState } from "../contracts/models";
import {
  clearPreviewSession,
  loadPreviewConfig,
  normalizePreviewApiUrl,
  savePreviewConfig,
} from "./previewSession";

interface AccessGateProps {
  gateway: SalarGateway;
  children: ReactNode;
  initialState?: AccessState;
}

const ACCESS_MESSAGES: Partial<Record<AccessState, string>> = {
  expired: "Your preview session expired. Pair again or use recovery login.",
  offline: "SALAR is out of reach right now.",
};

function errorStatus(error: unknown): number | undefined {
  if (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    typeof error.status === "number"
  ) {
    return error.status;
  }
  return undefined;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function AccessGate({
  gateway,
  children,
  initialState = "checking",
}: AccessGateProps) {
  const initialConfig = loadPreviewConfig();
  const [accessState, setAccessState] = useState<AccessState>(initialState);
  const [apiUrl, setApiUrl] = useState(initialConfig.apiUrl);
  const [pairingCode, setPairingCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showRecovery, setShowRecovery] = useState(false);
  const apiUrlRef = useRef<HTMLInputElement>(null);
  const pairingCodeRef = useRef<HTMLInputElement>(null);

  const applyAccessState = useCallback((nextState: AccessState) => {
    if (nextState === "expired") {
      clearPreviewSession();
    }
    setAccessState(nextState);
    setMessage(ACCESS_MESSAGES[nextState] ?? "");
  }, []);

  const checkAccess = useCallback(async () => {
    setAccessState("checking");
    setMessage("");
    try {
      applyAccessState(await gateway.getAccessState());
    } catch (error) {
      applyAccessState(errorStatus(error) === 401 ? "expired" : "offline");
    }
  }, [applyAccessState, gateway]);

  useEffect(() => {
    let active = true;
    void gateway
      .getAccessState()
      .then((state) => {
        if (active) applyAccessState(state);
      })
      .catch((error: unknown) => {
        if (active) {
          applyAccessState(
            errorStatus(error) === 401 || errorStatus(error) === 403
              ? "expired"
              : "offline",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [applyAccessState, gateway]);

  function persistLiveConfig(): boolean {
    try {
      const normalizedApiUrl = normalizePreviewApiUrl(apiUrl);
      setApiUrl(normalizedApiUrl);
      savePreviewConfig({ apiUrl: normalizedApiUrl, mode: "live" });
      return true;
    } catch (error) {
      setMessage(
        errorMessage(error, "Enter a valid HTTP or HTTPS backend URL."),
      );
      apiUrlRef.current?.focus();
      return false;
    }
  }

  async function handlePair(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!/^\d{6}$/.test(pairingCode)) {
      setMessage("Enter the six-digit code shown by SALAR.");
      pairingCodeRef.current?.focus();
      return;
    }
    if (!persistLiveConfig()) {
      return;
    }

    setIsSubmitting(true);
    setMessage("");
    try {
      const nextState = await gateway.pair({
        code: pairingCode,
        name: "SALAR Preview",
        platform: "web-preview",
      });
      if (nextState === "paired") {
        setPairingCode("");
      }
      applyAccessState(nextState);
    } catch (error) {
      const status = errorStatus(error);
      if (status === 401 || status === 403) {
        applyAccessState("expired");
      } else if (status === 0) {
        applyAccessState("offline");
      } else {
        setMessage(errorMessage(error, "That pairing code was not accepted."));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      setMessage("Enter both your email and password.");
      return;
    }
    if (!persistLiveConfig()) {
      setPassword("");
      return;
    }

    setIsSubmitting(true);
    setMessage("");
    try {
      applyAccessState(await gateway.login({ email: email.trim(), password }));
    } catch (error) {
      const status = errorStatus(error);
      if (status === 0) {
        applyAccessState("offline");
      } else {
        setMessage(errorMessage(error, "Recovery login was not accepted."));
      }
    } finally {
      setPassword("");
      setIsSubmitting(false);
    }
  }

  if (accessState === "paired") {
    return <>{children}</>;
  }

  if (accessState === "checking") {
    return (
      <section aria-live="polite" aria-busy="true">
        <p>Checking your private connection…</p>
      </section>
    );
  }

  return (
    <section aria-labelledby="access-heading">
      <p>SALAR companion preview</p>
      <h1 id="access-heading">Bring SALAR closer</h1>
      <p>
        Connect this preview to your SALAR backend. Your session stays in this
        browser tab.
      </p>

      {message ? (
        <p id="access-message" role="alert">
          {message}
        </p>
      ) : null}

      {accessState === "offline" ? (
        <button type="button" onClick={() => void checkAccess()}>
          Try again
        </button>
      ) : null}

      <form noValidate onSubmit={(event) => void handlePair(event)}>
        <label htmlFor="preview-api-url">Backend URL</label>
        <input
          ref={apiUrlRef}
          id="preview-api-url"
          name="apiUrl"
          type="url"
          value={apiUrl}
          onChange={(event) => setApiUrl(event.target.value)}
          autoComplete="url"
          required
          aria-invalid={
            message === "Enter a valid HTTP or HTTPS backend URL."
          }
          aria-describedby={
            message === "Enter a valid HTTP or HTTPS backend URL."
              ? "access-message"
              : undefined
          }
          disabled={isSubmitting}
        />

        <label htmlFor="preview-pairing-code">Six-digit pairing code</label>
        <input
          ref={pairingCodeRef}
          id="preview-pairing-code"
          name="pairingCode"
          type="text"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          autoComplete="one-time-code"
          value={pairingCode}
          onChange={(event) =>
            setPairingCode(event.target.value.replace(/\D/g, "").slice(0, 6))
          }
          aria-invalid={
            message === "Enter the six-digit code shown by SALAR."
          }
          aria-describedby={message ? "access-message" : undefined}
          disabled={isSubmitting}
        />

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Connecting…" : "Connect securely"}
        </button>
      </form>

      <button
        type="button"
        aria-expanded={showRecovery}
        aria-controls="recovery-login"
        onClick={() => setShowRecovery((visible) => !visible)}
        disabled={isSubmitting}
      >
        Use recovery login
      </button>

      {showRecovery ? (
        <form id="recovery-login" onSubmit={(event) => void handleLogin(event)}>
          <label htmlFor="preview-email">Email</label>
          <input
            id="preview-email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            disabled={isSubmitting}
          />

          <label htmlFor="preview-password">Password</label>
          <input
            id="preview-password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            disabled={isSubmitting}
          />

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      ) : null}
    </section>
  );
}
