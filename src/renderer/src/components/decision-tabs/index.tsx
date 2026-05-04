import { Tab, TabName } from "@/components";
import { css } from "@/styled/css";
import { Stack } from "@/styled/jsx";
import nArray from "@/utils/nArray";
import { Plus } from "phosphor-react";

const button = css({
  cursor: "pointer",
  p: "2",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",

  height: "full",
  width: "12",
});

interface Props {
  selected: number;
  decisionAmount: number;
  addDecision: () => void;
  selectDecision: (n: number) => void;
}
export default function DecisionTabs({
  selected,
  decisionAmount,
  addDecision,
  selectDecision,
}: Props) {
  const decisionArr = nArray(decisionAmount, undefined).map((_, i) => i);

  const selectDecisionHandler = (n: number) => () => selectDecision(n);

  return (
    <Stack direction="row" gap="2">
      {decisionArr.map((dec) => (
        <Tab
          key={dec}
          as="button"
          css={{ cursor: "pointer" }}
          onClick={selectDecisionHandler(dec)}
          status={selected === dec ? "focus" : "default"}
        >
          <TabName css={{ cursor: "pointer" }}>Decisión {dec + 1}</TabName>
        </Tab>
      ))}
      <button onClick={addDecision} className={button} type="button">
        <Plus size={16} weight="light" />
      </button>
    </Stack>
  );
}
