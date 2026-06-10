import { WHITELISTED_EXTENSIONS } from "@/constants/config";
import { css, cva } from "@/styled/css";
import { Stack, styled } from "@/styled/jsx";
import { File } from "phosphor-react";
import { useCallback, useRef, useState } from "react";

function FileIcon() {
  return (
    <styled.div
      rounded="[14px]"
      bg="bg.primary-alternative"
      color="text.lighter"
      padding="3"
    >
      <File size={48} />
    </styled.div>
  );
}

const styles = cva({
  base: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "8",

    w: "full",
    h: "[335px]",
    p: "8",

    rounded: "sm",
    border: "primary",

    bg: "[#F3F4FF]",
    cursor: "pointer",

    transitionProperty: "[border-color, background-color, box-shadow]",
    transitionTimingFunction: "default",
    transitionDuration: "normal",
  },
  variants: {
    dragging: {
      true: {
        borderColor: "brand.primary",
        bg: "bg.primary-alternative",
        boxShadow: "[0px 0px 15px 0px #3F479D66]",
      },
    },
  },
});

interface DropAreaProps {
  onDropFiles: (files: File[]) => void;
  title: string;
  description: string;
  multiple?: boolean;
}

export default function DropArea({
  onDropFiles,
  title,
  description,
  multiple = true,
}: DropAreaProps) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  const accept = WHITELISTED_EXTENSIONS.map((ext) => `.${ext}`).join(",");

  const handleFiles = useCallback(
    (fileList: FileList) => {
      const files = Array.from(fileList).filter((file) => {
        const ext = file.name.split(".").pop()?.toLowerCase();
        return ext && WHITELISTED_EXTENSIONS.includes(ext);
      });
      if (files.length > 0) onDropFiles(files);
    },
    [onDropFiles],
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) setDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setDragging(false);
      if (e.dataTransfer.files.length > 0) {
        handleFiles(e.dataTransfer.files);
      }
    },
    [handleFiles],
  );

  const handleClick = () => inputRef.current?.click();

  const handleChange: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    if (e.target.files) handleFiles(e.target.files);
  };

  return (
    <div
      className={styles({ dragging })}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <FileIcon />
      <Stack gap="1" align="center">
        <styled.p
          textStyle="subtitle.md.default"
          textAlign="center"
          whiteSpace="pre-line"
        >
          {title}
        </styled.p>
        <styled.p textStyle="subtitle.sm.default" color="text.lighter">
          {description}
        </styled.p>
      </Stack>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleChange}
        className={css({ display: "none" })}
      />
    </div>
  );
}
