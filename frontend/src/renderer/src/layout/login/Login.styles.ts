import { Stack } from "@/components";
import { styled } from "@/styles";

/**
 * Adds the `$secondary` colors
 */
export const Background = styled("main", {
  bg: "$secondary",

  display: "flex",

  height: "100vh",
});

/**
 * Contains the Login elements and adds the margin
 */
export const Container = styled("div", {
  bg: "$white",

  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  alignItems: "center",
  flex: 1,
  gap: "$l",

  padding: "$l",
  margin: "$xl",

  b: "1px solid $borderPrimary",
});

export const MainContent = styled(Stack, {
  flex: 1,
});

export const Logo = styled("img", {
  width: 250,
  mt: -32,
  mb: -16,
});
