import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApprovalDialog, type ApprovalRequest } from "./ApprovalDialog";

const deleteRequest: ApprovalRequest = {
  title: "Delete source",
  actionLabel: "delete",
  target: "Launch brief",
  scope: "This source only",
  effect: "Permanently removes it from SALAR’s library.",
};

afterEach(cleanup);

describe("ApprovalDialog", () => {
  it("does not execute a consequential action before confirmation", () => {
    const execute = vi.fn();
    render(<ApprovalDialog request={deleteRequest} onConfirm={execute} onCancel={() => undefined} />);
    expect(execute).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(execute).toHaveBeenCalledOnce();
  });

  it("shows target, scope, and effect and cancels with focus restoration", async () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();
    const cancel = vi.fn();
    const view = render(<ApprovalDialog request={deleteRequest} onConfirm={() => undefined} onCancel={cancel} />);

    expect(screen.getByRole("dialog", { name: "Delete source" })).toHaveTextContent("Launch brief");
    expect(screen.getByRole("dialog")).toHaveTextContent("This source only");
    expect(screen.getByRole("dialog")).toHaveTextContent("Permanently removes");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(cancel).toHaveBeenCalledOnce();
    view.unmount();
    await waitFor(() => expect(opener).toHaveFocus());
    opener.remove();
  });

  it("prevents duplicate confirmation while pending", async () => {
    let resolve: (() => void) | undefined;
    const execute = vi.fn(() => new Promise<void>((done) => { resolve = done; }));
    render(<ApprovalDialog request={deleteRequest} onConfirm={execute} onCancel={() => undefined} />);
    const confirm = screen.getByRole("button", { name: "Confirm delete" });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    expect(execute).toHaveBeenCalledOnce();
    expect(confirm).toBeDisabled();
    resolve?.();
  });

  it("treats a failed request as uncertain and requires a status refresh", async () => {
    const execute = vi.fn().mockRejectedValue(new Error("offline"));
    const refresh = vi.fn().mockResolvedValue(undefined);
    render(
      <ApprovalDialog
        request={deleteRequest}
        onConfirm={execute}
        onCancel={() => undefined}
        onRefreshStatus={refresh}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("couldn’t verify the outcome");
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeDisabled();
    const refreshButton = screen.getByRole("button", { name: "Refresh status before retrying" });
    await waitFor(() => expect(refreshButton).toHaveFocus());
    fireEvent.click(refreshButton);
    await waitFor(() => expect(screen.getByRole("button", { name: "Confirm delete" })).toBeEnabled());
    expect(refresh).toHaveBeenCalledOnce();
  });

  it("keeps a backend-declared failure refresh-gated", async () => {
    render(
      <ApprovalDialog
        request={deleteRequest}
        onConfirm={() => ({
          ok: false,
          message: "The source may already be in use.",
        })}
        onCancel={() => undefined}
        onRefreshStatus={() => undefined}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The source may already be in use. Refresh status before retrying.",
    );
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeDisabled();
  });

  it("keeps confirmation blocked if status refresh fails", async () => {
    render(
      <ApprovalDialog
        request={deleteRequest}
        onConfirm={() => Promise.reject(new Error("offline"))}
        onCancel={() => undefined}
        onRefreshStatus={() => Promise.reject(new Error("still offline"))}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    fireEvent.click(await screen.findByRole("button", { name: "Refresh status before retrying" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Status is still unavailable");
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeDisabled();
  });

  it("inerts and aria-isolates background content, then restores prior attributes", () => {
    function Harness({ open }: { open: boolean }) {
      return (
        <main>
          <button aria-hidden="false">Background action</button>
          {open ? (
            <ApprovalDialog
              request={deleteRequest}
              onConfirm={() => undefined}
              onCancel={() => undefined}
            />
          ) : null}
        </main>
      );
    }
    const view = render(<Harness open />);
    const background = screen.getByText("Background action", { selector: "button" });
    expect(background).toHaveAttribute("inert");
    expect(background).toHaveAttribute("aria-hidden", "true");

    view.rerender(<Harness open={false} />);
    expect(background).not.toHaveAttribute("inert");
    expect(background).toHaveAttribute("aria-hidden", "false");
  });
});
