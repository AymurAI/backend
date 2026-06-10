import {
  MutationCache,
  QueryClient,
  QueryClientProvider,
  matchQuery,
} from "@tanstack/react-query";

export function getContext() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: false,
      },
    },
    mutationCache: new MutationCache({
      onSettled: async (_data, _err, _vars, _ctx, mutation) => {
        if (!mutation.meta) return;
        const { invalidates, awaits } = mutation.meta;

        const promise = queryClient.invalidateQueries({
          predicate: (query) => {
            if (typeof invalidates === "boolean") return invalidates;

            return (
              invalidates?.some((queryKey) =>
                matchQuery({ queryKey }, query),
              ) ?? false
            );
          },
        });

        if (awaits) {
          await promise;
        }
      },
    }),
  });

  return {
    queryClient,
  };
}

export function Provider({
  children,
  queryClient,
}: {
  children: React.ReactNode;
  queryClient: QueryClient;
}) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
