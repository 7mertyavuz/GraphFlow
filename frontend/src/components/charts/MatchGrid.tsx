"use client";

import { BlueprintChart } from "./BlueprintChart";
import { SkeletonGrid } from "./SkeletonChart";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { type paths } from "@/types/api";

type Match = paths["/api/search"]["post"]["responses"]["200"]["content"]["application/json"]["results"][number];

interface MatchGridProps {
  results: Match[];
  queryVector: number[];
  isLoading?: boolean;
  isFetching?: boolean;
  total?: number;
  hasMore?: boolean;
  onLoadMore?: () => void;
}

export function MatchGrid({
  results,
  queryVector,
  isLoading,
  isFetching,
  total,
  hasMore,
  onLoadMore,
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
      <div className="flex min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 p-8 text-center text-muted-foreground">
        <p className="text-lg font-medium">Eşleşme bulunamadı</p>
        <p className="text-sm">
          Toleransı esnetmeyi, min. genliği düşürmeyi veya farklı bir şekil
          çizmeyi deneyin.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {total !== undefined && (
        <p className="text-sm font-medium text-muted-foreground">
          {total.toLocaleString("tr-TR")} eşleşme bulundu · {results.length} gösteriliyor
        </p>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
        {results.map((match) => (
          <BlueprintChart
            key={`${match.symbol}-${match.start_idx}-${match.window_length}`}
            match={match}
            queryVector={queryVector}
          />
        ))}
      </div>
      {hasMore && onLoadMore && (
        <Button
          variant="outline"
          onClick={onLoadMore}
          disabled={isFetching}
          className="w-full self-center sm:w-auto"
        >
          {isFetching ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : null}
          Daha Fazla (+12)
        </Button>
      )}
    </div>
  );
}
