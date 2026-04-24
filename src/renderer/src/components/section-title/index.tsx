import type { MouseEventHandler, ReactNode } from "react";

import { Arrow, Button, Stack, Title } from "@/components";

interface Props {
  children: ReactNode;
  onClick?: MouseEventHandler<HTMLButtonElement>;
}
export default function SectionTitle({ children, onClick }: Props) {
  return (
    <Title>
      <Stack>
        {/* Only render the button when is necessary */}
        {onClick && (
          <Button
            variant="none"
            size="s"
            css={{ p: 0, alignSelf: "center" }}
            onClick={onClick}
          >
            <Arrow.Left />
          </Button>
        )}
        {children}
      </Stack>
    </Title>
  );
}
