import { cva, cx } from "@/styled/css";
import { stack } from "@/styled/patterns";

const content = cva({
  base: {
    flex: "1",
    minH: "0",

    width: "full",
    overflowY: "auto",

    bg: "bg.primary",
  },
  variants: {
    full: {
      true: {},
      false: {
        ...stack.raw({ align: "center", gap: "0" }),

        pt: { base: "6", xl: "16" },
        px: "8",

        "& > div.spacing": {
          width: "full",
          maxWidth: "5xl",
        },
      },
    },
  },
  defaultVariants: {
    full: false,
  },
});

interface MainContentProps {
  children: React.ReactNode;
  full?: boolean;
}
export default function MainContent({
  children,
  full = false,
}: MainContentProps) {
  return (
    <main className={cx(content({ full }))}>
      <div className="spacing">{children}</div>
    </main>
  );
}
