import BuiltBy from "@/components/brand/built-by";
import { css } from "@/styled/css";
import { stack } from "@/styled/patterns";

const background = css({
  display: "flex",

  bg: "bg.primary-highlight",
  height: "screen",
  width: "screen",

  p: "8",
});
const inner = css(
  stack.raw({ justify: "center", align: "center", gap: "12" }),
  {
    pos: "relative",

    bg: "bg.secondary",
    border: "primary",

    width: "full",
    height: "full",
  },
);

const builtBy = css({
  pos: "absolute",
  bottom: "16", // 64px
});

interface HomeLayoutProps {
  children?: React.ReactNode;
}
export default function HomeLayout({ children }: HomeLayoutProps) {
  return (
    <main className={background}>
      <div className={inner}>
        {children}

        {/* Floating content below */}
        <div className={builtBy}>
          <BuiltBy />
        </div>
      </div>
    </main>
  );
}
