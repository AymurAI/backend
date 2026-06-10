import { DATAGENERO_URL } from "@/constants/config";
import { styled } from "@/styled/jsx";
import { type StackStyles, stack } from "@/styled/patterns";
import { useTranslation } from "react-i18next";

interface BuiltByProps {
  size?: number;
  gap?: StackStyles["gap"];
}
export default function BuiltBy({ size = 150, gap = "2" }: BuiltByProps) {
  const { t } = useTranslation();
  return (
    <a
      className={stack({ gap, align: "center" })}
      href={DATAGENERO_URL}
      target="_blank"
      rel="noreferrer"
    >
      <styled.p textStyle="label.sm.default" color="text.lighter">
        {t("platformBuiltBy")}
      </styled.p>
      <img
        src={`${import.meta.env.BASE_URL}brand/datagenero.svg`}
        alt="DataGenero isologo"
        width={size}
      />
    </a>
  );
}
