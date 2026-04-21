import { formatLabel } from "@/features/autonomy/formatters";
import { SectionHeader } from "@/features/autonomy/components/ui";

export default function SelectedRunPanel({ selectedRunSummary }) {
  if (!selectedRunSummary) {
    return null;
  }

  return (
    <section className="autonomy-panel autonomy-panel--selectedRun">
      <SectionHeader
        title="Selected run in replay"
        description="Autonomy navigation preserves the existing run-detail surface rather than duplicating replay in this workspace."
      />
      <div className="autonomy-selectedRunSummary">
        <div>
          <div className="autonomy-keyValueLabel">Run id</div>
          <div className="autonomy-keyValueValue">{selectedRunSummary.run_id}</div>
        </div>
        <div>
          <div className="autonomy-keyValueLabel">State</div>
          <div className="autonomy-keyValueValue">{formatLabel(selectedRunSummary.state)}</div>
        </div>
        <div>
          <div className="autonomy-keyValueLabel">Goal</div>
          <div className="autonomy-keyValueValue autonomy-keyValueValue--wrap">{selectedRunSummary.goal}</div>
        </div>
      </div>
    </section>
  );
}