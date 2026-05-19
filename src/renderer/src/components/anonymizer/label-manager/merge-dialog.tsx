import Button from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
import type { EntityGroup } from "@/hooks/useEntityGroups";

interface MergeDialogProps {
  source: EntityGroup | null;
  target: EntityGroup | null;
  onClose: () => void;
  onConfirm: () => void;
}

export default function MergeDialog({
  source,
  target,
  onClose,
  onConfirm,
}: MergeDialogProps) {
  return (
    <Dialog
      open={source !== null && target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogTitle>Unificar grupos</DialogTitle>
        {source && target && (
          <p>
            ¿Deseas unificar <b>{source.renderToken}</b> con{" "}
            <b>{target.renderToken}</b>? <br />
            Todas las menciones de <b>{source.renderToken}</b> pasarán a
            pertenecer a <b>{target.renderToken}</b> y el grupo original será
            eliminado.
          </p>
        )}
        <DialogFooter>
          <Button onClick={onConfirm}>Unificar</Button>
          <Button onClick={onClose}>Cancelar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
