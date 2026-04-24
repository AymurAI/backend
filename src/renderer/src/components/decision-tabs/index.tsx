import { Plus as Icon } from "phosphor-react";

import { Stack, Tab, TabName } from "@/components";
import nArray from "@/utils/nArray";
import { PlusButton } from "./DecisionTabs.styles";

interface Props {
  selected: number;
  decisionAmount: number;
  addDecision: () => void;
  selectDecision: (n: number) => void;
  // biome-ignore lint/suspicious/noExplicitAny: in the future this any will be removed
  css?: any;
}
export default function DecisionTabs({
  selected,
  decisionAmount,
  addDecision,
  selectDecision,
  css,
}: Props) {
  const decisionArr = nArray(decisionAmount, undefined).map((_, i) => i);

  const selectDecisionHandler = (n: number) => () => selectDecision(n);

  return (
    <Stack css={css}>
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
      <PlusButton variant="secondary" onClick={addDecision}>
        <Icon size={16} weight="light" />
      </PlusButton>
    </Stack>
  );
}
