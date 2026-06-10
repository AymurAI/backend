import Toast, { type ToastVariant } from "@/components/ui/toast";
import type { Icon } from "phosphor-react";
import { toast } from "react-hot-toast";

export function showToast(message: string, variant: ToastVariant = "info", icon?: Icon) {
  toast.custom((t) => <Toast t={t} message={message} variant={variant} icon={icon} />);
}
