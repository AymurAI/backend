import Label from "@/components/label";
import { styled } from "@/styles";

export const ProgressLabel = styled(Label, {
  display: "flex",
  alignItems: "center",
  gap: "$xs",

  variants: {
    progress: {
      processing: {
        color: "$textDefault",
      },
      error: {
        color: "$errorPrimary",
      },
      stopped: {
        color: "$textLighter",
        fontStyle: "italic",
      },
      completed: {
        color: "$actionPressed",
      },
    },
  },
  defaultVariants: {
    progress: "processing",
  },
});
