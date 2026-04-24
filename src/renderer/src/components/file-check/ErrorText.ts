import { styled } from "@/styles";

const ErrorText = styled("p", {
  fontStyle: "italic",
  color: "$errorPrimary",
  textAlign: "center",
  fontSize: "$subtitleSm",
  lineHeight: "$subtitleSm",
  fontWeight: "$default",
});

export default ErrorText;
