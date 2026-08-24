import { useId } from "react";

import { cn } from "@/lib/utils";
import { smoothPath } from "@/utils/shape";

interface ShapeThumbProps {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
  filled?: boolean;
  strokeClassName?: string;
}

/**
 * Bir şekil vektörünün küçük önizlemesi.
 *
 * Şablon kütüphanesi bir metin listesi olamaz: kullanıcı "Yükselen Takoz"
 * ifadesini değil, şekli tanır.
 */
export function ShapeThumb({
  values,
  width = 120,
  height = 48,
  className,
  filled = true,
  strokeClassName = "stroke-brand",
}: ShapeThumbProps) {
  // SVG id'leri belge genelindedir: içerikten türetilen id, aynı uzunlukta ve
  // aynı değerle başlayan iki şablonda çakışıp ikinci karonun dolgusunu
  // birincininkine bağlıyordu.
  // (":" React'in ürettiği id'lerde var ve `url(#...)` içinde sorun çıkarır)
  const areaId = `thumb${useId().replace(/:/g, "")}`;
  if (values.length < 2) return null;
  const pad = 4;
  const d = smoothPath(values, width, height, pad);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn("h-full w-full overflow-visible", className)}
      aria-hidden
    >
      {filled && (
        <>
          <defs>
            <linearGradient id={areaId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d={`${d} L ${width - pad} ${height} L ${pad} ${height} Z`}
            fill={`url(#${areaId})`}
            className="text-brand"
          />
        </>
      )}
      <path
        d={d}
        fill="none"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={strokeClassName}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
