import { styled } from "@/styles";

const ErrorText = styled("p", {
  fontStyle: "italic",
  color: "$errorPrimary",
  textAlign: "center",
  fontSize: "$subtitleSm",
  lineHeight: "$subtitleSm",
  fontWeight: "$default",
  whiteSpace: "pre-line",
});

export default ErrorText;
