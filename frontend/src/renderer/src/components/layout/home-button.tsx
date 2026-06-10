import { css } from "@/styled/css";
import { House } from "phosphor-react";
import Link from "../ui/link";

export default function HomeButton() {
  return (
    <Link
      to="/home/features"
      size="icon-sm"
      className={css({ p: "0.5" })}
      aria-label="Volver al inicio"
    >
      <House size={32} />
    </Link>
  );
}
