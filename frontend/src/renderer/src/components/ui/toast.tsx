import type { Icon } from "phosphor-react";
import { type Toast as HotToast, toast } from "react-hot-toast";
import Callout, { type CalloutVariant } from "./callout";

export type ToastVariant = CalloutVariant;

interface ToastProps {
  t: HotToast;
  message: string;
  variant?: ToastVariant;
  icon?: Icon;
}

const ASSERTIVE_VARIANTS: ToastVariant[] = ["error", "warning"];

function Toast({ t, message, variant = "info", icon }: ToastProps) {
  const isAssertive = ASSERTIVE_VARIANTS.includes(variant);

  return (
    <div style={{ maxWidth: "75%", width: "100%" }}>
      <Callout
        message={message}
        variant={variant}
        icon={icon}
        onDismiss={() => toast.remove(t.id)}
        role={isAssertive ? "alert" : "status"}
        aria-live={isAssertive ? "assertive" : "polite"}
        aria-atomic="true"
        noBorder
      />
    </div>
  );
}

export default Toast;
