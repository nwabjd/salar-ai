interface SkeletonProps {
  height?: string;
  width?: string;
}

export function Skeleton({ height = "1rem", width = "100%" }: SkeletonProps) {
  return (
    <span
      className="skeleton"
      aria-hidden="true"
      style={{ display: "block", height, width }}
    />
  );
}
