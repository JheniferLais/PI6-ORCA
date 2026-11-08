import type { Metadata } from "next";
import ExigirLogin from "@/components/auth/ExigirLogin";
import LogsPanel from "@/components/logs/LogsPanel";

export const metadata: Metadata = {
  title: "Histórico de alertas | ORCA",
};

export default function LogsPage() {
  return (
    <ExigirLogin>
      <LogsPanel />
    </ExigirLogin>
  );
}
