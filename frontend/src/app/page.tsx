"use client";

import Link from "next/link";
import {
  ArrowRight,
  LineChart,
  Radar,
  Ruler,
  ScanSearch,
  ShieldAlert,
  Sigma,
} from "lucide-react";

import { ShapeThumb } from "@/components/query/ShapeThumb";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";

const STEP_ICONS = [ScanSearch, Ruler, Sigma];

const SHAPE_VALUES = [
  [0, 0.35, 0.15, 0.75, 0.2, 0.5, 0.05],
  [0.9, 0.25, 0.05, 0.5, 0.08, 0.35, 0.95],
  [0.85, 0.4, 0.1, 0.05, 0.15, 0.5, 0.8, 0.6, 1],
  [0.1, 0.5, 0.25, 0.65, 0.45, 0.8, 0.62, 0.9],
];

export default function Home() {
  const { t } = useI18n();
  return (
    <main className="flex flex-1 flex-col">
      <section className="mx-auto w-full max-w-[1100px] px-4 pb-14 pt-16 lg:px-6 lg:pt-24">
        <div className="flex flex-col items-center text-center">
          <Badge tone="brand" className="mb-6 px-3 py-1">
            <span className="size-1.5 rounded-full bg-brand" />
            {t.home.badge}
          </Badge>

          <h1 className="max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
            {t.home.headlineStart}{" "}
            <span className="bg-gradient-to-r from-brand to-sky-200 bg-clip-text text-transparent">
              {t.home.headlineHighlight}
            </span>{" "}
            {t.home.headlineEnd}
          </h1>

          <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            {t.home.leadStart}{" "}
            <span className="text-foreground">{t.home.leadHighlight}</span>{" "}
            {t.home.leadEnd}
          </p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link href="/backtest" className={cn(buttonVariants({ size: "lg" }), "gap-2 px-5")}>
              <LineChart className="size-4" />
              {t.home.searchCta}
            </Link>
            <Link
              href="/radar"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "gap-2 px-5")}
            >
              <Radar className="size-4" />
              {t.home.radarCta}
            </Link>
          </div>

          <div className="mt-14 grid w-full grid-cols-2 gap-3 sm:grid-cols-4">
            {SHAPE_VALUES.map((values, i) => (
              <div
                key={i}
                className="panel flex flex-col gap-2 p-3 transition-colors hover:border-brand/30"
              >
                <div className="h-12">
                  <ShapeThumb values={values} />
                </div>
                <span className="text-[11px] text-muted-foreground">{t.home.shapes[i]}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-[1100px] px-4 pb-16 lg:px-6">
        <div className="grid gap-4 md:grid-cols-3">
          {t.home.steps.map((step, index) => {
            const Icon = STEP_ICONS[index];
            return (
              <Card key={step.title}>
                <CardBody className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="flex size-8 items-center justify-center rounded-lg border border-brand/25 bg-brand/10">
                      <Icon className="size-4 text-brand" />
                    </span>
                    <span className="text-[11px] font-medium tabular text-muted-foreground">
                      0{index + 1}
                    </span>
                  </div>
                  <h2 className="text-sm font-semibold">{step.title}</h2>
                  <p className="text-xs leading-relaxed text-muted-foreground">{step.body}</p>
                </CardBody>
              </Card>
            );
          })}
        </div>

        <div className="mt-4 flex flex-col gap-3 rounded-xl border border-warp/20 bg-warp/[0.06] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warp" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-warp">{t.home.notSignalTitle}</p>
              <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
                {t.home.notSignalBody}
              </p>
            </div>
          </div>
          <Link
            href="/bulgular"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "shrink-0 gap-1.5")}
          >
            {t.home.findingsCta}
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </section>
    </main>
  );
}
