"use client";

export function SkeletonChart() {
  return (
    <div className="flex h-40 w-full animate-pulse flex-col gap-2 rounded-md border border-border bg-muted/50 p-3">
      <div className="h-3 w-16 rounded bg-muted" />
      <div className="flex-1 rounded bg-muted" />
      <div className="flex gap-2">
        <div className="h-3 w-12 rounded bg-muted" />
        <div className="h-3 w-12 rounded bg-muted" />
      </div>
    </div>
  );
}

export function SkeletonGrid({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonChart key={i} />
      ))}
    </div>
  );
}
