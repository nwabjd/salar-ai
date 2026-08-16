interface SkeletonProps {
  height: string;
  width: string;
}

export function Skeleton({ height, width }: SkeletonProps) {
  return (
    <div
      className="skeleton"
      aria-hidden="true"
      style={{ height, width, maxWidth: "100%" }}
    />
  );
}
