import { css } from "@/styled/css";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { DotsSixVertical } from "phosphor-react";
import { type PointerEvent, type ReactNode, useRef } from "react";

const handle = css({
  cursor: "grab",
  color: "text.lighter",
  display: "flex",
  alignItems: "center",
  p: "0",
  bg: "transparent",
  border: "none",
  "&:hover": { color: "text.default" },
  "&:active": { cursor: "grabbing" },
});

const wrapper = css({
  display: "flex",
  alignItems: "flex-start",
  gap: "2",
  minW: "0",
  w: "full",
  transition: "[opacity 0.2s, box-shadow 0.2s]",
});

const content = css({
  flex: "1",
  minW: "0",
});

interface SortableGroupProps {
  id: string;
  children: ReactNode;
  isOpen?: boolean;
  onToggleOpen?: () => void;
  toggleLabel?: string;
}

export default function SortableGroup({
  id,
  children,
  isOpen,
  onToggleOpen,
  toggleLabel,
}: SortableGroupProps) {
  const pointerStartRef = useRef<{ x: number; y: number } | null>(null);
  const movedRef = useRef(false);
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    boxShadow: isDragging ? "0 4px 12px rgba(0,0,0,0.15)" : "none",
  };

  function handlePointerDown(event: PointerEvent<HTMLButtonElement>) {
    pointerStartRef.current = { x: event.clientX, y: event.clientY };
    movedRef.current = false;
  }

  function handlePointerMove(event: PointerEvent<HTMLButtonElement>) {
    const pointerStart = pointerStartRef.current;
    if (!pointerStart) return;

    const dx = event.clientX - pointerStart.x;
    const dy = event.clientY - pointerStart.y;
    if (Math.hypot(dx, dy) > 4) movedRef.current = true;
  }

  function handleClick() {
    if (movedRef.current) return;
    onToggleOpen?.();
  }

  return (
    <div ref={setNodeRef} style={style} className={wrapper}>
      <button
        type="button"
        className={handle}
        onPointerDownCapture={handlePointerDown}
        onPointerMoveCapture={handlePointerMove}
        onClick={handleClick}
        aria-label={toggleLabel}
        aria-expanded={isOpen}
        {...attributes}
        {...listeners}
      >
        <DotsSixVertical size={20} />
      </button>
      <div className={content}>{children}</div>
    </div>
  );
}
