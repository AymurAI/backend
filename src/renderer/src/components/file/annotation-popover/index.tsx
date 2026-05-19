import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { css } from "@/styled/css";
import type { AllLabels } from "@/types/aymurai";
import type { FocusEventHandler, ReactNode } from "react";
import { useEffect, useId, useRef, useState } from "react";
import Tagger from "./tagger";

const CLOSE_DELAY_MS = 120;
const OPEN_EVENT = "aymurai:annotation-popover-open";

const triggerFocus = css({
  "&:focus-visible": {
    outline: "[2px solid token(colors.action.hover)]",
    outlineOffset: "[2px]",
    borderRadius: "sm",
  },
});

interface AnnotationPopoverProps {
  children: ReactNode;
  onClickOne: (label: AllLabels) => void;
  onClickAll: (label: AllLabels) => void;
  onDeleteOne?: () => void;
  onDeleteAll?: () => void;
  onHoverChange?: (hovered: boolean) => void;
}

export default function AnnotationPopover({
  children,
  onClickAll,
  onClickOne,
  onDeleteOne,
  onDeleteAll,
  onHoverChange,
}: AnnotationPopoverProps) {
  const popoverId = useId();
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isTriggerHovered = useRef(false);
  const isContentHovered = useRef(false);
  const isFocusInside = useRef(false);
  const isKeyboardOpen = useRef(false);

  const cancelClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  useEffect(() => {
    const closeWhenAnotherOpens = (event: Event) => {
      const openedId = (event as CustomEvent<string>).detail;
      if (openedId === popoverId) return;

      isTriggerHovered.current = false;
      isContentHovered.current = false;
      isFocusInside.current = false;
      setOpen(false);
      if (closeTimer.current) {
        clearTimeout(closeTimer.current);
        closeTimer.current = null;
      }
    };

    window.addEventListener(OPEN_EVENT, closeWhenAnotherOpens);

    return () => {
      window.removeEventListener(OPEN_EVENT, closeWhenAnotherOpens);
      if (closeTimer.current) clearTimeout(closeTimer.current);
    };
  }, [popoverId]);

  const setInteractive = (nextOpen: boolean, announce = false) => {
    setOpen(nextOpen);
    onHoverChange?.(nextOpen);
    if (nextOpen && announce) {
      window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: popoverId }));
    }
  };

  const scheduleClose = () => {
    cancelClose();
    closeTimer.current = setTimeout(() => {
      if (
        !isFocusInside.current &&
        !isTriggerHovered.current &&
        !isContentHovered.current
      ) {
        setInteractive(false);
      }
    }, CLOSE_DELAY_MS);
  };

  const handleBlur: FocusEventHandler<HTMLDivElement> = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) {
      isFocusInside.current = false;
      scheduleClose();
    }
  };

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) {
          cancelClose();
          setInteractive(true, true);
          return;
        }
        if (
          isTriggerHovered.current ||
          isContentHovered.current ||
          isFocusInside.current
        ) {
          scheduleClose();
          return;
        }
        setInteractive(false);
      }}
    >
      <PopoverTrigger
        asChild
        className={triggerFocus}
        onMouseEnter={() => {
          isTriggerHovered.current = true;
          cancelClose();
          setInteractive(true, true);
        }}
        onMouseLeave={() => {
          isTriggerHovered.current = false;
          scheduleClose();
        }}
        onFocus={() => {
          isFocusInside.current = true;
          cancelClose();
          setInteractive(true, true);
        }}
        onBlur={() => {
          isFocusInside.current = false;
          scheduleClose();
        }}
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
        onMouseEnter={() => {
          isContentHovered.current = true;
          cancelClose();
          onHoverChange?.(true);
        }}
        onMouseLeave={() => {
          isContentHovered.current = false;
          scheduleClose();
        }}
        onFocus={() => {
          isFocusInside.current = true;
          cancelClose();
          onHoverChange?.(true);
        }}
        onBlur={handleBlur}
      >
        <Tagger
          onClickOne={onClickOne}
          onClickAll={onClickAll}
          onDeleteOne={onDeleteOne}
          onDeleteAll={onDeleteAll}
        />
      </PopoverContent>
    </Popover>
  );
}
