import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from "@tanstack/react-router";

import { ThemeProvider } from "@/components";
import * as TanstackReactQuery from "@/features/ReactQueryProvider";

// Import the generated route tree
import { routeTree } from "./routeTree.gen";

const TanStackQueryProviderContext = TanstackReactQuery.getContext();

// Create a new router instance
const memoryHistory = createMemoryHistory({
  initialEntries: ["/home/host"], // Pass your initial url
});
const router = createRouter({
  routeTree,
  history: memoryHistory,
  context: { ...TanStackQueryProviderContext },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export default function App() {
  return (
    <TanstackReactQuery.Provider {...TanStackQueryProviderContext}>
      {/* Stitches global styles */}
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </TanstackReactQuery.Provider>
  );
}
