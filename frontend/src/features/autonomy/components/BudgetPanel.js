import { formatNumber, formatTimestamp } from "@/features/autonomy/formatters";
import { PanelMessage, SectionHeader, TableCell, TableHeader } from "@/features/autonomy/components/ui";

export default function BudgetPanel({ autonomyStatus, budgets, resourceError }) {
  return (
    <section className="autonomy-panel">
      <SectionHeader
        title="Budget ledgers"
        count={budgets.length}
        description="See which agents are approaching bounded runtime limits."
      />
      {resourceError ? <PanelMessage text={resourceError} tone="error" /> : null}
      <div className="autonomy-tableWrap">
        <table className="autonomy-table">
          <thead>
            <tr>
              <TableHeader>Agent</TableHeader>
              <TableHeader>Launched runs</TableHeader>
              <TableHeader>Active runs</TableHeader>
              <TableHeader>Steps observed</TableHeader>
              <TableHeader>Retries used</TableHeader>
              <TableHeader>Last breach</TableHeader>
              <TableHeader>Deadman / timeout</TableHeader>
            </tr>
          </thead>
          <tbody>
            {budgets.length === 0 ? (
              <tr><TableCell colSpan={7}>No budget ledgers returned.</TableCell></tr>
            ) : (
              budgets.map((ledger) => (
                <tr key={ledger.agent_id}>
                  <TableCell>{ledger.agent_id}</TableCell>
                  <TableCell>{formatNumber(ledger.launched_runs_total, "0")}</TableCell>
                  <TableCell>{formatNumber(ledger.active_runs, "0")}</TableCell>
                  <TableCell>{formatNumber(ledger.total_steps_observed, "0")}</TableCell>
                  <TableCell>{formatNumber(ledger.total_retries_used, "0")}</TableCell>
                  <TableCell>{formatTimestamp(ledger.last_budget_breach_at)}</TableCell>
                  <TableCell>{autonomyStatus?.kill_switch_active ? "Kill switch active" : "Unavailable"}</TableCell>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}