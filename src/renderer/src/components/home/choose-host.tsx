import { Button } from "@/components";
import { useRunLocalServer } from "@/services/aymurai";
import { css } from "@/styled/css";
import { Stack } from "@/styled/jsx";
import { useNavigate } from "@tanstack/react-router";
import { HardDrives, Monitor } from "phosphor-react";
import { useTranslation } from "react-i18next";

interface ChooseHostProps {
  onRemoteClick: () => void;
}
export default function ChooseHost({ onRemoteClick }: ChooseHostProps) {
  const navigate = useNavigate();
  const { run: runLocalServer, isRunning } = useRunLocalServer({
    onSuccess: () =>
      navigate({
        to: "/home/features",
      }),
  });

  const { t } = useTranslation();

  return (
    <Stack align="center" gap="12" width="[400px]">
      <img
        src={`${import.meta.env.BASE_URL}brand/aymurai-vert-darkpurple.svg`}
        alt="Logotipo AymurAI"
        width={180}
      />
      <Stack
        as="fieldset"
        aria-labelledby="connect-heading"
        align="stretch"
        gap="4"
        width="full"
      >
        <h2
          id="connect-heading"
          className={css({
            textStyle: "subtitle.sm.strong",
            textAlign: "center",
          })}
        >
          {t("home.host.howToConnect")}
        </h2>
        <Stack gap="2" align="stretch" textAlign="center">
          <Button
            onClick={runLocalServer}
            disabled={isRunning}
            isLoading={isRunning}
          >
            <Monitor weight="bold" />
            {t("home.host.optionLocal")}
          </Button>
          <p className={css({ textStyle: "subtitle.sm.default" })}>
            {t("home.host.optionOr")}
          </p>
          <Button onClick={onRemoteClick}>
            <HardDrives weight="bold" />
            {t("home.host.optionServer")}
          </Button>
        </Stack>
      </Stack>
    </Stack>
  );
}
