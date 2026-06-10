import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { sva } from "@/styled/css";
import { styled } from "@/styled/jsx";

const button = sva({
  slots: ["button", "tooltipContent"],
  base: {
    button: {
      p: "0.5",
      rounded: "[6px]",
      cursor: "pointer",
      flexShrink: "0",
      _hover: {
        bg: "action.hover",
      },
    },
    tooltipContent: {
      bg: "action.hover",
      color: "white",
      px: "1",
      py: "0.5",
      rounded: "sm",
    },
  },
  variants: {
    disabled: {
      true: {
        button: {
          cursor: "not-allowed",
          _hover: {
            bg: "transparent",
          },
        },
      },
    },
  },
});

interface TaggerButtonProps {
  tooltip: string;
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}
export default function TaggerButton({
  children,
  tooltip,
  onClick,
  disabled = false,
}: TaggerButtonProps) {
  const classes = button({ disabled });
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={disabled ? undefined : onClick}
            disabled={disabled}
            aria-disabled={disabled}
            className={classes.button}
          >
            {children}
          </button>
        </TooltipTrigger>
        <TooltipContent showArrow={false} sideOffset={12}>
          <div className={classes.tooltipContent}>
            <styled.p textStyle="label.sm.default">{tooltip}</styled.p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
