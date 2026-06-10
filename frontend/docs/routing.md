# Routing

El proyecto usa `react-router-dom` para manejar las rutas de la aplicación. Las rutas se definen en el archivo `src/index.tsx` y se deben agregar en el objeto `router` de la siguiente manera:

```jsx
const router = createRouter([
  {
    // Main as a layout element
    path: '/',
    element: <MainLayout />,
    children: [
      { path: 'onboarding', element: <Onboarding /> },
      { path: 'preview', element: <Preview /> },
      { path: 'process', element: <Process /> },
    ],
  },
  {
    path: '/login',
    element: <Login></Login>,
  },
]);
```

Al ser un proyecto basado en _Electron_, el router que utilizamos no es el mismo que se usa en un proyecto web normal. Para este caso, usamos un [_memory router_](https://reactrouter.com/en/main/routers/create-memory-router#creatememoryrouter) que mantiene en memoria el history stack de las rutas.

## Protección de rutas

Existen dos high order components que se encargan de proteger las rutas de la aplicación dependiendo qué se requiere:

- `withAuthProtection`: verifica si el usuario está autenticado y redirige a `/login` si no lo está.
