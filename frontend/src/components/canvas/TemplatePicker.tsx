"use client";

import { useTemplates } from "@/hooks/useGraphFlowApi";
import { Button } from "@/components/ui/button";

interface TemplatePickerProps {
  onSelect: (vector: number[]) => void;
}

export function TemplatePicker({ onSelect }: TemplatePickerProps) {
  const { data: templates, isLoading, error } = useTemplates();

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Şablonlar yükleniyor…</div>;
  }

  if (error) {
    return (
      <div className="text-sm text-destructive">
        Şablonlar alınamadı. API çalışıyor mu?
      </div>
    );
  }

  if (!templates || templates.length === 0) {
    return <div className="text-sm text-muted-foreground">Şablon bulunamadı.</div>;
  }

  const categories = Array.from(new Set(templates.map((t) => t.category)));

  return (
    <div className="flex flex-col gap-4">
      {categories.map((category) => (
        <div key={category}>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {category}
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
