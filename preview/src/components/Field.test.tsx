import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Field } from "./Field";

afterEach(cleanup);

describe("Field", () => {
  it("merges existing descriptions and preserves aria-invalid without an error", () => {
    render(
      <>
        <p id="account-help">Use your private account.</p>
        <Field id="email" label="Email" hint="We never share this.">
          <input aria-describedby="account-help" aria-invalid="true" />
        </Field>
      </>,
    );

    const input = screen.getByRole("textbox", { name: "Email" });
    const hint = screen.getByText("We never share this.");

    expect(input).toHaveAttribute(
      "aria-describedby",
      `account-help ${hint.id}`,
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("adds the error description and marks the control invalid", () => {
    render(
      <Field id="name" label="Name" error="A name is required.">
        <input aria-describedby="profile-help" aria-invalid="false" />
      </Field>,
    );

    const input = screen.getByRole("textbox", { name: "Name" });
    const error = screen.getByText("A name is required.");

    expect(input).toHaveAttribute(
      "aria-describedby",
      `profile-help ${error.id}`,
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
  });
});
