import Button from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";

interface ReplaceDialogProps {
  isOpen: boolean;
  label: string;
  onClose: (open: boolean) => void;
  onConfirm: () => void;
}
export default function ReplaceDialog({
  isOpen,
  onClose,
  onConfirm,
  label,
}: ReplaceDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Reemplazar todas las ocurrencias</DialogTitle>
        <p>
          ¿Deseas reemplazar todas las ocurrencias del grupo con la etiqueta{" "}
          <b>{label}</b>?
        </p>
        <DialogFooter>
          <Button onClick={onConfirm}>Aplicar</Button>
          <Button onClick={() => onClose(false)}>Cancelar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
