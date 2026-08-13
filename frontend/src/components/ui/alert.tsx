import { cva, type VariantProps } from "class-variance-authority";
import { AlertTriangle, Info, OctagonAlert, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "flex gap-2.5 rounded-lg border p-3 text-xs leading-relaxed",
  {
    variants: {
      tone: {
        info: "border-border bg-secondary/60 text-muted-foreground",
        warn: "border-warp/25 bg-warp/10 text-warp",
        danger: "border-destructive/30 bg-destructive/10 text-destructive",
      },
    },
    defaultVariants: { tone: "info" },
  }
);

const ICONS: Record<string, LucideIcon> = {
  info: Info,
  warn: AlertTriangle,
  danger: OctagonAlert,
};

interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  title?: string;
}

export function Alert({ className, tone = "info", title, children, ...props }: AlertProps) {
  const Icon = ICONS[tone ?? "info"];
  return (
    <div className={cn(alertVariants({ tone }), className)} role="status" {...props}>
      <Icon className="mt-0.5 size-3.5 shrink-0" />
      <div className="space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  );
}
