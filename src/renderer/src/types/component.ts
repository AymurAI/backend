import type { ComponentPropsWithoutRef, ElementType } from "react";

/**
 * Props for any 'native' component. 'style' prop is removed by default to enforce the use of Stitches
 * @param T 'Tag' of the element
 * @param K Any prop that should be omitted from the base tag
 */
export type NativeComponent<
  T extends ElementType = "div",
  K extends string = "",
> = Omit<ComponentPropsWithoutRef<T>, "style" | K>;
