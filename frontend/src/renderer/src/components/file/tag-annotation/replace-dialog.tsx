import Button from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";

interface ReplaceDialogProps {
  isOpen: boolean;
  text: string;
  label: string;
  onClose: (open: boolean) => void;
  onConfirm: () => void;
}
export default function ReplaceDialog({
  isOpen,
  onClose,
  onConfirm,
  text,
  label,
}: ReplaceDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogTitle>Reemplazar todas las ocurrencias</DialogTitle>
        <p>
          Se reemplazará la etiqueta en todas las ocurrencias que coincidan
          exactamente con el texto <b>{text}</b> por <b>{label}</b>.
          ¿Deseas continuar?
        </p>
        <DialogFooter>
          <Button onClick={onConfirm}>Aplicar</Button>
          <Button onClick={() => onClose(false)}>Cancelar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
