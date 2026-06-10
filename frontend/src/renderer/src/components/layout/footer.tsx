import { css, cx } from "@/styled/css";
import BuiltBy from "../brand/built-by";

const content = css({
  display: "flex",
  flexDirection: "row",
  alignItems: "center",

  borderTop: "primary",
  px: "12",
  py: "6",
});
const childrenContainer = css({
  flex: "1",
  display: "flex",
  justifyContent: "flex-end",
});

interface FooterProps {
  withBuiltBy?: boolean;
  children?: React.ReactNode;
  className?: string;
}
export default function Footer({
  withBuiltBy,
  children,
  className,
}: FooterProps) {
  return (
    <footer className={cx(content, className)}>
      {withBuiltBy && <BuiltBy size={120} gap="0" />}
      <div className={childrenContainer}>{children}</div>
    </footer>
  );
}
