import BuiltBy from "@/components/brand/built-by";
import { css } from "@/styled/css";

const background = css({
  display: "flex",

  bg: "bg.primary-highlight",
  height: "screen",
  width: "screen",

  p: "8",
});

const inner = css({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",

  pos: "relative",

  bg: "bg.secondary",
  border: "primary",

  width: "full",
  height: "full",

  overflowY: "auto",
  pb: "8",
});

const childrenArea = css({
  flex: "1",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
});

interface HomeLayoutProps {
  children?: React.ReactNode;
}
export default function HomeLayout({ children }: HomeLayoutProps) {
  return (
    <main className={background}>
      <div className={inner}>
        <div className={childrenArea}>{children}</div>
        <BuiltBy />
      </div>
    </main>
  );
}
