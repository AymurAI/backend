import * as RadixSwitch from "@radix-ui/react-switch";
import { css } from "@/styled/css";

const rootStyle = css({
  width: "[44px]",
  height: "[24px]",
  borderRadius: "full",
  border: "none",
  cursor: "pointer",
  position: "relative",
  flexShrink: "0",
  bg: "bg.primary-highlight",

  transitionProperty: "[background-color]",
  transitionDuration: "slow",
  transitionTimingFunction: "default",

  '&[data-state="checked"]': {
    bg: "brand.primary",
  },

  "&:disabled": {
    cursor: "not-allowed",
    opacity: "0.4",
  },
});

const thumbStyle = css({
  display: "block",
  width: "[20px]",
  height: "[20px]",
  borderRadius: "full",
  bg: "white",
  position: "absolute",
  top: "[2px]",
  left: "[2px]",

  transitionProperty: "[transform]",
  transitionDuration: "slow",
  transitionTimingFunction: "default",

  '&[data-state="checked"]': {
    transform: "[translateX(20px)]",
  },
});

type SwitchProps = RadixSwitch.SwitchProps;

function Switch(props: SwitchProps) {
  return (
    <RadixSwitch.Root className={rootStyle} {...props}>
      <RadixSwitch.Thumb className={thumbStyle} />
    </RadixSwitch.Root>
  );
}

export default Switch;
