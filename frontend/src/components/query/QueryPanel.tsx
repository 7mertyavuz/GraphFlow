"use client";

import { useState } from "react";
import { Library, Loader2, Pencil, Search } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Slider } from "@/components/ui/slider";
import { useDraw } from "@/hooks/useDraw";
import { useI18n } from "@/i18n/LanguageProvider";
import {
  type SearchRequest,
  type Template,
  type Timeframe,
  type Tolerance,
} from "@/services/endpoints";
import { formatAmplitude } from "@/utils/formatters";
import { isFlat } from "@/utils/shape";

import { DrawPad } from "./DrawPad";
import { ShapeThumb } from "./ShapeThumb";
import { TemplatePicker } from "./TemplatePicker";

interface QueryPanelProps {
  mode: SearchRequest["mode"];
  submitLabel: string;
  isPending: boolean;
  errorMessage?: string | null;
  onSubmit: (payload: SearchRequest) => void;
}

export function QueryPanel({
  mode,
  submitLabel,
  isPending,
  errorMessage,
  onSubmit,
}: QueryPanelProps) {
  const [source, setSource] = useState<"draw" | "template">("draw");
  const [template, setTemplate] = useState<Template | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>("4h");
  const [tolerance, setTolerance] = useState<Tolerance>("medium");
  const [minAmplitude, setMinAmplitude] = useState<number[]>([10]);

  const draw = useDraw();
  const { t } = useI18n();

  const timeframes = [
    { value: "4h" as Timeframe, label: t.query.tf4h, hint: t.query.tf4hHint },
    { value: "1d" as Timeframe, label: t.query.tf1d, hint: t.query.tf1dHint },
  ];
  // DTW mesafesi yüzde değildir: kademe, uydurma bir "%85 benzerlik" yerine (K-17).
  const tolerances = [
    { value: "strict" as Tolerance, label: t.query.strict, hint: t.query.strictHint },
    { value: "medium" as Tolerance, label: t.query.medium, hint: t.query.mediumHint },
    { value: "flexible" as Tolerance, label: t.query.flexible, hint: t.query.flexibleHint },
  ];
  const sources = [
    { value: "draw" as const, label: t.query.draw, icon: Pencil },
    { value: "template" as const, label: t.query.library, icon: Library },
  ];

  const usingTemplate = source === "template" && template !== null;
  const drawnFlat = source === "draw" && draw.series.length > 1 && isFlat(draw.series);
  const ready = usingTemplate || (source === "draw" && draw.series.length > 1 && !drawnFlat);

  const preview = usingTemplate ? template.vector : draw.series;

  const handleSubmit = () => {
    if (!ready) return;
    onSubmit({
      mode,
      timeframe,
      tolerance,
      min_amplitude: minAmplitude[0],
      limit: 12,
      window_lengths: [24, 40, 64, 100],
      // Ham (x, y) noktaları gider; 32'ye indirgeme, aliasing filtresi ve
      // z-score sunucuda (K-02). İstemci kendi ızgarasını dayatmaz.
      points: usingTemplate ? null : draw.queryPoints,
      template_id: usingTemplate ? template.id : null,
    });
  };

  const handleTemplateSelect = (selected: Template) => {
    setTemplate(selected);
    // Çizim tarafına da yansısın: kütüphaneden seçmek ile aynı şekli çizmek
    // motor açısından aynı yoldur (K-04), arayüz de bunu göstersin.
    draw.setSeries(selected.vector);
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2">
          <CardTitle>{t.query.title}</CardTitle>
          <Segmented
            options={sources}
            value={source}
            onChange={(value) => {
              setSource(value);
              if (value === "draw") setTemplate(null);
            }}
            size="sm"
            className="w-[168px]"
            ariaLabel={t.query.sourceAria}
          />
        </CardHeader>
        <CardBody className="space-y-3">
          {source === "draw" ? (
            <DrawPad
              points={draw.points}
              isDrawing={draw.isDrawing}
              onPointerDown={draw.start}
              onPointerMove={draw.move}
              onPointerUp={draw.end}
              onClear={() => {
                draw.reset();
                setTemplate(null);
              }}
            />
          ) : (
            <TemplatePicker selectedId={template?.id ?? null} onSelect={handleTemplateSelect} />
          )}

          {drawnFlat && (
            <Alert tone="warn" title={t.query.flatTitle}>
              {t.query.flatBody}
            </Alert>
          )}

          {usingTemplate && preview.length > 1 && (
            <div className="flex items-center gap-3 rounded-lg border border-border bg-secondary/40 p-3">
              <div className="h-10 w-24 shrink-0">
                <ShapeThumb values={preview} />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-medium">{template.name}</p>
                <p className="truncate text-[11px] text-muted-foreground">
                  {template.description || template.name_en}
                </p>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t.query.filters}</CardTitle>
        </CardHeader>
        <CardBody className="space-y-5">
          <Field label={t.query.timeframe}>
            <Segmented options={timeframes} value={timeframe} onChange={setTimeframe} size="sm" />
          </Field>

          <Field label={t.query.tolerance} hint={t.query.toleranceHint}>
            <Segmented options={tolerances} value={tolerance} onChange={setTolerance} size="sm" />
          </Field>

          <Field
            label={t.query.minAmplitude}
            value={formatAmplitude(minAmplitude[0]).replace(/[.,]0(?=%|$)/, "")}
            hint={t.query.minAmplitudeHint}
          >
            <Slider
              value={minAmplitude}
              onValueChange={(v) => setMinAmplitude(Array.isArray(v) ? [...v] : [v])}
              min={0}
              max={50}
              step={5}
              className="pt-1"
            />
          </Field>

          <Button
            onClick={handleSubmit}
            disabled={!ready || isPending}
            size="lg"
            className="w-full gap-2"
          >
            {isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Search className="size-4" />
            )}
            {isPending ? t.query.scanning : submitLabel}
          </Button>

          {!ready && !isPending && (
            <p className="text-center text-[11px] text-muted-foreground">
              {source === "draw" ? t.query.drawToSearch : t.query.pickToSearch}
            </p>
          )}

          {errorMessage && <Alert tone="danger">{errorMessage}</Alert>}
        </CardBody>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  hint,
  children,
}: {
  label: string;
  value?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">{label}</span>
        {value && (
          <Badge tone="brand" className="tabular">
            {value}
          </Badge>
        )}
      </div>
      {children}
      {hint && <p className="text-[11px] leading-relaxed text-muted-foreground">{hint}</p>}
    </div>
  );
}
