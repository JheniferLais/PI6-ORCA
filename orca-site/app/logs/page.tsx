import type { Metadata } from "next";
import LogsPanel from "@/components/logs/LogsPanel";

export const metadata: Metadata = {
  title: "Histórico de alertas | ORCA",
};

export default function LogsPage() {
  return <LogsPanel />;
}
