import {
  cloneElement,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";

interface FieldProps {
  id: string;
  label: string;
  children: ReactElement<{
    id?: string;
    className?: string;
    "aria-describedby"?: string;
    "aria-invalid"?: boolean;
  }>;
  hint?: ReactNode;
  error?: ReactNode;
}

export function Field({ id, label, children, hint, error }: FieldProps) {
  const descriptionId = hint || error ? `${id}-description` : undefined;
  const mergedDescriptionIds =
    [children.props["aria-describedby"], descriptionId]
      .filter(Boolean)
      .join(" ") || undefined;
  const control = isValidElement(children)
    ? cloneElement(children, {
        id,
        className: `field__control ${children.props.className ?? ""}`.trim(),
        "aria-describedby": mergedDescriptionIds,
        "aria-invalid": error ? true : children.props["aria-invalid"],
      })
    : children;

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {control}
      {hint || error ? (
        <p
          id={descriptionId}
          className={error ? "field__error" : "field__hint"}
        >
          {error ?? hint}
        </p>
      ) : null}
    </div>
  );
}
