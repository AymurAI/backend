import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import { z } from "zod";

import { ProfileInfo, Stepper, Title } from "@/components";
import FileProvider from "@/context/File";
import { Header, Layout } from "@/layout/main";
import { Feature } from "@/types/features";

// Validation schema for feature parameter
const featureParamSchema = z.object({
  feature: z.enum([Feature.Dataset, Feature.Anonymizer]),
});

export const Route = createFileRoute("/app/$feature")({
  // Parse and validate params
  params: {
    parse: (params) => {
      try {
        return featureParamSchema.parse(params);
      } catch {
        throw redirect({ to: "/home/features" });
      }
    },
    stringify: (params) => params,
  },
  component: AppLayoutRoute,
});

function AppLayoutRoute() {
  const { feature } = Route.useParams();

  // Determine title based on feature
  const title = feature === Feature.Dataset ? "Set de datos" : "Anonimizador";

  return (
    <Layout>
      <Header>
        {/* Title & Profile picture & Logout */}
        <Title weight="strong" css={{ fontSize: 24 }}>
          AymurAI {title}
        </Title>
        <Stepper />
        <ProfileInfo />
      </Header>

      <FileProvider>
        {/* Child routes render here */}
        <Outlet />
      </FileProvider>
    </Layout>
  );
}
