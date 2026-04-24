import { styled } from "@/styles";
import { X } from "phosphor-react";
import type { FC, ReactNode } from "react";
import Button from "../button";

export interface DialogOption {
  id: string;
  label: string;
  action: () => void;
}

interface DialogProps {
  isOpen: boolean;
  title?: string;
  message?: string;
  options?: DialogOption[];
  onClose: () => void;
  children?: ReactNode;
}

export const Overlay = styled("div", {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: "rgba(0, 0, 0, 0.5)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
});

export const DialogContainer = styled("div", {
  backgroundColor: "$white",
  borderRadius: "$xs",
  padding: "$l",
  minWidth: 300,
  maxWidth: 700,
  boxShadow: "0px 4px 8px rgba(0, 0, 0, 0.1)",
});

export const DialogHeader = styled("div", {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "$m",
});

export const DialogTitle = styled("h3", {
  fontSize: "$titleMd",
  fontWeight: 600,
  color: "$textDefault",
  margin: 0,
});

export const DialogMessage = styled("label", {
  color: "$textDefault",
  marginBottom: "$l",
});

export const DialogButtons = styled("div", {
  display: "flex",
  gap: "$s",
  justifyContent: "flex-end",
  alignItems: "center",
  marginTop: "$xl",
});

const Dialog: FC<DialogProps> = ({
  isOpen,
  title = "",
  message,
  options,
  onClose,
  children,
}) => {
  if (!isOpen) return null;

  return (
    <Overlay onClick={onClose}>
      <DialogContainer onClick={(e) => e.stopPropagation()}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <Button variant="none" onClick={onClose}>
            <X size={24} />
          </Button>
        </DialogHeader>
        {message && <DialogMessage>{message}</DialogMessage>}
        {children}
        {options && options.length > 0 && (
          <DialogButtons>
            {options.map((option, index) => (
              <Button
                key={option.id}
                variant={index === options.length - 1 ? "primary" : "secondary"}
                onClick={option.action}
              >
                {option.label}
              </Button>
            ))}
          </DialogButtons>
        )}
      </DialogContainer>
    </Overlay>
  );
};

export default Dialog;
