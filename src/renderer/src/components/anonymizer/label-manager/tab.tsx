import { Tab } from "@/components/tabs";
import { css } from "@/styled/css";

const button = css({
  cursor: "pointer",
});

interface LabelManagerTabProps {
  children: string;
  onClick: () => void;
  isSelected: boolean;
}
export default function LabelManagerTab({
  onClick,
  children,
  isSelected,
}: LabelManagerTabProps) {
  return (
    <button onClick={onClick} type="button" className={button}>
      <Tab status={isSelected ? "completed" : "default"}>
        <span>{children}</span>
      </Tab>
    </button>
  );
}
