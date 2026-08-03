"use client";

import { BlueprintChart } from "./BlueprintChart";
import { SkeletonGrid } from "./SkeletonChart";
import { type paths } from "@/types/api";

type Match = paths["/api/search"]["post"]["responses"]["200"]["content"]["application/json"]["results"][number];

interface MatchGridProps {
  results: Match[];
  queryVector: number[];
  isLoading?: boolean;
  total?: number;
}

export function MatchGrid({
  results,
  queryVector,
  isLoading,
  total,
}: MatchGridProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <SkeletonGrid count={12} />
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border p-8 text-center text-muted-foreground">
        Eşleşme bulunamadı.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {total !== undefined && (
        <p className="text-sm text-muted-foreground">
          {total} eşleşme bulundu, en iyi {results.length} gösteriliyor.
        </p>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {results.map((match) => (
          <BlueprintChart key={`${match.symbol}-${match.start_idx}`} match={match} queryVector={queryVector} />
        ))}
      </div>
    </div>
  );
}
