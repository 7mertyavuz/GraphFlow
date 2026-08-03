"use client";

import { useState } from "react";
import { DrawPad } from "@/components/canvas/DrawPad";
import { TemplatePicker } from "@/components/canvas/TemplatePicker";
import { MatchGrid } from "@/components/charts/MatchGrid";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { useCreateSearch, useSearchResults } from "@/hooks/useGraphFlowApi";
import { PValueWarning } from "@/components/outcome/PValueWarning";
import { AlertCircle, Pencil, Library, Search, Loader2 } from "lucide-react";

const TOLERANCE_LABELS = ["Katı", "Orta", "Esnek"];

export default function RadarPage() {
  const [mode, setMode] = useState<"draw" | "template">("draw");
  const [vector, setVector] = useState<number[]>([]);
  const [tolerance, setTolerance] = useState<number[]>([1]);
  const [minAmplitude, setMinAmplitude] = useState<number[]>([15]);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<
    { session_queries: number; multiple_comparison_warning: boolean; adjusted_alpha: number } | null
  >(null);

  const toleranceValue = ["strict", "medium", "flexible"][tolerance[0]] as "strict" | "medium" | "flexible";
  const createSearch = useCreateSearch();
  const { data: searchData, isLoading } = useSearchResults(searchId, 0, 12);

  const handleSearch = () => {
    if (mode === "draw" && vector.length < 32) return;
    const payload = {
      points: mode === "draw" ? vector.slice(0, 32) : undefined,
      template_id: undefined as string | undefined,
      mode: "live" as const,
      timeframe: "4h" as const,
      tolerance: toleranceValue,
      min_amplitude: minAmplitude[0],
      limit: 12,
    };
    createSearch.mutate(payload, {
      onSuccess: (data) => {
        setSearchId(data.search_id);
        setSessionInfo(data.session);
      },
    });
  };

  const handleTemplateSelect = (templateVector: number[]) => {
    setMode("draw");
    setVector(templateVector);
  };

  const isReady = vector.length >= 32 || mode === "template";

  return (
    <div className="flex flex-1 flex-col gap-6 p-4 lg:flex-row lg:p-6">
      <aside className="flex w-full flex-shrink-0 flex-col gap-5 lg:w-96">
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Sorgu</h2>
          <div className="mb-4 grid grid-cols-2 gap-2">
            <Button
              variant={mode === "draw" ? "default" : "outline"}
              onClick={() => setMode("draw")}
              size="sm"
              className="gap-2"
            >
              <Pencil className="size-4" /> Çizim
            </Button>
            <Button
              variant={mode === "template" ? "default" : "outline"}
              onClick={() => setMode("template")}
              size="sm"
              className="gap-2"
            >
              <Library className="size-4" /> Şablon
            </Button>
          </div>

          {mode === "draw" ? (
            <DrawPad onChange={setVector} initialVector={vector.length >= 32 ? vector : undefined} />
          ) : (
            <TemplatePicker onSelect={handleTemplateSelect} />
          )}
        </div>

        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Filtreler
          </h3>
          <div className="space-y-5">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Tolerans</span>
                <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  {TOLERANCE_LABELS[tolerance[0]]}
                </span>
              </div>
              <Slider
                value={tolerance}
                onValueChange={(v) => setTolerance(Array.isArray(v) ? [...v] : [v])}
                min={0}
                max={2}
                step={1}
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Min. Genlik</span>
                <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  %{minAmplitude[0]}
                </span>
              </div>
              <Slider
                value={minAmplitude}
                onValueChange={(v) => setMinAmplitude(Array.isArray(v) ? [...v] : [v])}
                min={5}
                max={50}
                step={5}
              />
            </div>
          </div>

          <Button
            onClick={handleSearch}
            disabled={createSearch.isPending || !isReady}
            size="lg"
            className="mt-6 w-full gap-2"
          >
            {createSearch.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Search className="size-4" />
            )}
            {createSearch.isPending ? "Taranıyor…" : "Piyasayı Tara"}
          </Button>

          {createSearch.error && (
            <div className="mt-3 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
              <AlertCircle className="size-4 shrink-0" />
              <span>Arama başarısız oldu.</span>
            </div>
          )}
        </div>

        {sessionInfo && (
          <PValueWarning
            sessionQueries={sessionInfo.session_queries}
            multipleComparisonWarning={sessionInfo.multiple_comparison_warning}
            adjustedAlpha={sessionInfo.adjusted_alpha}
          />
        )}
      </aside>

      <section className="flex flex-1 flex-col">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Canlı Radar</h1>
          {searchData && !isLoading && (
            <span className="text-sm text-muted-foreground">
              {searchData.total.toLocaleString("tr-TR")} eşleşme
            </span>
          )}
        </div>
        <MatchGrid
          results={searchData?.results ?? []}
          queryVector={vector}
          isLoading={isLoading || createSearch.isPending}
          total={searchData?.total}
        />
      </section>
    </div>
  );
}
