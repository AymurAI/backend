# AymurAI

La AI está documentada en su swagger accediendo directamente a `{{AYMURAI_URL}}/docs` una vez que el servidor está corriendo.

> 💡 Si la AI está corriendo en la red LAN o bajo un ngrok, se debe cambiar la ruta.

## Uso

Para usar la AI en la aplicación se ponen a disposición cuatro funciones en la carpeta `/src/services/aymurai`:

- `document-extract.ts`: obtiene cada párrafo del documento en texto plano para poder renderizarlo en la aplicación.
- `predict.ts`: genera predicciones sobre los párrafos previamente extraídos.
- `anonymize.ts`: permite generar un archivo `.odt` con las anotaciones hechas por el usuario y la AI.
- `health-check.ts`: se utiliza para verificar si la api está funcionando de manera correcta. Se utiliza en la pantalla de inicio.
