import { Button, Label, Stack, Subtitle } from "@/components";
import { Outlet, useNavigate } from "@tanstack/react-router";
import { ArrowBendUpLeft } from "phosphor-react";
import * as S from "./Login.styles";

interface LoginLayoutProps {
  canGoBack?: boolean;
}
export default function LoginLayout({ canGoBack = false }: LoginLayoutProps) {
  const navigate = useNavigate();

  const handleGoBack = () => {
    navigate({ to: "/home" });
  };
  return (
    <S.Background>
      <S.Container>
        <S.MainContent direction="column" justify="center" align="center">
          {/*  Title */}
          <Stack direction="column" align="center">
            <Subtitle>Te damos la bienvenida a</Subtitle>
            <S.Logo src="brand/aymurai-vert.png" alt="AymurAI" />
          </Stack>

          {/* Outlet: buttons and actions to proceed to the platform */}
          <Outlet />

          {canGoBack && (
            <Button variant="secondary" onClick={handleGoBack}>
              <ArrowBendUpLeft weight="bold" />
              Volver al inicio
            </Button>
          )}
        </S.MainContent>

        {/* DataGenero info */}
        <Stack direction="column" align="center" spacing="none">
          <Label size="s">Plataforma hecha por</Label>
          <a
            href="https://www.datagenero.org/"
            target="_blank"
            rel="noreferrer"
          >
            <img src="brand/data-genero.png" alt="DataGenero" width={170} />
          </a>
        </Stack>
      </S.Container>
    </S.Background>
  );
}
