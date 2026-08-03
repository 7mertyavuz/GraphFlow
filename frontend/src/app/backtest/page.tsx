"use client";

import { useState } from "react";
import { DrawPad } from "@/components/canvas/DrawPad";
import { TemplatePicker } from "@/components/canvas/TemplatePicker";
import { MatchGrid } from "@/components/charts/MatchGrid";
import { StatEnvelope } from "@/components/outcome/StatEnvelope";
import { RegimeTable } from "@/components/outcome/RegimeTable";
import { PValueWarning } from "@/components/outcome/PValueWarning";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  useCreateSearch,
  useSearchResults,
  useSearchStats,
} from "@/hooks/useGraphFlowApi";
import { formatR, formatPercent } from "@/utils/formatters";
import { AlertCircle } from "lucide-react";

export default function BacktestPage() {
  const [mode, setMode] = useState<"draw" | "template">("draw");
  const [vector, setVector] = useState<number[]>([]);
  const [tolerance, setTolerance] = useState<number[]>([1]);
  const [minAmplitude, setMinAmplitude] = useState<number[]>([10]);
  const [searchId, setSearchId] = useState<string | null>(null);

  const toleranceValue = ["strict", "medium", "flexible"][tolerance[0]] as "strict" | "medium" | "flexible";
  const createSearch = useCreateSearch();
  const { data: searchData, isLoading: resultsLoading } = useSearchResults(searchId, 0, 12);
  const { data: statsData, isLoading: statsLoading } = useSearchStats(searchId);

  const handleSearch = () => {
    if (mode === "draw" && vector.length < 32) return;
    const payload = {
      points: mode === "draw" ? vector.slice(0, 32) : undefined,
      template_id: undefined as string | undefined,
      mode: "historical" as const,
      timeframe: "4h" as const,
      tolerance: toleranceValue,
      min_amplitude: minAmplitude[0],
      limit: 12,
    };
    createSearch.mutate(payload, {
      onSuccess: (data) => setSearchId(data.search_id),
    });
  };

  const handleTemplateSelect = (templateVector: number[]) => {
    setMode("draw");
    setVector(templateVector);
  };

  const configs = statsData?.configs ? Object.entries(statsData.configs) : [];
  const primaryConfig = configs[0]?.[1];

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
            <span className="font-medium">
              {({ strict: "Katı", medium: "Orta", flexible: "Esnek" } as const)[toleranceValue]}
            </span>
          </div>
          <Slider value={tolerance} onValueChange={(v) => setTolerance(Array.isArray(v) ? [...v] : [v])} min={0} max={2} step={1} />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span>Min. Genlik</span>
            <span className="font-medium">%{minAmplitude[0]}</span>
          </div>
          <Slider value={minAmplitude} onValueChange={(v) => setMinAmplitude(Array.isArray(v) ? [...v] : [v])} min={5} max={50} step={5} />
        </div>

        <Button
          onClick={handleSearch}
          disabled={createSearch.isPending || (mode === "draw" && vector.length < 32)}
          size="lg"
        >
          {createSearch.isPending ? "Taranıyor…" : "Geçmişte Tara"}
        </Button>

        {createSearch.error && (
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="size-4" />
            <span>Arama başarısız oldu.</span>
          </div>
        )}

        {searchData?.session && (
          <PValueWarning
            sessionQueries={searchData.session.session_queries}
            multipleComparisonWarning={searchData.session.multiple_comparison_warning}
            adjustedAlpha={searchData.session.adjusted_alpha}
          />
        )}
      </aside>

      <section className="flex flex-1 flex-col gap-6">
        {primaryConfig && (
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-xl font-semibold">Sonra Ne Oldu?</h2>
              {!primaryConfig.expectancy.significant && (
                <span className="w-fit rounded bg-muted px-2 py-1 text-xs text-muted-foreground">
                  İstatistiksel Edge Bulunamadı
                </span>
              )}
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatEnvelope label="Beklenti (R)" envelope={primaryConfig.expectancy} />
              <StatEnvelope label="Başarı Oranı" envelope={primaryConfig.win_rate} />
              {primaryConfig.edge && (
                <StatEnvelope label="Edge (R)" envelope={primaryConfig.edge} showEdge />
              )}
            </div>
            <div className="mt-4 flex gap-4 text-sm text-muted-foreground">
              <span>Hedef: 2R</span>
              <span>Stop: 1R</span>
              <span>Teorik null: {formatPercent(primaryConfig.win_rate.null ?? 0)}</span>
            </div>
            {statsData?.disclaimer && (
              <p className="mt-4 text-xs text-muted-foreground">{statsData.disclaimer}</p>
            )}
          </div>
        )}

        {statsLoading && searchId && (
          <div className="text-sm text-muted-foreground">İstatistikler hesaplanıyor…</div>
        )}

        {primaryConfig && primaryConfig.by_regime && (
          <div>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Rejim Kırılımı
            </h3>
            <RegimeTable regimes={primaryConfig.by_regime as { period: string; n: number; win_rate: number; expectancy_r: number }[]} />
          </div>
        )}

        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Eşleşmeler
          </h3>
          <MatchGrid
            results={searchData?.results ?? []}
            queryVector={vector}
            isLoading={resultsLoading || createSearch.isPending}
            total={searchData?.total}
          />
        </div>
      </section>
    </div>
  );
}
