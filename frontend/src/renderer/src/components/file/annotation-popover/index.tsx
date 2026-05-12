import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { css } from "@/styled/css";
import type { AllLabels } from "@/types/aymurai";
import type { FocusEventHandler, ReactNode } from "react";
import { useRef, useState } from "react";
import Tagger from "./tagger";

const triggerReset = css({
  appearance: "none",
  bg: "transparent",
  border: "[none]",
  padding: "0",
  cursor: "default",
  "&:focus-visible": {
    outline: "[2px solid token(colors.action.hover)]",
    outlineOffset: "[2px]",
    borderRadius: "sm",
  },
});

interface AnnotationPopoverProps {
  children: ReactNode;
  onClickOne: (label: AllLabels, suffix: number | null) => void;
  onClickAll: (label: AllLabels, suffix: number | null) => void;
  onDeleteOne?: () => void;
  onDeleteAll?: () => void;
}

export default function AnnotationPopover({
  children,
  onClickAll,
  onClickOne,
  onDeleteOne,
  onDeleteAll,
}: AnnotationPopoverProps) {
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const isFocusInside = useRef(false);
  const isKeyboardOpen = useRef(false);

  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = setTimeout(() => {
      if (!isFocusInside.current) setOpen(false);
    }, 100);
  };

  const cancelClose = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
  };

  const handleBlur: FocusEventHandler<HTMLDivElement> = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) {
      isFocusInside.current = false;
      scheduleClose();
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        className={triggerReset}
        onMouseEnter={() => {
          cancelClose();
          setOpen(true);
        }}
        onMouseLeave={scheduleClose}
        onKeyDown={(e) => {
          if (e.key === " " || e.key === "Enter") {
            isKeyboardOpen.current = true;
          }
        }}
      >
        {children}
      </PopoverTrigger>
      <PopoverContent
        side="top"
        sideOffset={8}
        showArrow={false}
        onOpenAutoFocus={(e) => {
          if (!isKeyboardOpen.current) e.preventDefault();
        }}
        onCloseAutoFocus={(e) => {
          if (!isKeyboardOpen.current) e.preventDefault();
          isKeyboardOpen.current = false;
        }}
        onMouseEnter={cancelClose}
        onMouseLeave={scheduleClose}
        onFocus={() => {
          isFocusInside.current = true;
        }}
        onBlur={handleBlur}
      >
        <Tagger onClickOne={onClickOne} onClickAll={onClickAll} onDeleteOne={onDeleteOne} onDeleteAll={onDeleteAll} />
      </PopoverContent>
    </Popover>
  );
}
