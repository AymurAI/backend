# Filesystem

Las funcionalidades de _NodeJS_ sobre el _filesystem_ se aprovechan para poder
leer y escribir sobre el set de datos de forma local y offline en la
computadora. Además, también se generan reportes que ayudan a reentrenar el
modelo de inteligencia artificial.

## Ubicación

Las ubicaciones para los archivos de exportación se encuentran en la carpeta:

```ts
// Ejemplo windows: C:\Users\[Usuario]\Documents\AymurAI
const EXPORTS_FOLDER = path.resolve(homedir(), 'Documents/AymurAI');
```

## API

Para poder formar un canal de comunicación entre la aplicación de _React_
y _Electron_, se utilizan los [_preload scripts_](https://www.electronjs.org/docs/latest/tutorial/tutorial-preload)
para exponer una _API_ que permita la lectura y escritura de archivos.

De esta forma el _frontend_ podría acceder a las funcionalidades de _NodeJS_
utilizando `window.filesystem.excel.read` y `window.filesystem.excel.write` por ejemplo.
Estas funciones fueron definidas dentro de los archivos de _Electron_.

Para el caso de los reportes se utiliza `window.filesystem.feedback.export`.

> 📚 Se pueden encontrar estos scripts y más yendo al
[script preloader del proyecto.](../../renderer/preload.ts)

## Tipo de archivo

### Set de datos

El set de datos se exporta en formato _Excel_ con extensión `.xlsx`.

```ts
const FILENAME = 'set_de_datos.xlsx';
// Ejemplo windows: C:/Users/[Usuario]/Documents/AymurAI/set_de_datos.xlsx
const PATH = `${EXPORTS_FOLDER}/${FILENAME}`;
```

Desde el frontend se utiliza la librería [_ExcelJS_](https://www.npmjs.com/package/exceljs)
que permite leer un archivo `.xlsx`, modificarlo en memoria y luego escribir los
cambios en el filesystem, apoyándose en las funcionalidades de _NodeJS_.

```ts
import { Workbook } from 'exceljs';

// Ejemplo de escritura de archivo
async function writeXLSX(workbook: Workbook) {
  const buffer = (await workbook.xlsx.writeBuffer()) as Buffer;

  return window.filesystem.excel.write(buffer);
}
```

### Reportes / Feedback

El reporte se exporta en formato _JSON_ con extensión `.json`. Utiliza el nombre
del archivo procesado y la fecha para generar el nombre del archivo.

```ts
const FEEDBACK_FOLDER = `${EXPORTS_FOLDER}/feedback`;
const FILENAME = `${FEEDBACK_FOLDER}/{name}-{date}.json`
```

Se escribe en el filesystem de forma tradicional.
