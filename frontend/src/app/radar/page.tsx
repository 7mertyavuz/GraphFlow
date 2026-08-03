"use client";

import { useState } from "react";
import { DrawPad } from "@/components/canvas/DrawPad";
import { TemplatePicker } from "@/components/canvas/TemplatePicker";
import { MatchGrid } from "@/components/charts/MatchGrid";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { useCreateSearch, useSearchResults } from "@/hooks/useGraphFlowApi";
import { PValueWarning } from "@/components/outcome/PValueWarning";
import { AlertCircle } from "lucide-react";

const TOLERANCE_LABELS: Record<string, string> = {
  strict: "Katı",
  medium: "Orta",
  flexible: "Esnek",
};

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

  return (
    <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row">
      <aside className="flex w-full flex-col gap-4 lg:w-80">
        <div className="flex gap-2">
          <Button
            variant={mode === "draw" ? "default" : "outline"}
            onClick={() => setMode("draw")}
          >
            Çizim
          </Button>
          <Button
            variant={mode === "template" ? "default" : "outline"}
            onClick={() => setMode("template")}
          >
            Şablon
          </Button>
        </div>

        {mode === "draw" ? (
          <DrawPad onChange={setVector} />
        ) : (
          <TemplatePicker onSelect={handleTemplateSelect} />
        )}

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span>Tolerans</span>
            <span className="font-medium">{TOLERANCE_LABELS[toleranceValue]}</span>
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
            <span className="font-medium">%{minAmplitude[0]}</span>
          </div>
          <Slider
            value={minAmplitude}
            onValueChange={(v) => setMinAmplitude(Array.isArray(v) ? [...v] : [v])}
            min={5}
            max={50}
            step={5}
          />
        </div>

        <Button
          onClick={handleSearch}
          disabled={createSearch.isPending || (mode === "draw" && vector.length < 32)}
          size="lg"
        >
          {createSearch.isPending ? "Taranıyor…" : "Piyasayı Tara"}
        </Button>

        {createSearch.error && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="size-4" />
            <span>Arama başarısız oldu.</span>
          </div>
        )}

        {sessionInfo && (
          <PValueWarning
            sessionQueries={sessionInfo.session_queries}
            multipleComparisonWarning={sessionInfo.multiple_comparison_warning}
            adjustedAlpha={sessionInfo.adjusted_alpha}
          />
        )}
      </aside>

      <section className="flex-1">
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
