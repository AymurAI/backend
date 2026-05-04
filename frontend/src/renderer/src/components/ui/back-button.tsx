import { css, cx } from "@/styled/css";
import { createLink } from "@tanstack/react-router";
import { ArrowLeft } from "phosphor-react";

const link = css({
  cursor: "pointer",
});

const BackButton = createLink(
  ({ className, children: _, ref, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { ref?: React.Ref<HTMLAnchorElement> }) => (
    <a ref={ref} className={cx(className, link)} {...props}>
      <ArrowLeft size={32} />
    </a>
  ),
);

export default BackButton;
