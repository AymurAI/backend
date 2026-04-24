import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { SEARCH_MIN_LENGTH } from "../annotations";

const SCROLL_DEBOUNCE = 300;

const find = () => document.querySelectorAll("mark.search");

const scrollToComponent = (n: number) => {
  const index = n - 1;
  const components = find();
  if (components.length === 0 || components.length < n) return;

  components[index].scrollIntoView({
    behavior: "smooth",
    block: "center",
    inline: "nearest",
  });
};

/**
 * Hook to scroll to the searched word
 * @param count Count of words found in the html
 */
export const useScroll = (word: string) => {
  // Always start the counter on 1
  const [count, setCount] = useState(1);
  const [matchesCount, setMatchesCount] = useState(0);
  const timer = useRef<number | null>(null);

  // Calculated values
  const isSearching = word.length >= SEARCH_MIN_LENGTH;

  // Handlers
  const clearTimer = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };

  const next = () => {
    if (count === matchesCount) return;
    setCount((prev) => prev + 1);
  };

  const previous = () => {
    if (count === 1) return;
    setCount((prev) => prev - 1);
  };

  /**
   * Scroll on word change
   */
  useEffect(() => {
    if (word.length >= 2) {
      setTimeout(() => scrollToComponent(1), SCROLL_DEBOUNCE);
    }
    return () => clearTimer();
  }, [word]);

  /**
   * Scroll on count change. That is, whenever the user clicks next or previous
   */
  useEffect(() => {
    setTimeout(() => scrollToComponent(count), SCROLL_DEBOUNCE);
    return () => clearTimer();
  }, [count]);

  /**
   * Update the matches count whenever the word changes
   */
  useLayoutEffect(() => {
    const getMatchCount = () => {
      if (!isSearching) return 0;

      setCount(1);
      return find().length;
    };

    setMatchesCount(getMatchCount());
  }, [word, isSearching]);

  return { next, previous, count, matchesCount, isSearching };
};
