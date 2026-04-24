import { Button, Input, Label, Stack, Subtitle } from "@/components";
import { useConnectToHost, useRunLocalServer } from "@/services/aymurai";
import { localStore } from "@/store/useLocal";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AxiosError } from "axios";
import { ArrowBendUpLeft, HardDrives, Monitor } from "phosphor-react";
import { useState } from "react";
import { ZodError } from "zod";

function errorMessage(err: Error): string {
  if (err instanceof AxiosError) {
    if (err.code === "ERR_NETWORK") return "No se pudo conectar al servidor";
    return "Error de conexión";
  }

  if (err instanceof ZodError) {
    return "Formato de respuesta inválido.";
  }

  return "Error desconocido";
}

export const Route = createFileRoute("/home/_layout/host")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();

  const [isLocal, setIsLocal] = useState<boolean | null>(null);

  const remoteHost = localStore.useServerHost() ?? "";
  const { setServerHost } = localStore.useServerHostActions();
  const { mutate: connectToHost, isPending, error, reset } = useConnectToHost();
  const { run: runLocalServer, isRunning } = useRunLocalServer({
    onSuccess: () =>
      navigate({
        to: "/home/features",
      }),
  });

  const handleBack = () => {
    setIsLocal(null);
  };

  const handleUseLocal = async () => {
    await runLocalServer();
  };

  const handleUseRemote = () => {
    setIsLocal(false);
  };

  const tryConnection = () => {
    connectToHost(remoteHost, {
      onSuccess: () =>
        navigate({
          to: "/home/features",
        }),
    });
  };

  const handleHostChange = (value: string) => {
    setServerHost(value);
    reset();
  };

  return (
    <Stack
      direction="column"
      spacing="m"
      align="stretch"
      css={{ width: 400, minHeight: "240px" }}
    >
      {/* Not yet selected */}
      {isLocal === null && (
        <>
          <Subtitle weight="strong" size="s" css={{ textAlign: "center" }}>
            ¿Cómo prefieres conectarte a AymurAI?
          </Subtitle>
          {/* Buttons */}
          <Stack direction="column" align="center" spacing="s">
            <Button
              onClick={handleUseLocal}
              disabled={isRunning}
              isLoading={isRunning}
            >
              <Monitor weight="bold" />
              Local
            </Button>
            <Subtitle size="s">o</Subtitle>
            <Button onClick={handleUseRemote}>
              <HardDrives weight="bold" />
              Servidor
            </Button>
          </Stack>
        </>
      )}

      {/* Remote host option selected */}
      {isLocal === false && (
        <Stack spacing="m" align="center" w-full justify="center">
          <Subtitle weight="strong" size="s" css={{ textAlign: "center" }}>
            Ingresa la dirección del servidor al que deseas conectarte
          </Subtitle>
          <Stack
            direction="column"
            spacing={"none"}
            css={{ marginBottom: "$space$m" }}
          >
            <Input
              label="Dirección del servidor"
              css={{
                minWidth: "300px",
                position: "relative",
              }}
              onChange={handleHostChange}
              defaultValue={remoteHost}
            />
            {error && (
              <div>
                <Label
                  css={{ color: "$errorPrimary", position: "absolute" }}
                  size="s"
                >
                  Error de conexión: {errorMessage(error)}
                </Label>
              </div>
            )}
          </Stack>
          <Button
            disabled={!remoteHost || isPending}
            css={{ width: "100%" }}
            onClick={tryConnection}
          >
            Conectar
          </Button>
          <Button
            css={{ width: "100%" }}
            variant={"secondary"}
            onClick={handleBack}
          >
            <ArrowBendUpLeft weight="bold" />
            Volver al inicio
          </Button>
        </Stack>
      )}
    </Stack>
  );
}
