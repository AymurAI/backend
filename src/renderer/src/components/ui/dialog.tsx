import { css, cx } from "@/styled/css";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import type { ComponentPropsWithoutRef, HTMLAttributes } from "react";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogClose = DialogPrimitive.Close;
const DialogTitle = DialogPrimitive.Title;
const DialogDescription = DialogPrimitive.Description;

const overlayStyles = css({
  position: "fixed",
  inset: "[0]",
  zIndex: 50,
  bg: "[rgba(0, 0, 0, 0.5)]",

  "&[data-state='open']": {
    animation: "fadeIn",
  },
  "&[data-state='closed']": {
    animation: "fadeOut",
  },
});

const contentStyles = css({
  position: "fixed",
  inset: "[0]",
  margin: "auto",
  zIndex: 50,

  bg: "bg.secondary",
  rounded: "sm",
  p: "6",
  boxShadow: "[0px 4px 8px rgba(0, 0, 0, 0.1)]",

  width: "[90vw]",
  minWidth: "[300px]",
  maxWidth: "[80%]",
  h: "[fit-content]",

  "&[data-state='open']": {
    animation: "fadeIn",
  },
  "&[data-state='closed']": {
    animation: "fadeOut",
  },
});

const headerStyles = css({
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  mb: "4",
});

const footerStyles = css({
  display: "flex",
  gap: "2",
  justifyContent: "flex-end",
  alignItems: "center",
  mt: "8",
});

function DialogOverlay({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      className={cx(overlayStyles, className)}
      {...props}
    />
  );
}

function DialogContent({
  className,
  container,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  container?: HTMLElement;
}) {
  return (
    <DialogPrimitive.Portal container={container}>
      <DialogOverlay />
      <DialogPrimitive.Content
        className={cx(contentStyles, className)}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function DialogHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx(headerStyles, className)} {...props} />;
}

function DialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx(footerStyles, className)} {...props} />;
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
  DialogTrigger,
};
