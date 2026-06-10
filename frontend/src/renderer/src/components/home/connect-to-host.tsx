import { useConnectToHost } from "@/services/aymurai";
import * as localStore from "@/store/useLocal";
import { css } from "@/styled/css";
import { Stack } from "@/styled/jsx";
import { useNavigate } from "@tanstack/react-router";
import { AxiosError } from "axios";
import { ArrowLeft } from "phosphor-react";
import {
  type ChangeEventHandler,
  type SubmitEventHandler,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { ZodError } from "zod";
import Button from "../ui/button";
import Input from "../ui/input";

const BackButton = ({ onClick }: { onClick: () => void }) => (
  <button
    className={css({
      cursor: "pointer",
      position: "absolute",
      top: "8",
      left: "8",
    })}
    type="button"
    onClick={onClick}
  >
    <ArrowLeft size={32} />
  </button>
);

interface ConnectToHostProps {
  onBackClick: () => void;
}
export default function ConnectToHost({ onBackClick }: ConnectToHostProps) {
  const navigate = useNavigate();
  const remoteHost = localStore.useServerHost() ?? "";
  const { setServerHost } = localStore.useServerHostActions();
  const { t } = useTranslation();

  const [host, setHost] = useState(remoteHost);

  const { mutate: connectToHost, isPending, error, reset } = useConnectToHost();

  const handleChange: ChangeEventHandler<HTMLInputElement> = (e) => {
    setHost(e.target.value);
    reset();
  };

  const tryConnection: SubmitEventHandler = (e) => {
    e.preventDefault();

    connectToHost(host, {
      onSuccess: () => {
        setServerHost(host);
        navigate({
          to: "/home/features",
        });
      },
    });
  };

  const errorMessage = (err: Error | null): string => {
    console.error(err);
    if (err instanceof AxiosError) {
      if (err.code === "ERR_NETWORK") return t("home.host.errors.network");
      return t("home.host.errors.connection");
    }

    if (err instanceof ZodError) {
      return t("home.host.errors.invalidResponse");
    }

    if (err instanceof TypeError) {
      return t("home.host.errors.invalidUrl");
    }

    return t("home.host.errors.unknown");
  };

  return (
    <>
      <BackButton onClick={onBackClick} />
      <form onSubmit={tryConnection}>
        <Stack justify="center" gap="3" width="[400px]">
          <h2 className={css({ textStyle: "subtitle.sm.strong" })}>
            {t("home.host.connectServerExplanation")}
          </h2>

          <Stack gap="1" width="full">
            <Input
              label={t("home.host.connectServerLabel")}
              placeholder="http://"
              value={host}
              onChange={handleChange}
              error={error ? errorMessage(error) : undefined}
            />
          </Stack>

          <Button type="submit" isLoading={isPending}>
            {t("home.host.connectServerSubmit")}
          </Button>
        </Stack>
      </form>
    </>
  );
}
