import { Tab } from "@/components/tabs";
import { css } from "@/styled/css";
import { type ButtonHTMLAttributes, forwardRef } from "react";

const button = css({
  cursor: "pointer",
});

interface LabelManagerTabProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  children: string;
  onClick: () => void;
  isSelected: boolean;
}
const LabelManagerTab = forwardRef<HTMLButtonElement, LabelManagerTabProps>(
  function LabelManagerTab({ onClick, children, isSelected, ...props }, ref) {
    return (
      <button
        {...props}
        ref={ref}
        onClick={onClick}
        type="button"
        className={button}
      >
        <Tab status={isSelected ? "completed" : "default"}>
          <span>{children}</span>
        </Tab>
      </button>
    );
  },
);

export default LabelManagerTab;
