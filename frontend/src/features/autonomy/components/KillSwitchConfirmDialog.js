import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function KillSwitchConfirmDialog({ open, onConfirm, onCancel, nextActive, reason, onReasonChange }) {
  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {nextActive ? "Activate kill switch?" : "Clear kill switch?"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {nextActive
              ? "This blocks new and continued bounded autonomy until the backend clears it."
              : "This allows bounded autonomy to resume under backend policy controls."}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {nextActive ? (
          <div className="autonomy-killDialogReason">
            <label className="autonomy-field autonomy-field--wide">
              <span className="autonomy-fieldLabel">Kill reason (optional)</span>
              <input
                className="autonomy-input"
                onChange={(event) => onReasonChange(event.target.value)}
                placeholder="Operator reason recorded with kill-switch activation"
                value={reason}
              />
            </label>
          </div>
        ) : null}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm}>
            {nextActive ? "Activate kill switch" : "Confirm clear"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
