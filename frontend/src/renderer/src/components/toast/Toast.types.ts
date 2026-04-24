import type { CSS } from "@/styles";

export interface Props {
  children: React.ReactNode;
  icon: React.ReactElement;
  isVisible?: boolean;
  css?: CSS;
  onClose?: () => void;
}
