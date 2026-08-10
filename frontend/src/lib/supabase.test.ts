import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanAuthFromUrl } from "./supabase";

function installWindow(href: string) {
  const replaceState = vi.fn();
  vi.stubGlobal("window", {
    location: { href },
    history: { state: { preserved: true }, replaceState },
  });
  return replaceState;
}

describe("Supabase auth redirect URL cleanup", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("removes auth tokens and transient errors from the query string", () => {
    const replaceState = installWindow(
      "https://salar.example/welcome?campaign=launch&access_token=secret&error=oauth_error&error_description=denied#features",
    );

    cleanAuthFromUrl();

    expect(replaceState).toHaveBeenCalledWith(
      { preserved: true },
      "",
      "https://salar.example/welcome?campaign=launch#features",
    );
  });

  it("removes auth tokens and transient errors from the hash while preserving unrelated hash parameters", () => {
    const replaceState = installWindow(
      "https://salar.example/welcome?campaign=launch#access_token=secret&refresh_token=refresh&error_description=expired&panel=pricing",
    );

    cleanAuthFromUrl();

    expect(replaceState).toHaveBeenCalledWith(
      { preserved: true },
      "",
      "https://salar.example/welcome?campaign=launch#panel=pricing",
    );
  });

  it("cleans query and hash auth artifacts in one history replacement", () => {
    const replaceState = installWindow(
      "https://salar.example/callback?code=pkce-code&next=app#provider_token=provider-secret&tab=home",
    );

    cleanAuthFromUrl();

    expect(replaceState).toHaveBeenCalledTimes(1);
    expect(replaceState).toHaveBeenCalledWith(
      { preserved: true },
      "",
      "https://salar.example/callback?next=app#tab=home",
    );
  });

  it("leaves ordinary query parameters and anchors untouched", () => {
    const replaceState = installWindow(
      "https://salar.example/pricing?type=annual&campaign=launch#plans",
    );

    cleanAuthFromUrl();

    expect(replaceState).not.toHaveBeenCalled();
  });
});
