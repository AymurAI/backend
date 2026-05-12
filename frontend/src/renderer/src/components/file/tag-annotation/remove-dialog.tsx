import Button from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";

interface RemoveDialogProps {
  isOpen: boolean;
  text: string;
  onClose: (open: boolean) => void;
  onConfirm: () => void;
}
export default function RemoveDialog({
  isOpen,
  onClose,
  onConfirm,
  text,
}: RemoveDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Eliminar ocurrencias con este texto</DialogTitle>
        <p id="remove-dialog-description">
          Se eliminarán todas las ocurrencias que coincidan exactamente con el
          texto <b>{text}</b>. ¿Deseas continuar?
        </p>
        <DialogFooter>
          <Button onClick={onConfirm}>Eliminar</Button>
          <Button onClick={() => onClose(false)}>Cancelar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
