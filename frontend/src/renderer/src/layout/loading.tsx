import { css } from "@/styled/css";
import { stack } from "@/styled/patterns";

const background = css(
  stack.raw({
    align: "center",
    justify: "center",
  }),
  {
    width: "screen",
    height: "screen",

    bgGradient: "primary",
  },
);
const image = css({
  animation: "pulse",
});

export default function Loading() {
  return (
    <div className={background}>
      <img
        className={image}
        src={`${import.meta.env.BASE_URL}brand/iso-white.png`}
        alt="AymurAI iso white"
        width={260}
      />
    </div>
  );
}
