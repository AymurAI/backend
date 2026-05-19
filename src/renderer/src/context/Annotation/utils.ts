/**
 * Check if the selection contains another Node.
 * @param selection The current selection.
 * @returns `true` if the selection contains a Node, `false` otherwise.
 */
export const selectionHasNodes = (selection: Selection | null): boolean => {
  if (!selection) return false;

  const container = document.createElement("div");

  for (let i = 0; i < selection.rangeCount; ++i) {
    container.appendChild(selection.getRangeAt(i).cloneContents());
  }

  return new RegExp(/<.*?>/g).test(container.innerHTML);
};

/**
 * Checks if the node is can be annotated. It checks the type of Node and its parentElement (if it's a span).
 * @param node Node from the selection
 * @returns `true` if the node is a valid node, `false` otherwise.
 */
export const isValidNode = (node: Node | null): node is Node =>
  !!node &&
  node instanceof Text &&
  node.parentElement instanceof HTMLSpanElement;

/**
 * Get the start and end boundaries of the selection. Reverses the boundaries if the selection is made from right to left.
 * @param selection Selection object
 * @returns The start and end boundaries of the selection
 */
export const getBoundaries = (selection: Selection): [number, number] => {
  const start = selection.anchorOffset;
  const end = selection.focusOffset;
  return [start, end].sort((a, b) => a - b) as [number, number];
};

/**
 * Get the id of the paragraph where the selection is made.
 * @param selection Selection object
 * @returns The id of the paragraph where the selection is made
 */
export const paragraphIdFromSelection = (selection: Selection) => {
  // This is evaluated after the isValidNode check, so we can safely assume that the parentElement is a span
  const span = selection.anchorNode?.parentElement;
  const paragraph = span?.parentElement as HTMLParagraphElement;

  return paragraph.id;
};

function closestOffsetElement(node: Node | null): HTMLElement | null {
  const element = node instanceof HTMLElement ? node : node?.parentElement;
  return element?.closest<HTMLElement>("[data-start]") ?? null;
}

function offsetWithinElement(
  element: HTMLElement,
  container: Node,
  offset: number,
): number | null {
  const range = document.createRange();
  range.setStart(element, 0);

  try {
    range.setEnd(container, offset);
  } catch {
    return null;
  }

  return range.toString().length;
}

export function getSelectionAnnotationRange(selection: Selection): {
  paragraphId: string;
  start: number;
  end: number;
  text: string;
} | null {
  if (selection.rangeCount === 0 || selection.type !== "Range") return null;

  const range = selection.getRangeAt(0);
  const text = range.toString();
  if (!text) return null;

  const startElement = closestOffsetElement(range.startContainer);
  const endElement = closestOffsetElement(range.endContainer);
  if (!startElement || !endElement) return null;

  const startParagraph = startElement.closest<HTMLParagraphElement>("p[id]");
  const endParagraph = endElement.closest<HTMLParagraphElement>("p[id]");
  if (!startParagraph || !endParagraph || startParagraph.id !== endParagraph.id)
    return null;

  const startBase = Number(startElement.dataset.start ?? 0);
  const endBase = Number(endElement.dataset.start ?? 0);
  const startOffset = offsetWithinElement(
    startElement,
    range.startContainer,
    range.startOffset,
  );
  const endOffset = offsetWithinElement(
    endElement,
    range.endContainer,
    range.endOffset,
  );

  if (startOffset === null || endOffset === null) return null;

  return {
    paragraphId: startParagraph.id,
    start: startBase + startOffset,
    end: endBase + endOffset,
    text,
  };
}

/**
 * Find all indexes where a search string appears in a text.
 * @param text The text to search in
 * @param search The string to search for
 * @returns An array of indexes where the search string appears
 */
export const findSearchIndexes = (text: string, search: string): number[] => {
  const indexes: number[] = [];
  const lowerText = text.toLowerCase();
  const lowerSearch = search.toLowerCase();
  let index = lowerText.indexOf(lowerSearch);

  while (index !== -1) {
    indexes.push(index);
    index = lowerText.indexOf(lowerSearch, index + 1);
  }

  return indexes;
};
