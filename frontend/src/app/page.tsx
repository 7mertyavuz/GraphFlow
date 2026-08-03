import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Radar, LineChart, ShieldAlert } from "lucide-react";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="flex flex-1 flex-col items-center justify-center gap-10 px-6 py-20 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
          <Radar className="size-4" />
          <span>Görsel formasyon arama motoru</span>
        </div>

        <div className="max-w-3xl space-y-4">
          <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl">
            GraphFlow
          </h1>
          <p className="text-lg text-muted-foreground sm:text-xl">
            Bir formasyon çizin veya kütüphaneden seçin. Piyasada benzer
            şekilleri bulun ve geçmişte o formasyondan sonra{" "}
            <span className="text-foreground">ne olduğunu dürüstçe görün</span>.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href="/radar"
            className={cn(buttonVariants({ size: "lg" }), "gap-2")}
          >
            <Radar className="size-4" />
            Canlı Radar
          </Link>
          <Link
            href="/backtest"
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "gap-2")}
          >
            <LineChart className="size-4" />
            Tarihsel Analiz
          </Link>
        </div>

        <div className="flex max-w-xl flex-col gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldAlert className="size-4" />
            <span>Uyarı</span>
          </div>
          <p>
            Bu uygulama işlem sinyali değildir. Sunulan veriler geçmiş
            dağılımlar ve istatistiksel beklentilerdir; gelecek getirinin
            garantisi yoktur.
          </p>
        </div>
      </section>
    </main>
  );
}
