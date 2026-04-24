import { styled } from "@/styles";

const Suggestion = styled("mark", {
  backgroundColor: "$primaryAlt",
  fontFamily: "$primary",
  padding: "0px $sizes$s",
  borderRadius: "$s",
  cursor: "pointer",
});

export default Suggestion;
