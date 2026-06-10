import { FileX } from "phosphor-react";

import { Checkbox, Spinner, Text } from "@/components";
import { useFileDispatch } from "@/hooks";
import type { PredictStatus } from "@/hooks/usePredict";
import { toggleSelected } from "@/reducers/file/actions";
import type { DocFile } from "@/types/file";

import { FeatureFlowEnum, parseFeatureRouteSlug } from "@/types/features";
import { useParams } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import * as S from "./FilePreview.styles";

interface Props {
  file: DocFile;
  status: PredictStatus;
}
export default function FilePreview({ file, status }: Props) {
  const { feature: featureSlug } = useParams({ from: "/$feature/preview" });
  const feature = parseFeatureRouteSlug(featureSlug);
  const { t } = useTranslation();
  const dispatch = useFileDispatch();

  const isAnonymizer = feature === FeatureFlowEnum.Anonymizer;
  const moreThanOneParagraph = file.paragraphs && file.paragraphs.length > 1;
  const isError = status === "error";
  const isPending = status === "processing";

  if (isError) {
    return (
      <S.Wrapper>
        <FileX
          size={48}
          style={{
            position: "absolute",
            top: "30%",
            left: "50%",
            transform: "translateX(-50%)",
            color: "#DC582E",
          }}
        />

        <S.FileContainer error={true} isLoading={false} />

        <Text
          css={{ color: "$colors$errorPrimary", textAlign: "center" }}
          title={file.data.name}
          size="xs"
        >
          {t("filePreview.loadError")}
        </Text>
      </S.Wrapper>
    );
  }

  if (isPending || !file.paragraphs) {
    return (
      <S.Wrapper>
        <S.FileContainer error={false} isLoading={true}>
          <Spinner />
        </S.FileContainer>
      </S.Wrapper>
    );
  }

  return (
    <S.Wrapper>
      {!isAnonymizer && moreThanOneParagraph && (
        <Checkbox
          css={{ position: "absolute", top: "$s", right: "$s" }}
          checked={file.selected}
          onChange={() => dispatch(toggleSelected(file.data.name))}
        />
      )}

      <S.FileContainer error={isError} isLoading={isPending}>
        {file.paragraphs.map((p) => (
          <S.Paragraph key={p.id} id={p.id}>
            {p.value}
          </S.Paragraph>
        ))}
      </S.FileContainer>

      <Text title={file.data.name} size="s">
        {file.data.name}
      </Text>
    </S.Wrapper>
  );
}
