"use client";

import { Loader2, TrendingDown, TrendingUp } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useTemplates } from "@/hooks/useGraphFlowApi";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { type Template } from "@/services/endpoints";

import { ShapeThumb } from "./ShapeThumb";

interface TemplatePickerProps {
  selectedId: string | null;
  onSelect: (template: Template) => void;
}

export function TemplatePicker({ selectedId, onSelect }: TemplatePickerProps) {
  const { data: templates, isLoading, error } = useTemplates();
  const { t } = useI18n();
  const categoryLabels: Record<string, string> = {
    reversal: t.templates.reversal,
    continuation: t.templates.continuation,
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[86px]" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Alert tone="danger" title={t.templates.loadFailed}>
        {t.templates.apiRunning} <code className="kbd">uvicorn engine.api.main:app</code>
      </Alert>
    );
  }

  if (!templates?.length) {
    return <Alert tone="info">{t.templates.empty}</Alert>;
  }

  const categories = Array.from(new Set(templates.map((tpl) => tpl.category)));

  return (
    <div className="space-y-4">
      {categories.map((category) => (
        <div key={category} className="space-y-2">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {categoryLabels[category] ?? category}
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {templates
              .filter((tpl) => tpl.category === category)
              .map((template) => {
                const active = template.id === selectedId;
                const Bias = template.bias === "bearish" ? TrendingDown : TrendingUp;
                return (
                  <button
                    key={template.id}
                    type="button"
                    title={template.description || template.name_en}
                    onClick={() => onSelect(template)}
                    className={cn(
                      "group flex flex-col gap-1.5 rounded-lg border p-2 text-left transition-all",
                      active
                        ? "border-brand/60 bg-brand/10 ring-1 ring-brand/30"
                        : "border-border bg-secondary/40 hover:border-border hover:bg-accent"
                    )}
                  >
                    <div className="h-10 w-full">
                      <ShapeThumb
                        values={template.vector}
                        strokeClassName={active ? "stroke-brand" : "stroke-muted-foreground group-hover:stroke-brand"}
                      />
                    </div>
                    <div className="flex items-center justify-between gap-1">
                      <span className="truncate text-xs font-medium">{template.name}</span>
                      <Bias
                        className={cn(
                          "size-3 shrink-0",
                          template.bias === "bearish" ? "text-down" : "text-up"
                        )}
                      />
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
      ))}
    </div>
  );
}

export function TemplatePickerFallback() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" />
      {t.templates.loading}
    </div>
  );
}
