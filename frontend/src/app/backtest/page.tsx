import { SearchWorkspace } from "@/components/workspace/SearchWorkspace";

export const metadata = {
  title: "Backtest — GraphFlow",
  description:
    "Geçmişteki tüm benzer formasyonları bulun ve sonrasında ne olduğunu baseline'lı olarak görün.",
};

export default function BacktestPage() {
  return (
    <SearchWorkspace
      mode="historical"
      title="Tarihsel analiz"
      description="2017'den bugüne tüm kayan pencereler taranır; yalnızca bağımsız olaylar istatistiğe girer."
      submitLabel="Geçmişte tara"
      withOutcome
    />
  );
}
