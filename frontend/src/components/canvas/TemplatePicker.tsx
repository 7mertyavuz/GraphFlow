"use client";

import { useTemplates } from "@/hooks/useGraphFlowApi";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";

interface TemplatePickerProps {
  onSelect: (vector: number[]) => void;
}

export function TemplatePicker({ onSelect }: TemplatePickerProps) {
  const { data: templates, isLoading, error } = useTemplates();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        Şablonlar yükleniyor…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
        Şablonlar alınamadı. API çalışıyor mu?
      </div>
    );
  }

  if (!templates || templates.length === 0) {
    return <div className="text-sm text-muted-foreground">Şablon bulunamadı.</div>;
  }

  const categories = Array.from(new Set(templates.map((t) => t.category)));

  return (
    <div className="flex flex-col gap-5">
      {categories.map((category) => (
        <div key={category}>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {category === "reversal" ? "Dönüş Formasyonları" : category === "continuation" ? "Devam Formasyonları" : category}
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {templates
              .filter((t) => t.category === category)
              .map((t) => (
                <Button
                  key={t.id}
                  variant="outline"
                  size="sm"
                  onClick={() => onSelect(t.vector)}
                  className="justify-start text-xs"
                >
                  {t.name}
                </Button>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
