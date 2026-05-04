import FeaturesMenu from "@/components/features-menu";
import FinishAnonymizer from "@/components/finish/finish-anonymizer";
import FinishDataset from "@/components/finish/finish-dataset";
import Stepper from "@/components/home/stepper";
import HowItWorksModal from "@/components/how-it-works-modal";
import Header from "@/components/layout/header";
import RequireFile from "@/features/RequireFile";
import { useFileDispatch } from "@/hooks";
import { removeAllFiles } from "@/reducers/file/actions";
import { useTutorialSeen } from "@/store/useLocal";
import { HStack } from "@/styled/jsx";
import { FeatureFlowEnum, featureNamespace } from "@/types/features";
import {
  createFileRoute,
  useNavigate,
  useParams,
} from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

export const Route = createFileRoute("/app/$feature/finish")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const params = useParams({ from: "/app/$feature/finish" });
  const { feature } = params;

  const { t } = useTranslation(featureNamespace[feature]);
  const tutorialSeen = useTutorialSeen(feature);
  const dispatch = useFileDispatch();

  const handleRestart = () => {
    dispatch(removeAllFiles());
    navigate({ to: "/app/$feature/onboarding", params });
  };

  return (
    <RequireFile>
      <Header
        title={t("title")}
        center={
          feature === FeatureFlowEnum.Dataset ? (
            <Stepper currentStep={4} />
          ) : undefined
        }
        right={
          <HStack>
            {tutorialSeen && <HowItWorksModal feature={feature} />}
            <FeaturesMenu />
          </HStack>
        }
      />

      {feature === FeatureFlowEnum.Dataset ? (
        <FinishDataset onRestart={handleRestart} />
      ) : (
        <FinishAnonymizer onRestart={handleRestart} />
      )}
    </RequireFile>
  );
}
