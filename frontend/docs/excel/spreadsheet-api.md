# Google Spreadsheet API

Para leer y escribir de forma remota en una hoja de cálculo de _Google Sheets_ se
utiliza la [REST API](https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets)
provista por _Google_.

## Ubicación

La ubicación del dataset está definida de forma __estática__ dentro del
[código](../../src/utils/config.ts). Esto significa que para poder acceder a
este archivo se necesita tener accesos de lectura/escritura sobre el archivo.

## Implementación

Dentro del proyecto se crearon una serie de funciones que ayudan a interactuar
con la API de _Google Sheets_. En general lo que hacen es _envolver_ las
llamadas a la _REST API_ utilizando el _access token_ provisto por el
[proceso de autenticación](../authentication.md).

> Estas funciones se pueden encontrar dentro de la carpeta de
[servicios de google](../../src/services/google/).

Por ejemplo, para obtener el contenido de una hoja de cálculo se utiliza la
función:

```ts
import google from 'services/google';

await google(authToken).spreadsheet(id).range('A1:B2');
```
