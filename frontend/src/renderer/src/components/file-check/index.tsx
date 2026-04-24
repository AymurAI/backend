import { Text } from "@/components";
import ErrorText from "./ErrorText";
import { Card, Wrapper } from "./FileCheck.styles";
import Icon from "./Icon";

interface Props {
  fileName: string;
  hasError?: boolean;
  isLoading?: boolean;
}
export default function FileCheck({
  fileName,
  hasError = false,
  isLoading = false,
}: Props) {
  return (
    <Wrapper>
      <Card {...{ hasError }}>
        <Icon {...{ hasError, isLoading }} />
      </Card>
      <Text>{fileName}</Text>
      {hasError && (
        <ErrorText>
          Error de guardado <br /> Volvé a cargar el archivo
        </ErrorText>
      )}
    </Wrapper>
  );
}
