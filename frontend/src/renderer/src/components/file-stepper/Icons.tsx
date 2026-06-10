import { CaretLeft, CaretRight, CheckCircle } from "phosphor-react";

import { colors } from "@/styles/tokens";

function ArrowRight() {
  return <CaretRight size={32} weight="light" />;
}
function ArrowLeft() {
  return <CaretLeft size={32} weight="light" />;
}

interface Props {
  status: "completed" | "focus" | "default";
}
function Check({ status }: Props) {
  return status === "completed" ? (
    <CheckCircle weight="fill" color={colors.white} size={24} />
  ) : null;
}

const Icons = {
  ArrowRight,
  ArrowLeft,
  Check,
};
export default Icons;
