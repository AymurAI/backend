import { Text } from "@/components";
import ErrorText from "./ErrorText";
import { Card, Wrapper } from "./FileCheck.styles";
import Icon from "./Icon";

interface Props {
  fileName: string;
  hasError?: boolean;
  isLoading?: boolean;
  errorMessage?: string;
}
export default function FileCheck({
  fileName,
  hasError = false,
  isLoading = false,
  errorMessage = "Error de guardado\nVolvé a cargar el archivo",
}: Props) {
  return (
    <Wrapper>
      <Card {...{ hasError }}>
        <Icon {...{ hasError, isLoading }} />
      </Card>
      <Text>{fileName}</Text>
      {hasError && <ErrorText>{errorMessage}</ErrorText>}
    </Wrapper>
  );
}
