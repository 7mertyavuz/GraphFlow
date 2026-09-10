import { SearchWorkspace } from "@/components/workspace/SearchWorkspace";

export const metadata = {
  title: "Backtest — GraphFlow",
  description:
    "Find every similar pattern in history and see what happened next against a baseline · Geçmişteki benzer formasyonları bulun, sonrasını baseline'la görün.",
};

export default function BacktestPage() {
  return (
    <SearchWorkspace
      mode="historical"
      copy="backtest"
      withOutcome
    />
  );
}
