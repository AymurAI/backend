import { css, sva } from "@/styled/css";
import { stack } from "@/styled/patterns";
import { useTranslation } from "react-i18next";

const stepper = css({
  ...stack.raw({ align: "center", direction: "row" }),
});

const step = sva({
  slots: ["container", "circle", "text"],
  base: {
    container: stack.raw({ direction: "row", align: "center", gap: "2" }),
    circle: {
      ...stack.raw({ direction: "row", align: "center", justify: "center" }),
      rounded: "full",
      height: "9",
      width: "9",
      textStyle: "cta.md.strong",
    },
    text: {
      color: "text.default",
      textStyle: "label.md.default",
      display: "none",
      visibility: "hidden",
    },
  },
  variants: {
    status: {
      complete: {
        circle: {
          color: "text.onbutton-alternative",
          bg: "action.alt-default",
        },
      },
      pending: {
        circle: {
          color: "text.onbutton-default",
          bg: "action.disabled",
        },
      },
      in_progress: {
        circle: {
          color: "text.onbutton-default",
          bg: "action.default",
          border: "primary-alt",
        },
        text: { display: "inline", visibility: "visible" },
      },
    },
  },
});

type StepStatus = "complete" | "pending" | "in_progress";
interface StepProps {
  children: string;
  status: StepStatus;
  number: number;
}
function Step({ children, status, number }: StepProps) {
  const classes = step({ status });
  // Used to hide text from visuals but expose to screen readers
  const srOnly = css({
    srOnly: true,
  });

  return (
    <div className={classes.container}>
      <div className={classes.circle} aria-hidden="true">
        {number}
      </div>
      <span className={srOnly}>
        Paso {number}: {children}
      </span>
      <span className={classes.text} aria-hidden="true">
        {children}
      </span>
    </div>
  );
}

interface StepperProps {
  currentStep: number;
}
export default function Stepper({ currentStep }: StepperProps) {
  const { t } = useTranslation();

  const status = (step: number): StepStatus => {
    if (step === currentStep) return "in_progress";
    if (step > currentStep) return "pending";
    return "complete";
  };

  return (
    <div className={stepper}>
      <Step number={1} status={status(1)}>
        {t("stepper.selection")}
      </Step>
      <Step number={2} status={status(2)}>
        {t("stepper.extraction")}
      </Step>
      <Step number={3} status={status(3)}>
        {t("stepper.validation")}
      </Step>
      <Step number={4} status={status(4)}>
        {t("stepper.finalization")}
      </Step>
    </div>
  );
}
