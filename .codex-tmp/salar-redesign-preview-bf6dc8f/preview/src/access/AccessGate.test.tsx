import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SalarGateway } from "../contracts/gateway";
import type {
  AccessState,
  LoginCredentials,
  PairingCredentials,
} from "../contracts/models";
import { AccessGate } from "./AccessGate";
import {
  clearPreviewSession,
  loadPreviewConfig,
  savePreviewConfig,
} from "./previewSession";

interface GatewayHarness {
  gateway: SalarGateway;
  getAccessState: ReturnType<typeof vi.fn<() => Promise<AccessState>>>;
  pair: ReturnType<
    typeof vi.fn<(credentials: PairingCredentials) => Promise<AccessState>>
  >;
  login: ReturnType<
    typeof vi.fn<(credentials: LoginCredentials) => Promise<AccessState>>
  >;
}

function createGateway(
  initialState: AccessState,
  overrides: {
    getAccessState?: () => Promise<AccessState>;
    pair?: (credentials: PairingCredentials) => Promise<AccessState>;
    login?: (credentials: LoginCredentials) => Promise<AccessState>;
  } = {},
): GatewayHarness {
  const getAccessState = vi.fn(
    overrides.getAccessState ?? (async () => initialState),
  );
  const pair = vi.fn(
    overrides.pair ?? (async () => "paired" as const),
  );
  const login = vi.fn(
    overrides.login ?? (async () => "paired" as const),
  );

  return {
    gateway: { getAccessState, pair, login } as unknown as SalarGateway,
    getAccessState,
    pair,
    login,
  };
}

describe("AccessGate", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("invites an unpaired live preview to bring SALAR closer", async () => {
    const { gateway } = createGateway("unpaired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );

    expect(
      await screen.findByRole("heading", { name: "Bring SALAR closer" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Backend URL")).toBeInTheDocument();
    expect(screen.getByLabelText("Six-digit pairing code")).toHaveAttribute(
      "inputmode",
      "numeric",
    );
  });

  it("renders connected content after the gateway validates the session", async () => {
    const { gateway } = createGateway("paired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );

    expect(await screen.findByText("Connected app")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Bring SALAR closer" }),
    ).not.toBeInTheDocument();
  });

  it("validates the six-digit code inline before calling the gateway", async () => {
    const { gateway, pair } = createGateway("unpaired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });

    fireEvent.change(screen.getByLabelText("Six-digit pairing code"), {
      target: { value: "123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect securely" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter the six-digit code shown by SALAR.",
    );
    expect(pair).not.toHaveBeenCalled();
  });

  it("pairs through the gateway and stores only preview-scoped configuration", async () => {
    const { gateway, pair } = createGateway("unpaired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });

    fireEvent.change(screen.getByLabelText("Backend URL"), {
      target: { value: "https://salar.example.test/" },
    });
    fireEvent.change(screen.getByLabelText("Six-digit pairing code"), {
      target: { value: "246810" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect securely" }));

    expect(await screen.findByText("Connected app")).toBeInTheDocument();
    expect(pair).toHaveBeenCalledWith({
      code: "246810",
      name: "SALAR Preview",
      platform: "web-preview",
    });
    expect(sessionStorage.getItem("salar-preview.apiUrl")).toBe(
      "https://salar.example.test",
    );
    expect(localStorage).toHaveLength(0);
  });

  it("shows a submitting state and reports a rejected pairing inline", async () => {
    let rejectPair: (reason: Error) => void = () => undefined;
    const pendingPair = new Promise<AccessState>((_resolve, reject) => {
      rejectPair = reject;
    });
    const { gateway, pair } = createGateway("unpaired", {
      pair: async () => pendingPair,
    });

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });

    fireEvent.change(screen.getByLabelText("Six-digit pairing code"), {
      target: { value: "246810" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect securely" }));

    expect(
      await screen.findByRole("button", { name: "Connecting…" }),
    ).toBeDisabled();
    expect(pair).toHaveBeenCalledOnce();

    await act(async () => {
      rejectPair(new Error("That code has already been used."));
      await pendingPair.catch(() => undefined);
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That code has already been used.",
    );
    expect(
      screen.getByRole("button", { name: "Connect securely" }),
    ).toBeEnabled();
  });

  it("clears the single-use pairing code after a successful pairing", async () => {
    const pairedGateway = createGateway("unpaired");
    const nextGateway = createGateway("unpaired");
    const view = render(
      <AccessGate gateway={pairedGateway.gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });

    fireEvent.change(screen.getByLabelText("Six-digit pairing code"), {
      target: { value: "246810" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect securely" }));
    expect(await screen.findByText("Connected app")).toBeInTheDocument();

    view.rerender(
      <AccessGate gateway={nextGateway.gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );

    expect(
      await screen.findByRole("heading", { name: "Bring SALAR closer" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Six-digit pairing code")).toHaveValue("");
  });

  it("clears the recovery password after login settles", async () => {
    const { gateway } = createGateway("unpaired", {
      login: async () => {
        throw new Error("Recovery login was not accepted.");
      },
    });

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });
    fireEvent.click(
      screen.getByRole("button", { name: "Use recovery login" }),
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Recovery login was not accepted.",
    );
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("rejects a non-HTTP pairing backend before persisting or calling the gateway", async () => {
    const { gateway, pair } = createGateway("unpaired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });
    const urlInput = screen.getByLabelText("Backend URL");
    fireEvent.change(urlInput, {
      target: { value: "ftp://salar.example.test" },
    });
    fireEvent.change(screen.getByLabelText("Six-digit pairing code"), {
      target: { value: "246810" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Connect securely" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a valid HTTP or HTTPS backend URL.",
    );
    expect(urlInput).toHaveFocus();
    expect(pair).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("salar-preview.apiUrl")).toBeNull();
  });

  it("rejects a malformed recovery backend before sending credentials", async () => {
    const { gateway, login } = createGateway("unpaired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });
    fireEvent.change(screen.getByLabelText("Backend URL"), {
      target: { value: "not a backend URL" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Use recovery login" }),
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a valid HTTP or HTTPS backend URL.",
    );
    expect(screen.getByLabelText("Backend URL")).toHaveFocus();
    expect(login).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("salar-preview.apiUrl")).toBeNull();
  });

  it("explains when a saved session has expired", async () => {
    const { gateway } = createGateway("expired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your preview session expired.",
    );
    expect(
      screen.getByRole("heading", { name: "Bring SALAR closer" }),
    ).toBeInTheDocument();
  });

  it("retries an offline access check", async () => {
    const getAccessState = vi
      .fn<() => Promise<AccessState>>()
      .mockResolvedValueOnce("offline")
      .mockResolvedValueOnce("paired");
    const { gateway } = createGateway("offline", { getAccessState });

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );

    expect(await screen.findByText("SALAR is out of reach right now.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Connected app")).toBeInTheDocument();
    expect(getAccessState).toHaveBeenCalledTimes(2);
  });

  it("keeps recovery login behind a disclosure and calls login", async () => {
    const { gateway, login } = createGateway("unpaired");

    render(
      <AccessGate gateway={gateway}>
        <p>Connected app</p>
      </AccessGate>,
    );
    await screen.findByRole("heading", { name: "Bring SALAR closer" });

    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Use recovery login" }),
    );
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "person@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(login).toHaveBeenCalledWith({
        email: "person@example.test",
        password: "secret",
      }),
    );
    expect(await screen.findByText("Connected app")).toBeInTheDocument();
  });
});

describe("previewSession", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("normalizes config and clears only the preview session token", () => {
    sessionStorage.setItem("salar_session", "production-token");
    savePreviewConfig({
      apiUrl: "https://salar.example.test///",
      mode: "live",
    });
    sessionStorage.setItem("salar-preview.session", "preview-token");

    expect(loadPreviewConfig()).toEqual({
      apiUrl: "https://salar.example.test",
      mode: "live",
    });

    clearPreviewSession();

    expect(sessionStorage.getItem("salar-preview.session")).toBeNull();
    expect(sessionStorage.getItem("salar_session")).toBe("production-token");
  });
});
