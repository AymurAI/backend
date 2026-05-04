import { useState } from "react";

import { css } from "@/styled/css";
import { HStack, Stack, styled } from "@/styled/jsx";
import { CaretUp } from "phosphor-react";

const header = css({
  cursor: "pointer",
});

const caret = css({
  transition: "transform",
  transitionDuration: "[0.2s]",
  transitionTimingFunction: "[ease]",
});

const contentOuter = css({
  display: "grid",
  transition: "[grid-template-rows]",
  transitionDuration: "[0.3s]",
  transitionTimingFunction: "[ease]",
});

const contentInner = css({
  minHeight: "[0]",
  overflow: "hidden",
});

interface SectionProps {
  children: React.ReactNode;
  title: string;
}
export default function LabelManagerSection({
  title: sectionTitle,
  children,
}: SectionProps) {
  const [open, setOpen] = useState(true);

  return (
    <Stack gap="6">
      <HStack
        gap="2"
        className={header}
        onClick={() => setOpen((prev) => !prev)}
      >
        <div
          className={caret}
          style={{ transform: open ? "rotate(0deg)" : "rotate(180deg)" }}
        >
          <CaretUp size={24} />
        </div>
        <styled.p textStyle="subtitle.md.strong" color="text.default">
          {sectionTitle}
        </styled.p>
      </HStack>
      <div
        className={contentOuter}
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className={contentInner}>{children}</div>
      </div>
    </Stack>
  );
}
