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
import {
  type SearchRequest,
  type Template,
  type Timeframe,
  type Tolerance,
} from "@/services/endpoints";
import { isFlat } from "@/utils/shape";

import { DrawPad } from "./DrawPad";
import { ShapeThumb } from "./ShapeThumb";
import { TemplatePicker } from "./TemplatePicker";

const TIMEFRAMES = [
  { value: "4h" as Timeframe, label: "4 saat", hint: "Kısa vadeli formasyonlar" },
  { value: "1d" as Timeframe, label: "1 gün", hint: "Uzun vadeli formasyonlar" },
];

/** DTW mesafesi yüzde değildir: kademe, uydurma bir "%85 benzerlik" yerine. */
const TOLERANCES = [
  { value: "strict" as Tolerance, label: "Katı", hint: "Yalnızca çok yakın eşleşmeler" },
  { value: "medium" as Tolerance, label: "Orta", hint: "Dengeli" },
  { value: "flexible" as Tolerance, label: "Esnek", hint: "Daha fazla, daha gevşek eşleşme" },
];

const SOURCES = [
  { value: "draw" as const, label: "Çiz", icon: Pencil },
  { value: "template" as const, label: "Kütüphane", icon: Library },
];

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
      // Ham noktalar gider; 32'ye indirgeme ve z-score sunucuda (K-02).
      points: usingTemplate ? null : draw.series,
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
          <CardTitle>Sorgu şekli</CardTitle>
          <Segmented
            options={SOURCES}
            value={source}
            onChange={(value) => {
              setSource(value);
              if (value === "draw") setTemplate(null);
            }}
            size="sm"
            className="w-[168px]"
            ariaLabel="Sorgu kaynağı"
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
            <Alert tone="warn" title="Düz çizim">
              Şekil taşımayan bir sorgu aranamaz (σ ≈ 0). Yükseliş, düşüş veya
              bir dönüş çizin.
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
          <CardTitle>Filtreler</CardTitle>
        </CardHeader>
        <CardBody className="space-y-5">
          <Field label="Zaman dilimi">
            <Segmented options={TIMEFRAMES} value={timeframe} onChange={setTimeframe} size="sm" />
          </Field>

          <Field
            label="Tolerans"
            hint="Eşik, sorgunun kendi null dağılımından türetilir — yüzdelik dilim."
          >
            <Segmented options={TOLERANCES} value={tolerance} onChange={setTolerance} size="sm" />
          </Field>

          <Field
            label="Min. genlik"
            value={`%${minAmplitude[0]}`}
            hint="Pencere içindeki toplam hareket. Düşük genlikli gürültüyü eler."
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
            {isPending ? "Taranıyor…" : submitLabel}
          </Button>

          {!ready && !isPending && (
            <p className="text-center text-[11px] text-muted-foreground">
              {source === "draw"
                ? "Aramak için bir şekil çizin."
                : "Aramak için kütüphaneden bir formasyon seçin."}
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
