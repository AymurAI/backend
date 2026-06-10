import { styled } from "@/styled/jsx";

interface SectionTitleProps {
  children: React.ReactNode;
  className?: string;
}
export function SectionTitle({ children, className }: SectionTitleProps) {
  return (
    <styled.h1 textStyle="title.md.strong" className={className}>
      {children}
    </styled.h1>
  );
}
