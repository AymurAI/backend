import ChooseHost from "@/components/home/choose-host";
import ConnectToHost from "@/components/home/connect-to-host";
import HomeLayout from "@/layout/home";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/home/host")({
  component: RouteComponent,
});

function RouteComponent() {
  const [isLocal, setIsLocal] = useState<boolean | null>(null);

  return (
    <HomeLayout>
      {isLocal === null && (
        <ChooseHost onRemoteClick={() => setIsLocal(false)} />
      )}
      {isLocal === false && (
        <ConnectToHost onBackClick={() => setIsLocal(null)} />
      )}
    </HomeLayout>
  );
}
