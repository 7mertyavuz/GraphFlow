import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 text-center">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight">GraphFlow</h1>
        <p className="max-w-lg text-lg text-muted-foreground">
          Bir formasyon çizin veya kütüphaneden seçin. Piyasada benzer şekilleri
          bulun, geçmişte ne olduğunu görün.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          href="/radar"
          className={cn(buttonVariants({ size: "lg" }))}
        >
          Canlı Radar
        </Link>
        <Link
          href="/backtest"
          className={cn(buttonVariants({ variant: "outline", size: "lg" }))}
        >
          Tarihsel Analiz
        </Link>
      </div>
      <p className="max-w-md text-xs text-muted-foreground">
        Bu uygulama işlem sinyali değil, geçmiş dağılımları ve istatistiksel
        beklentileri sunar.
      </p>
    </main>
  );
}
