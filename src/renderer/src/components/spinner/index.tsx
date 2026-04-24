import { keyframes, styled } from "@/styles";

const spin = keyframes({
  "0%": { transform: "rotate(0deg)" },
  "100%": { transform: "rotate(360deg)" },
});

const SVG = styled("svg", {
  animation: `${spin} 1s linear infinite`,
});

export default function Spinner() {
  return (
    <SVG width={48} height={48} fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M24 42c9.941 0 18-8.059 18-18S33.941 6 24 6 6 14.059 6 24s8.059 18 18 18Z"
        stroke="#E6E8FF"
        strokeWidth={3.25}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M42 24c0-9.941-8.059-18-18-18S6 14.059 6 24s8.059 18 18 18"
        stroke="url(#a)"
        strokeWidth={3.25}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <defs>
        <linearGradient
          id="a"
          x1={42}
          y1={20.5}
          x2={22}
          y2={42}
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#3F479D" />
          <stop offset={1} stopColor="#3F479D" stopOpacity={0} />
        </linearGradient>
      </defs>
    </SVG>
  );
}
