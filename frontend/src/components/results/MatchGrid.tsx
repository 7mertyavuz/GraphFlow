"use client";

import { Loader2, SearchX, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type Match } from "@/services/endpoints";

import { MatchCard } from "./MatchCard";

interface MatchGridProps {
  results: Match[];
  searchId: string | null;
  isLoading: boolean;
  isFetchingMore: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  hasSearched: boolean;
}

export function MatchGrid({
  results,
  searchId,
  isLoading,
  isFetchingMore,
  hasMore,
  onLoadMore,
  hasSearched,
}: MatchGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[248px]" />
        ))}
      </div>
    );
  }

  if (!hasSearched) {
    return (
      <Placeholder
        icon={Sparkles}
        title="Henüz arama yapılmadı"
        body="Soldan bir formasyon çizin veya kütüphaneden seçin, ardından taramayı başlatın."
      />
    );
  }

  if (results.length === 0) {
    return (
      <Placeholder
        icon={SearchX}
        title="Eşleşme bulunamadı"
        body="Motor 'eşleşme yok' diyebilir — bu bir hata değil, kalibre edilmiş bir cevaptır. Toleransı esnetin, min. genliği düşürün veya daha belirgin bir formasyon deneyin."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-3">
        {results.map((match) => (
          <MatchCard
            key={`${match.symbol}-${match.timeframe}-${match.start_idx}-${match.window_length}`}
            match={match}
            searchId={searchId}
          />
        ))}
      </div>

      {hasMore && (
        <div className="flex justify-center pt-2">
          <Button variant="outline" onClick={onLoadMore} disabled={isFetchingMore} className="gap-2">
            {isFetchingMore && <Loader2 className="size-4 animate-spin" />}
            Daha fazla göster
          </Button>
        </div>
      )}
    </div>
  );
}

function Placeholder({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border p-10 text-center">
      <div className="rounded-full border border-border bg-secondary/50 p-3">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-md text-xs leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}
