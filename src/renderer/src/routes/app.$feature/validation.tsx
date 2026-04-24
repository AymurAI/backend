import { Button, FileAnnotator, Grid, ValidateDataset } from "@/components";
import { useFiles } from "@/hooks";
import { Footer } from "@/layout/main";
import { Feature } from "@/types/features";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";

export const Route = createFileRoute("/app/$feature/validation")({
  component: ValidationRoute,
});

function ValidateAnonymizer() {
  const { feature } = useParams({
    from: "/app/$feature/validation",
  });
  const file = useFiles()[0]!;
  const navigate = useNavigate();

  const handleContinue = () =>
    navigate({ to: "/app/$feature/finish", params: { feature } });

  return (
    <>
      <Grid
        columns={1}
        spacing="none"
        justify="stretch"
        align="stretch"
        css={{ overflow: "hidden" }}
      >
        <FileAnnotator {...{ file }} isAnnotable />
      </Grid>

      <Footer
        css={{
          justifyContent: "flex-end",
          gap: 150,
        }}
      >
        <Button size="l" onClick={handleContinue}>
          Anonimizar documento
        </Button>
      </Footer>
    </>
  );
}

function ValidationRoute() {
  const { feature } = Route.useParams();

  if (feature === Feature.Dataset) return <ValidateDataset />;
  return <ValidateAnonymizer />;
}
