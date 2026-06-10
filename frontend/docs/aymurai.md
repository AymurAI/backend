# AymurAI

## Tecnologías principales

AymurAI es una aplicación de escritorio basada en
[NodeJS](https://nodejs.org/en/) que utiliza tres principales tecnologías:

- **[Electron.JS](https://www.electronjs.org/)**: elegido por su capacidad de
  poder crear aplicaciones multiplataforma, Electron nos permite crear
  aplicaciones web que pueden ser distribuidas sin la necesidad de tener un
  browser preinstalado
- **[React](https://reactjs.org/)**: elegido por su versatilidad, ReactJS es un
  web framework que nos permite crear todo tipo de web apps
- **[TypeScript](https://www.typescriptlang.org/)**: un _superset_ (es
  decir, que añade features al original, pero sin modificar sus principios) de
  _JavaScript_ que permite crear aplicaciones con la seguridad de que el flujo de
  datos respeta un orden particular y definido

Esta combinación de frameworks y lenguajes resulta muy eficiente ya que se puede
crear una web app desde cero, distribuible facilmente y multiplataforma, y con
herramientas incluidas para poder realizar un desarrollo confiable y
con la menor cantidad de _bugs_ posibles.

Además, el uso de _Electron_ nos permite combinar las ventajas de usar _NodeJS_
y todos sus paquetes como proceso principal y luego usar un browser levantado
por el mismo _Electron_ basado en
[Chromium](https://www.chromium.org/chromium-projects/) para utilizar las
[Web APIs](https://developer.mozilla.org/en-US/docs/Web/API) que podemos
encontrar en cualquier browser.

## Otras tecnologías

Además de las tecnologías principales anteriormente mencionadas se usaron:

- **[Stitches](https://stitches.dev/)**: elegida como librería de estilos, nos
  permite configurar toda una lista de _tokens_ que pueden ser utilizados a lo
  largo de toda la aplicación manteniendo una alta consistencia entre los estilos.
  Esto nos permite configurar y estandarizar colores, espaciados, sombras, etc además
  de darnos la posibilidad de trabajar con _styled components_ para un
  ágil desarrollo
- **[Google OAuth2](https://developers.google.com/identity/protocols/oauth2)**:
  sistema de autenticación de usuarios basado en [OAuth](https://oauth.net/) que
  nos permite tener un acceso total a las APIs de _Google_, permitiéndonos editar
  en tiempo real documentos _Spreadsheet_. Sin este sistema de autenticación no se
  podría obtener el token que nos permite interaccionar con las APIs

## Estructura

Se dividió la aplicación en 6 páginas, que se presentan en el siguiente orden:

1. **Login**: página en la que se selecciona cómo conectarse a la API de AyMurai y cuál funcionalidad se desea utilizar (anonimizador o set de datos)
1. **Onboarding**: se nos muestra una guía sobre el funcionamiento de la
   aplicación y los pasos a seguir para poder realizar la validación de nuestros
   archivos. Es en este paso donde podremos cargar nuestros documentos
1. **Preview**: obtendremos una vista previa de los escritos cargados en la
   página anterior con la oportunidad de cargar nuevos documentos si es necesario.
   Es aquí donde podemos decidir cuáles son los archivos finales que serán
   procesados por la inteligencia artificial
1. **Process**: página de procesamiento. En este paso se realiza la consulta
   a la inteligencia artificial para obtener las predicciones correspondientes
   a cada archivo. Esto puede tardar un poco. Podemos detener el procesamiento
   de los documentos o reemplazarlos en cualquier momento si es necesario
1. **Validation**: es en esta instancia donde validaremos lo que nos ha devuelto
   la inteligencia artificial. Tendremos un form donde podremos ir seleccionando
   las sugerencias hechas por la IA o completar con lo que corresponda en ese momento.
   Cada vez que se valida un documento, se crea una conexión con la
   _Spreadsheet API_ de _Google_ para poder enviar los datos finales
1. **Finish**: podremos ver una vista preview de los documentos que validamos y
   enviamos, con la posibilidad de revisar el set de datos o de realizar una nueva
   carga, reiniciando el flujo de trabajo
